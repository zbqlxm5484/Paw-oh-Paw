"""통과별 프레임 관절 각도(BE-14, 명세 12.4 관절 각도 파일, 15.6 GET /shots/{shot_id}/angles)."""

from __future__ import annotations

import copy
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClientError, load_fixture
from app.models import Shot
from app.services.analysis_results import ResultFormatError
from app.services.shot_angles import JOINTS, MAX_PASS_FRAMES, build_angles, dump_angles
from app.services.shots import delete_shot
from app.storage.base import get_storage
from app.storage.keys import analysis_key, angles_key
from tests.conftest import bearer
from tests.test_render_worker import FakeExecutor, KeypointClient, _done_shot, _renderer, _run, _session, _settings

SHOT_ID = uuid.uuid4()


def _frame(frame: int, side: str, base: float) -> dict[str, Any]:
    """그 쪽 다리의 여섯 각도. 관절마다 base에 0, 1, 2…를 더한다."""
    suffix = side[0]
    return {
        "frame": frame,
        "camera_side": side,
        "points": None,
        "angles": {f"{joint}_{suffix}": base + index for index, joint in enumerate(JOINTS)},
    }


def _keypoints(*frames: dict[str, Any], fps: Any = 59.94) -> dict[str, Any]:
    return {"angle_def": "v1", "fps": fps, "width": 1920, "height": 1080, "frames": list(frames)}


def _result(name: str = "valid") -> dict[str, Any]:
    return copy.deepcopy(load_fixture(f"result_{name}"))


# ---- 만들기 ----


def test_valid_passes_get_their_measure_window() -> None:
    doc = build_angles(_result(), _keypoints(), shot_id=SHOT_ID, job_id="job-1")
    assert doc["job_id"] == "job-1" and doc["fps"] == 59.94
    assert [(p["pass_no"], p["camera_side"], p["gait_type"], p["start_frame"]) for p in doc["passes"]] == [
        (1, "RIGHT", "TROT", 42),
        (2, "LEFT", "TROT", 252),
        (3, "RIGHT", "TROT", 472),
        (4, "LEFT", "TROT", 692),
    ]
    first = doc["passes"][0]
    assert list(first["angles"]) == list(JOINTS)
    # measure_start 42 ~ measure_end 176, 양 끝 포함
    assert {len(values) for values in first["angles"].values()} == {135}
    assert set(first["angles"]["stifle"]) == {None}


def test_excluded_passes_are_left_out() -> None:
    result = _result("partial")
    assert [item["valid"] for item in result["passes"]].count(False) == 1
    doc = build_angles(result, _keypoints(), shot_id=SHOT_ID, job_id="job-1")
    assert len(doc["passes"]) == 2
    assert build_angles(_result("invalid"), _keypoints(), shot_id=SHOT_ID, job_id="j")["passes"] == []


def test_angles_come_from_the_camera_side_and_missing_frames_are_null() -> None:
    keypoints = _keypoints(
        _frame(41, "right", 100.0),  # 유효 구간 밖
        _frame(42, "right", 110.0),
        {"frame": 43, "camera_side": None, "points": None, "angles": None},
        _frame(44, "left", 120.0),  # 반대쪽 다리의 각도만 있다
        _frame(252, "left", 130.0),
        _frame(253, "right", 140.0),
    )
    doc = build_angles(_result(), keypoints, shot_id=SHOT_ID, job_id="job-1")
    right, left = doc["passes"][0]["angles"], doc["passes"][1]["angles"]
    assert right["shoulder"][:4] == [110.0, None, None, None]
    assert right["tarsus"][0] == 115.0
    assert left["shoulder"][:3] == [130.0, None, None]
    assert left["stifle"][0] == 134.0


@pytest.mark.parametrize("value", [True, "123.4", None, float("nan"), float("inf"), [1.0]])
def test_values_that_are_not_numbers_become_null(value: Any) -> None:
    keypoints = _keypoints({"frame": 42, "camera_side": "right", "angles": {"stifle_r": value, "hip_r": 98}})
    angles = build_angles(_result(), keypoints, shot_id=SHOT_ID, job_id="job-1")["passes"][0]["angles"]
    assert angles["stifle"][0] is None
    assert angles["hip"][0] == 98.0


@pytest.mark.parametrize(
    "window",
    [
        {},
        {"measure_start": None, "measure_end": None},
        {"measure_start": 10, "measure_end": 100},
        {"measure_start": 100, "measure_end": 50},
        {"measure_start": 42, "measure_end": 9999},
        {"measure_start": True, "measure_end": 100},
    ],
)
def test_without_a_usable_measure_window_the_whole_pass_is_used(window: dict) -> None:
    result = _result()
    first = result["passes"][0]
    first.pop("measure_start")
    first.pop("measure_end")
    first.update(window)
    passed = build_angles(result, _keypoints(), shot_id=SHOT_ID, job_id="job-1")["passes"][0]
    # 통과 구간 30 ~ 190
    assert passed["start_frame"] == 30
    assert len(passed["angles"]["hip"]) == 161


@pytest.mark.parametrize(
    "keypoints", [None, [], {"frames": None}, {"frames": [1, "x", {"frame": "42"}, {"frame": 42}]}]
)
def test_broken_keypoints_give_nulls_not_errors(keypoints: Any) -> None:
    doc = build_angles(_result(), keypoints, shot_id=SHOT_ID, job_id="job-1")
    assert doc["fps"] is None
    assert len(doc["passes"]) == 4 and set(doc["passes"][0]["angles"]["hip"]) == {None}


def test_absurdly_long_pass_and_broken_result_are_errors() -> None:
    result = _result()
    first = result["passes"][0]
    first.update(start_frame=0, end_frame=MAX_PASS_FRAMES, measure_start=0, measure_end=MAX_PASS_FRAMES)
    with pytest.raises(ValueError, match="pass 1 spans"):
        build_angles(result, _keypoints(), shot_id=SHOT_ID, job_id="job-1")
    first.update(end_frame=MAX_PASS_FRAMES - 1, measure_end=MAX_PASS_FRAMES - 1)
    assert len(build_angles(result, _keypoints(), shot_id=SHOT_ID, job_id="j")["passes"][0]["angles"]["hip"]) == 36_000
    with pytest.raises(ResultFormatError):
        build_angles({"validity": "valid"}, _keypoints(), shot_id=SHOT_ID, job_id="job-1")


# ---- 워커 ----


def _analyzed_shot(db: Session, dog, session, seq_no: int = 1, **kwargs: Any) -> Shot:
    """DONE 촬영에 분석 결과 JSON(유효 통과 넷)을 붙인다."""
    shot = _done_shot(db, dog, session, seq_no, **kwargs)
    key = analysis_key(dog.institution_id, dog.id, session.id, shot.id)
    get_storage().write_bytes(key, json.dumps(load_fixture("result_valid")).encode("utf-8"))
    shot.analysis_key = key
    db.flush()
    return shot


def _angles_path(dog, session, shot):
    return get_storage().path(angles_key(dog.institution_id, dog.id, session.id, shot.id))


def _angles_url(shot) -> str:
    return f"/api/v1/shots/{shot.id}/angles"


def test_worker_stores_angles_when_it_fetches_keypoints(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    session = _session(db, dog, staff)
    shot = _analyzed_shot(db, dog, session)
    settings = _settings()
    analysis = KeypointClient(_keypoints(_frame(42, "right", 110.0), _frame(252, "left", 130.0), fps=10))
    renderer = _renderer(settings, analysis, FakeExecutor("hang"))
    assert _run(db, renderer, settings, analysis).render_started == 1

    stored = json.loads(_angles_path(dog, session, shot).read_bytes())
    assert stored["job_id"] == "job-1" and len(stored["passes"]) == 4
    assert analysis.calls == ["job-1"]  # 관절점 파일은 결과 영상용으로 한 번만 받는다

    body = client.get(_angles_url(shot), headers=auth_headers).json()
    assert (body["shot_id"], body["fps"]) == (str(shot.id), 10.0)
    assert [p["pass_no"] for p in body["passes"]] == [1, 2, 3, 4]
    assert body["passes"][0] == {**stored["passes"][0]}
    assert body["passes"][0]["angles"]["stifle"][:2] == [114.0, None]
    assert body["passes"][1]["angles"]["shoulder"][0] == 130.0
    renderer.shutdown()


def test_angles_are_discarded_when_the_shot_changed_meanwhile(db: Session, dog, staff, caplog) -> None:
    session = _session(db, dog, staff)
    shot = _analyzed_shot(db, dog, session)
    real = get_storage()

    class ChangesTheShot:
        """angles.json을 쓰는 순간 촬영이 다시 분석에 들어간 것처럼 job_id를 바꾼다."""

        def __getattr__(self, name: str) -> Any:
            return getattr(real, name)

        def write_bytes(self, key: str, data: bytes) -> None:
            real.write_bytes(key, data)
            if key.endswith("angles.json"):
                db.execute(update(Shot).where(Shot.id == shot.id).values(job_id="job-2"))

    settings = _settings()
    analysis = KeypointClient()
    renderer = _renderer(settings, analysis, FakeExecutor("hang"), storage=ChangesTheShot())
    with caplog.at_level(logging.WARNING, logger="app.worker.render"):
        _run(db, renderer, settings, analysis)
    assert not _angles_path(dog, session, shot).exists()
    assert "angles.json discarded" in caplog.text
    renderer.shutdown()


def test_angles_failure_does_not_stop_the_video(db: Session, dog, staff, caplog) -> None:
    session = _session(db, dog, staff)
    missing = _done_shot(db, dog, session, 1, analyzed_sec=1)
    missing.analysis_key = analysis_key(dog.institution_id, dog.id, session.id, missing.id)  # 파일은 없다
    broken = _analyzed_shot(db, dog, session, 2, analyzed_sec=2)
    get_storage().write_bytes(broken.analysis_key, b'{"validity": "valid"}')
    without_key = _done_shot(db, dog, session, 3, analyzed_sec=3)
    db.flush()
    settings = _settings(WORKER_RENDER_CONCURRENCY=3)
    analysis = KeypointClient()
    renderer = _renderer(settings, analysis, FakeExecutor("hang"))
    with caplog.at_level(logging.ERROR, logger="app.worker.render"):
        stats = _run(db, renderer, settings, analysis)
    assert stats.render_started == 3 and stats.render_failed == 0
    assert caplog.text.count("angles store failed") == 2
    for shot in (missing, broken, without_key):
        assert not _angles_path(dog, session, shot).exists()
    # 로그에 파일 경로가 없다(11.8)
    assert str(dog.id) not in caplog.text
    renderer.shutdown()


def test_deleting_the_shot_removes_the_angles_file(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    shot = _analyzed_shot(db, dog, session)
    settings = _settings()
    analysis = KeypointClient()
    renderer = _renderer(settings, analysis, FakeExecutor("hang"))
    _run(db, renderer, settings, analysis)
    path = _angles_path(dog, session, shot)
    assert path.exists()
    delete_shot(db, staff.institution_id, shot.id, analysis)
    assert not path.exists()
    renderer.shutdown()


# ---- API ----


# ---- 다시 만들기(12.4 관절 각도 파일, 271 리뷰) ----


class FlakyAngles:
    """angles.json 쓰기만 정해진 횟수만큼 실패하는 저장소(디스크가 잠깐 가득 찬 상황)."""

    def __init__(self, failures: int) -> None:
        self.real = get_storage()
        self.failures = failures

    def __getattr__(self, name: str) -> Any:
        return getattr(self.real, name)

    def write_bytes(self, key: str, data: bytes) -> None:
        if key.endswith("angles.json") and self.failures > 0:
            self.failures -= 1
            raise OSError(28, "No space left on device", str(self.real.path(key)))
        self.real.write_bytes(key, data)


def _ready_shot(db: Session, dog, session, seq_no: int, job_id: str, *, video: str = "READY", **kwargs: Any) -> Shot:
    """결과 영상까지 끝난 촬영. 분석 결과 파일은 있고 각도 파일은 없다."""
    shot = _analyzed_shot(db, dog, session, seq_no, job_id=job_id, **kwargs)
    shot.video_status = video
    db.flush()
    return shot


def _write_angles(dog, session, shot, job_id: str) -> None:
    key = angles_key(dog.institution_id, dog.id, session.id, shot.id)
    get_storage().write_bytes(key, dump_angles({"job_id": job_id, "fps": 10.0, "passes": []}))


def test_angles_that_could_not_be_stored_are_rebuilt_after_the_retry_interval(db: Session, dog, staff, caplog) -> None:
    session = _session(db, dog, staff)
    shot = _analyzed_shot(db, dog, session)
    settings = _settings()
    analysis = KeypointClient()
    renderer = _renderer(settings, analysis, FakeExecutor("run"), storage=FlakyAngles(1))

    with caplog.at_level(logging.INFO, logger="app.worker.render"):
        assert _run(db, renderer, settings, analysis).render_started == 1  # 영상은 그대로 맡긴다
        assert _run(db, renderer, settings, analysis).rendered == 1
        assert not _angles_path(dog, session, shot).exists()
        assert analysis.calls == ["job-1"]  # 간격이 되기 전에는 다시 받지 않는다

        renderer._next_angles_retry = 0.0  # 5분이 지났다
        _run(db, renderer, settings, analysis)
    assert json.loads(_angles_path(dog, session, shot).read_bytes())["job_id"] == "job-1"
    assert analysis.calls == ["job-1", "job-1"]  # 관절점 파일을 다시 받아 만들었다
    assert "retrying later" in caplog.text and f"angles rebuilt shot={shot.id}" in caplog.text
    assert str(dog.id) not in caplog.text  # 로그에 파일 경로가 없다(11.8)

    renderer._next_angles_retry = 0.0
    _run(db, renderer, settings, analysis)
    assert analysis.calls == ["job-1", "job-1"]  # 만든 뒤에는 더 하지 않는다
    renderer.shutdown()


def test_a_restarted_worker_finds_recent_shots_without_angles(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    missing = _ready_shot(db, dog, session, 1, "job-missing")
    stale = _ready_shot(db, dog, session, 2, "job-stale")
    _write_angles(dog, session, stale, "job-before")  # 다시 분석하기 전의 파일이 남아 있다
    good = _ready_shot(db, dog, session, 3, "job-good")
    _write_angles(dog, session, good, "job-good")
    old = _ready_shot(db, dog, session, 4, "job-old")
    old.analyzed_at = datetime.now(UTC) - timedelta(hours=49)
    no_video = _ready_shot(db, dog, session, 5, "job-no-video", video="FAILED")
    without_result = _done_shot(db, dog, session, 6, job_id="job-without-result")
    without_result.video_status = "READY"
    db.flush()

    settings = _settings()
    analysis = KeypointClient()
    renderer = _renderer(settings, analysis, FakeExecutor("hang"))  # 새로 켠 워커: 기억해 둔 것이 없다
    _run(db, renderer, settings, analysis)

    assert sorted(analysis.calls) == ["job-missing", "job-no-video", "job-stale"]
    for shot, job_id in (
        (missing, "job-missing"),
        (stale, "job-stale"),
        (no_video, "job-no-video"),
        (good, "job-good"),
    ):
        assert json.loads(_angles_path(dog, session, shot).read_bytes())["job_id"] == job_id
    assert not _angles_path(dog, session, old).exists()  # 48시간이 지난 촬영은 보지 않는다
    assert not _angles_path(dog, session, without_result).exists()

    _run(db, renderer, settings, analysis)
    assert len(analysis.calls) == 3  # 다음 확인(30분 뒤)까지는 다시 보지 않는다
    renderer.shutdown()


def test_failures_that_cannot_change_are_given_up(db: Session, dog, staff, caplog) -> None:
    session = _session(db, dog, staff)
    broken = _ready_shot(db, dog, session, 1, "job-broken")
    get_storage().write_bytes(broken.analysis_key, b'{"validity": "valid"}')  # 계약과 다른 분석 결과
    settings = _settings()
    analysis = KeypointClient()
    renderer = _renderer(settings, analysis, FakeExecutor("hang"))
    with caplog.at_level(logging.ERROR, logger="app.worker.render"):
        _run(db, renderer, settings, analysis)
    assert "giving up" in caplog.text and not _angles_path(dog, session, broken).exists()

    gone = _ready_shot(db, dog, session, 2, "job-gone")
    analysis.error = AnalysisClientError("gone", status_code=410)  # 분석 API에 작업이 없다
    renderer._next_angles_check = 0.0
    _run(db, renderer, settings, analysis)
    assert analysis.calls == ["job-broken", "job-gone"]
    assert renderer._angles_missing == {}

    analysis.error = None
    renderer._next_angles_check = 0.0  # 다음 확인에서도 그만둔 것은 다시 하지 않는다
    _run(db, renderer, settings, analysis)
    assert analysis.calls == ["job-broken", "job-gone"]
    assert not _angles_path(dog, session, gone).exists()
    renderer.shutdown()


def test_an_unreachable_analysis_api_stops_the_round_and_keeps_the_shots(db: Session, dog, staff, caplog) -> None:
    session = _session(db, dog, staff)
    first = _ready_shot(db, dog, session, 1, "job-a", analyzed_sec=2)
    second = _ready_shot(db, dog, session, 2, "job-b", analyzed_sec=1)
    settings = _settings()
    analysis = KeypointClient(error=AnalysisClientError("503", status_code=503))
    renderer = _renderer(settings, analysis, FakeExecutor("hang"))
    with caplog.at_level(logging.WARNING, logger="app.worker.render"):
        _run(db, renderer, settings, analysis)
    assert len(analysis.calls) == 1  # 답이 없으면 남은 촬영은 이번 차례에 부르지 않는다
    assert set(renderer._angles_missing) == {first.id, second.id}
    assert "retrying later" in caplog.text

    analysis.error = None
    renderer._next_angles_retry = 0.0
    _run(db, renderer, settings, analysis)
    assert renderer._angles_missing == {}
    assert _angles_path(dog, session, first).exists() and _angles_path(dog, session, second).exists()
    renderer.shutdown()


def test_a_shot_that_changed_before_the_retry_is_dropped(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    reanalysed = _analyzed_shot(db, dog, session, 1, analyzed_sec=1)
    deleted = _analyzed_shot(db, dog, session, 2, analyzed_sec=2)
    settings = _settings(WORKER_RENDER_CONCURRENCY=2)
    analysis = KeypointClient()
    renderer = _renderer(settings, analysis, FakeExecutor("hang"), storage=FlakyAngles(2))
    _run(db, renderer, settings, analysis)
    assert set(renderer._angles_missing) == {reanalysed.id, deleted.id}

    db.execute(update(Shot).where(Shot.id == reanalysed.id).values(job_id="job-2"))  # 다시 분석에 들어갔다
    delete_shot(db, dog.institution_id, deleted.id, KeypointClient())
    renderer._next_angles_retry = 0.0
    _run(db, renderer, settings, analysis)
    assert renderer._angles_missing == {} and len(analysis.calls) == 2  # 맡길 때 받은 두 번뿐이다
    assert not _angles_path(dog, session, reanalysed).exists()
    renderer.shutdown()


def test_a_file_that_is_already_there_is_not_rebuilt(db: Session, dog, staff) -> None:
    session = _session(db, dog, staff)
    shot = _ready_shot(db, dog, session, 1, "job-1")
    _write_angles(dog, session, shot, "job-1")
    settings = _settings()
    analysis = KeypointClient()
    renderer = _renderer(settings, analysis, FakeExecutor("hang"))
    renderer._angles_missing[shot.id] = "job-1"  # 저장소가 잠깐 안 읽혀 빠진 것으로 보였던 촬영
    _run(db, renderer, settings, analysis)
    assert analysis.calls == [] and renderer._angles_missing == {}
    renderer.shutdown()


def _stored(db: Session, dog, session, *, job_id: str | None = "job-1", doc: Any = None, **kwargs: Any) -> Shot:
    """DONE 촬영과, 통과 하나(프레임 42~44)가 든 angles.json."""
    shot = _done_shot(db, dog, session, 1, **kwargs)
    if doc is None:
        doc = {
            "job_id": job_id,
            "fps": 59.94,
            "passes": [
                {
                    "pass_no": 1,
                    "camera_side": "RIGHT",
                    "gait_type": "TROT",
                    "start_frame": 42,
                    "angles": {joint: [112.4, None, 114.1] for joint in JOINTS},
                }
            ],
        }
    data = doc if isinstance(doc, bytes) else dump_angles(doc)
    get_storage().write_bytes(angles_key(dog.institution_id, dog.id, session.id, shot.id), data)
    return shot


def test_api_returns_the_stored_angles(client: TestClient, db: Session, dog, staff, auth_headers) -> None:
    session = _session(db, dog, staff)
    shot = _stored(db, dog, session)
    response = client.get(_angles_url(shot), headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "shot_id": str(shot.id),
        "fps": 59.94,
        "passes": [
            {
                "pass_no": 1,
                "camera_side": "RIGHT",
                "gait_type": "TROT",
                "start_frame": 42,
                "angles": {joint: [112.4, None, 114.1] for joint in JOINTS},
            }
        ],
    }


def test_no_file_gives_an_empty_list_with_the_shot_fps(
    client: TestClient, db: Session, dog, staff, auth_headers
) -> None:
    session = _session(db, dog, staff)
    shot = _done_shot(db, dog, session, 1)
    assert client.get(_angles_url(shot), headers=auth_headers).json() == {
        "shot_id": str(shot.id),
        "fps": 10.0,
        "passes": [],
    }


@pytest.mark.parametrize("status", ["UPLOADED", "SUBMITTED", "ANALYZING", "FAILED"])
def test_shot_that_is_not_done_gives_an_empty_list(client, db: Session, dog, staff, auth_headers, status: str) -> None:
    session = _session(db, dog, staff)
    shot = _stored(db, dog, session, status=status)
    assert client.get(_angles_url(shot), headers=auth_headers).json()["passes"] == []


def test_angles_of_an_earlier_analysis_are_not_served(client, db: Session, dog, staff, auth_headers) -> None:
    session = _session(db, dog, staff)
    shot = _stored(db, dog, session, job_id="job-2")  # 촬영의 job_id는 job-1이다
    assert client.get(_angles_url(shot), headers=auth_headers).json()["passes"] == []
    shot.job_id = "job-2"
    db.flush()
    assert len(client.get(_angles_url(shot), headers=auth_headers).json()["passes"]) == 1


@pytest.mark.parametrize(
    "doc",
    [
        b"not json",
        b"[]",
        {"job_id": "job-1", "passes": "x"},
        {"job_id": "job-1", "passes": [{"pass_no": 1}]},
        {"job_id": "job-1"},
    ],
)
def test_unreadable_file_gives_an_empty_list(client, db: Session, dog, staff, auth_headers, doc: Any) -> None:
    session = _session(db, dog, staff)
    shot = _stored(db, dog, session, doc=doc)
    response = client.get(_angles_url(shot), headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["passes"] == []


def test_other_institution_trashed_and_unknown_shots_are_404(
    client, db: Session, dog, staff, other_staff, auth_headers
) -> None:
    session = _session(db, dog, staff)
    shot = _stored(db, dog, session)
    assert client.get(_angles_url(shot), headers=bearer(other_staff)).status_code == 404
    assert client.get(f"/api/v1/shots/{uuid.uuid4()}/angles", headers=auth_headers).status_code == 404
    assert client.get(_angles_url(shot)).status_code == 401
    dog.deleted_at = datetime.now(UTC)
    db.flush()
    assert client.get(_angles_url(shot), headers=auth_headers).status_code == 404
