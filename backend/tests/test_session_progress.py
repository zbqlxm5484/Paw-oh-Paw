"""측정 화면 흐름을 끝까지(명세 15.6, 17.3 BE-07·09).

워커가 저장한 결과로 GET /sessions/{id}의 촬영 상태·progress·notices가 나온다. 업로드 검사는 test_uploads.py, 워커의
상태 변화는 test_worker.py, 회차 조회 자체는 test_sessions.py가 본다. 여기서는 그 셋을 이어, 화면(S3)이 2~3초마다 부르는
응답이 워커가 한 일을 그대로 보여 주는지 본다. 촬영 행은 업로드 API 대신 직접 넣는다(ffmpeg 없이도 돌게).
"""

from __future__ import annotations

import copy
import math
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisStatus, SubmitInfo, load_fixture
from app.core.config import Settings, get_settings
from app.models import Shot
from app.storage.base import get_storage
from app.worker.main import run_once

DONE = AnalysisStatus("done", model_name="fs-v4", model_version="0.1.0")


def _settings(**overrides: Any) -> Settings:
    return get_settings().model_copy(update={"WORKER_MAX_IN_FLIGHT_PER_INSTITUTION": 100, **overrides})


class ScriptedClient:
    """테스트가 정한 상태(status)를 답하는 분석 클라이언트. 결과 JSON은 작업 ID별로 준다. 작업 ID = job-<촬영 ID>."""

    def __init__(self) -> None:
        self.status = AnalysisStatus("queued")
        self.results: dict[str, dict[str, Any]] = {}

    def submit(self, video: Path, info: SubmitInfo) -> str:
        return f"job-{info.shot_id}"

    def get_status(self, job_id: str) -> AnalysisStatus:
        return self.status

    def get_result(self, job_id: str) -> dict[str, Any]:
        return self.results[job_id]

    def get_keypoints(self, job_id: str) -> dict[str, Any]:
        raise NotImplementedError("관절점 파일은 결과 영상 작업에서 쓴다")


def _start(client: TestClient, headers: dict, dog_id) -> uuid.UUID:
    response = client.post(f"/api/v1/dogs/{dog_id}/sessions", json={}, headers=headers)
    assert response.status_code == 201
    return uuid.UUID(response.json()["id"])


def _uploaded_shot(db: Session, session_id: uuid.UUID, seq_no: int) -> Shot:
    """업로드가 끝난 촬영 한 건(UPLOADED). 원본은 워커가 읽어 보낼 수 있게 저장소에 둔다."""
    key = f"{uuid.uuid4()}/{uuid.uuid4()}/{session_id}/{uuid.uuid4()}/original.mp4"
    get_storage().write_bytes(key, b"\x00\x00\x00\x18ftypmp42 fake video")
    shot = Shot(
        session_id=session_id,
        seq_no=seq_no,
        status="UPLOADED",
        original_key=key,
        width=1920,
        height=1080,
        fps=Decimal("30"),
        duration_sec=Decimal("4.5"),
        bitrate_kbps=8000,
        codec="h264",
        uploaded_at=datetime.now(UTC) + timedelta(seconds=seq_no),  # seq_no 순서 = 올린 순서
    )
    db.add(shot)
    db.flush()
    return shot


def _detail(client: TestClient, db: Session, headers: dict, session_id: uuid.UUID) -> dict[str, Any]:
    # 테스트는 요청과 워커가 DB 세션 하나를 같이 쓴다. 실제 서버처럼 요청마다 DB에서 새로 읽게 한다
    db.expire_all()
    response = client.get(f"/api/v1/sessions/{session_id}", headers=headers)
    assert response.status_code == 200
    return response.json()


def _statuses(body: dict[str, Any]) -> list[str]:
    return [shot["status"] for shot in body["shots"]]


def _all_on(result: dict[str, Any], side: str) -> dict[str, Any]:
    """견본 결과의 모든 통과를 한쪽(side)으로 바꾼 복사본."""
    changed = copy.deepcopy(result)
    for item in changed["passes"]:
        item["camera_side"] = side
    return changed


def _run(db: Session, analysis: ScriptedClient, times: int = 1) -> None:
    for _ in range(times):
        run_once(db, analysis, _settings(), get_storage())


def test_shot_status_and_progress_follow_the_worker(client: TestClient, db: Session, auth_headers: dict, dog) -> None:
    # 17.3 BE-07: 촬영 상태가 UPLOADED → SUBMITTED → ANALYZING → DONE 순서로 보인다
    # 17.3 BE-09: progress는 DONE 촬영의 유효 통과 수다(일부 유효 촬영의 제외된 통과는 세지 않는다)
    session_id = _start(client, auth_headers, dog.id)
    first = _uploaded_shot(db, session_id, 1)
    second = _uploaded_shot(db, session_id, 2)
    analysis = ScriptedClient()
    recommended = get_settings().RECOMMENDED_PASSES

    body = _detail(client, db, auth_headers, session_id)
    assert _statuses(body) == ["UPLOADED", "UPLOADED"]  # seq_no 내림차순
    assert body["progress"] == {
        "LEFT": {"valid_passes": 0, "recommended": recommended},
        "RIGHT": {"valid_passes": 0, "recommended": recommended},
    }
    assert body["notices"] == []

    _run(db, analysis)  # 가져와서 보냄. 분석 API는 아직 queued
    assert _statuses(_detail(client, db, auth_headers, session_id)) == ["SUBMITTED", "SUBMITTED"]

    analysis.status = AnalysisStatus("running")
    _run(db, analysis)
    assert _statuses(_detail(client, db, auth_headers, session_id)) == ["ANALYZING", "ANALYZING"]

    analysis.status = DONE
    analysis.results[f"job-{first.id}"] = load_fixture("result_valid")  # 오른쪽 2·왼쪽 2
    analysis.results[f"job-{second.id}"] = load_fixture("result_partial")  # 오른쪽 1·왼쪽 1 유효, 오른쪽 1 제외
    _run(db, analysis)
    body = _detail(client, db, auth_headers, session_id)
    newest, oldest = body["shots"]
    assert (oldest["status"], oldest["validity"], oldest["validity_reason"]) == ("DONE", "VALID", None)
    assert [pass_out["pass_no"] for pass_out in oldest["passes"]] == [1, 2, 3, 4]
    assert oldest["analyzed_at"] is not None
    assert (newest["status"], newest["validity"], newest["validity_reason"]) == ("DONE", "PARTIAL", None)
    assert [(p["camera_side"], p["is_valid"]) for p in newest["passes"]] == [
        ("RIGHT", True),
        ("LEFT", True),
        ("RIGHT", False),
    ]
    excluded = newest["passes"][2]
    assert excluded["exclude_reason"]["code"] == "NOT_SIDE_VIEW" and excluded["exclude_reason"]["message"]
    assert excluded["gait_type"] == "OTHER"
    assert body["progress"] == {
        "LEFT": {"valid_passes": 3, "recommended": recommended},
        "RIGHT": {"valid_passes": 3, "recommended": recommended},
    }
    assert body["notices"] == []


def test_one_side_only_when_the_worker_saves_passes_on_one_side(
    client: TestClient, db: Session, auth_headers: dict, dog
) -> None:
    # 14.4 ONE_SIDE_ONLY: 한쪽만 유효 통과가 있다 → 반대 방향으로도 걷게 하라는 안내
    session_id = _start(client, auth_headers, dog.id)
    shot = _uploaded_shot(db, session_id, 1)
    analysis = ScriptedClient()
    analysis.status = DONE
    analysis.results[f"job-{shot.id}"] = _all_on(load_fixture("result_valid"), "left")

    _run(db, analysis, times=2)  # 1: 가져와서 보냄, 2: done → 결과 저장

    body = _detail(client, db, auth_headers, session_id)
    assert _statuses(body) == ["DONE"]
    assert (body["progress"]["LEFT"]["valid_passes"], body["progress"]["RIGHT"]["valid_passes"]) == (4, 0)
    assert [notice["code"] for notice in body["notices"]] == ["ONE_SIDE_ONLY"]
    assert body["notices"][0]["message"]


def test_recommended_met_when_both_sides_reach_the_recommended_count(
    client: TestClient, db: Session, auth_headers: dict, dog
) -> None:
    # 14.4 RECOMMENDED_MET: 양쪽 모두 권장 수(RECOMMENDED_PASSES) 이상 → 측정을 끝내도 된다는 안내
    recommended = get_settings().RECOMMENDED_PASSES
    needed = math.ceil(recommended / 2)  # result_valid는 한쪽에 유효 통과가 2개씩
    session_id = _start(client, auth_headers, dog.id)
    shots = [_uploaded_shot(db, session_id, seq_no) for seq_no in range(1, needed + 1)]
    analysis = ScriptedClient()
    analysis.status = DONE
    for shot in shots:
        analysis.results[f"job-{shot.id}"] = load_fixture("result_valid")

    _run(db, analysis, times=2)

    body = _detail(client, db, auth_headers, session_id)
    assert _statuses(body) == ["DONE"] * needed
    assert body["progress"]["LEFT"]["valid_passes"] == body["progress"]["RIGHT"]["valid_passes"] == 2 * needed
    assert 2 * needed >= recommended
    assert [notice["code"] for notice in body["notices"]] == ["RECOMMENDED_MET"]


def test_no_recommended_met_when_only_one_side_reaches_the_count(
    client: TestClient, db: Session, auth_headers: dict, dog
) -> None:
    # 14.4 RECOMMENDED_MET은 양쪽 "모두" 권장 수 이상일 때만. 한쪽만 채우고 다른 쪽이 1 이상이면 안내가 없다
    # (ONE_SIDE_ONLY도 아니다. 그건 다른 쪽이 0일 때다)
    recommended = get_settings().RECOMMENDED_PASSES
    left_shots = math.ceil(recommended / 4)  # result_valid를 전부 왼쪽으로 돌리면 촬영 하나에 왼쪽 유효 통과 4개
    session_id = _start(client, auth_headers, dog.id)
    shots = [_uploaded_shot(db, session_id, seq_no) for seq_no in range(1, left_shots + 2)]
    analysis = ScriptedClient()
    analysis.status = DONE
    for shot in shots[:-1]:
        analysis.results[f"job-{shot.id}"] = _all_on(load_fixture("result_valid"), "left")
    analysis.results[f"job-{shots[-1].id}"] = load_fixture("result_partial")  # 오른쪽 1·왼쪽 1 유효

    _run(db, analysis, times=2)

    body = _detail(client, db, auth_headers, session_id)
    left, right = body["progress"]["LEFT"]["valid_passes"], body["progress"]["RIGHT"]["valid_passes"]
    assert left == 4 * left_shots + 1 and right == 1
    assert left >= recommended > right > 0
    assert body["notices"] == []
