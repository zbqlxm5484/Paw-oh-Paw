"""시연 기관 데이터 넣기(scripts/seed_demo.py, S15P31A404-273).

분석 결과·관절점은 저장소의 견본(app/clients/fixtures)을 쓴다. 시연 폴더의 실제 파일(제니 영상·결과)은 회사 데이터라
저장소에 넣지 않는다.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import (
    Dog,
    DogHistory,
    DogNote,
    DogVital,
    Institution,
    MeasureSession,
    PurgeLog,
    Report,
    SessionMetric,
    Shot,
    Staff,
)
from app.services.shot_angles import shot_angles
from app.storage.base import StorageService, get_storage
from app.storage.local import LocalStorage
from app.video.probe import VideoInfo
from scripts import seed_demo
from scripts.seed_demo import RenderCache, SeedDemoError, demo_job_id, load_data, parse_day, seed

FIXTURES = Path(__file__).resolve().parents[1] / "app" / "clients" / "fixtures"
TODAY = date(2026, 11, 10)
PASSWORD = "Seed-demo-1234"
CODE = "DEMOT"
NAME = "시험 시연 병원(시연)"


def _shot(seq: int, result: str | None, *, video: str | None = None, status: str = "DONE") -> dict[str, Any]:
    return {
        "seq_no": seq,
        "status": status,
        "validity": None,
        "analysis": None if result is None else f"shots/{result}.analysis.json",
        "keypoints": None if result is None else "shots/keypoints.json",
        "video_file": video,
        "video_dir": "videos" if video else None,
    }


def _demo(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "format_version": 1,
        "institution": {"code": CODE, "name": NAME},
        "staff": [
            {"login_id": "seed-admin", "name": "김원장", "role": "ADMIN"},
            {"login_id": "seed-tech", "name": "박테크", "role": "STAFF"},
        ],
        "dogs": [
            {
                "key": "bori",
                "name": "보리",
                "breed": "",
                "weight_kg": 9.8,
                "size_class": "SMALL",
                "birth_year": 2020,
                "sex": "FEMALE_SPAYED",
                "stage": "REHAB",
                "focus_limb": "RH",
            },
            {"key": "dol", "name": "돌돌이", "breed": "", "weight_kg": 1.3, "stage": "PRE", "focus_limb": None},
        ],  # fmt: skip
        "histories": [
            {
                "dog": "bori",
                "occurred_on": "D-40",
                "kind": "SURGERY",
                "title": "TPLO",
                "site": "RH",
                "clinician": "김원장",
                "staff": "seed-admin",
            },
        ],  # fmt: skip
        "vitals": [
            {
                "dog": "bori",
                "measured_on": "D-28",
                "session": "bori_d28",
                "staff": "seed-tech",
                "weight_kg": 9.8,
                "temp_c": 38.6,
                "heart_rate": 120,
                "sbp": 127,
                "dbp": 71,
            },
            {
                "dog": "dol",
                "measured_on": "D-0",
                "session": None,
                "staff": "seed-tech",
                "weight_kg": None,
                "temp_c": 38.4,
                "heart_rate": None,
                "sbp": None,
                "dbp": None,
            },
        ],  # fmt: skip
        "notes": [
            {
                "dog": "bori",
                "category": "OTHER",
                "body": "시연용 예시 데이터",
                "important": False,
                "session": "bori_d28",
                "staff": "seed-admin",
            },
            {
                "dog": "bori",
                "category": "CAUTION",
                "body": "계단 금지",
                "important": True,
                "session": None,
                "staff": "seed-tech",
            },
        ],  # fmt: skip
        "sessions": [
            {
                "key": "bori_d28",
                "dog": "bori",
                "measured_on": "D-28",
                "staff": "seed-tech",
                "status": "DONE",
                "weight_kg": 9.8,
                "report_editions": ["OWNER", "VET"],
                "expected_symmetry": None,
                "shots": [_shot(1, "result_valid", video="a.mp4"), _shot(2, "result_partial")],
            },
            {
                "key": "bori_d0",
                "dog": "bori",
                "measured_on": "D-0",
                "staff": "seed-admin",
                "status": "MEASURING",
                "report_editions": [],
                "shots": [_shot(1, "result_valid"), _shot(2, None, status="ANALYZING")],
            },
            {
                "key": "bori_d2",
                "dog": "bori",
                "measured_on": "D-2",
                "staff": "seed-admin",
                "status": "DONE",
                "report_editions": ["OWNER"],
                "shots": [_shot(1, "result_invalid")],
            },
        ],  # fmt: skip
    }
    data.update(overrides)
    return data


def _write(tmp_path: Path, demo: dict[str, Any] | None = None) -> Path:
    root = tmp_path / "demo_seed"
    (root / "shots").mkdir(parents=True)
    for name in ("result_valid", "result_partial", "result_invalid"):
        shutil.copyfile(FIXTURES / f"{name}.json", root / "shots" / f"{name}.analysis.json")
    shutil.copyfile(FIXTURES / "keypoints.json", root / "shots" / "keypoints.json")
    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / "a.mp4").write_bytes(b"not really a video")
    (root / "demo.json").write_text(json.dumps(demo or _demo(), ensure_ascii=False), encoding="utf-8")
    return root


@pytest.fixture
def fake_video(monkeypatch: pytest.MonkeyPatch) -> None:
    """ffprobe 없이 업로드 검사를 통과시킨다. 영상 정보는 고정 값이다."""
    info = VideoInfo(
        width=1920,
        height=1080,
        fps=Decimal("59.94"),
        duration_sec=Decimal("4.50"),
        bitrate_kbps=16000,
        codec="h264",
        rotation=0,
    )

    monkeypatch.setattr(seed_demo, "check_video", lambda path, name: (info, "mp4", []))


class _Renders:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, video: Path, keypoints: Path, output: Path, *, ffmpeg_path: str) -> None:
        self.calls.append(video.name)
        output.write_bytes(b"rendered:" + video.read_bytes())


class _Analysis:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete(self, job_id: str) -> None:
        self.deleted.append(job_id)


def _run(db: Session, root: Path, tmp_path: Path, *, storage: StorageService | None = None, **kwargs: Any):
    renders = _Renders()
    cache = RenderCache(tmp_path / f"render-{uuid.uuid4().hex[:6]}", "ffmpeg", render=renders)
    cache.workdir.mkdir()
    store = storage or get_storage()
    report = seed(db, store, load_data(root), today=TODAY, password=PASSWORD, render_cache=cache, **kwargs)
    db.flush()
    return report, renders


def _institution(db: Session) -> Institution:
    return db.scalars(select(Institution).where(Institution.code == CODE)).one()


def _sessions(db: Session) -> dict[date, MeasureSession]:
    institution = _institution(db)
    rows = db.scalars(
        select(MeasureSession).join(Dog, MeasureSession.dog_id == Dog.id).where(Dog.institution_id == institution.id)
    ).all()
    return {row.measured_on: row for row in rows}


# ---- 넣기 ----


def test_seeds_accounts_dogs_records_and_finished_sessions(db: Session, tmp_path: Path, fake_video: None) -> None:
    report, _renders = _run(db, _write(tmp_path), tmp_path)

    institution = _institution(db)
    assert institution.name == NAME and institution.contract_ends_at is None
    accounts = db.scalars(select(Staff).where(Staff.institution_id == institution.id).order_by(Staff.login_id)).all()
    assert [a.login_id for a in accounts] == ["seed-admin", "seed-tech"]
    # ADMIN·STAFF는 크림오프 계정이라 시연 병원 계정은 모두 CLIENT다
    assert {a.role for a in accounts} == {"CLIENT"}
    assert all(verify_password(PASSWORD, a.password_hash) for a in accounts)
    assert any("CLIENT로 넣습니다" in note for note in report.notes)

    dogs = {d.name: d for d in db.scalars(select(Dog).where(Dog.institution_id == institution.id))}
    assert set(dogs) == {"보리", "돌돌이"}
    assert dogs["보리"].size_class == "SMALL" and dogs["보리"].stage == "REHAB" and dogs["보리"].focus_limb == "RH"
    assert dogs["돌돌이"].stage == "PRE" and dogs["돌돌이"].breed == ""

    history = db.scalars(select(DogHistory).where(DogHistory.dog_id == dogs["보리"].id)).one()
    assert history.occurred_on == TODAY - timedelta(days=40) and history.kind == "SURGERY"

    sessions = _sessions(db)
    first, today, two_days = sessions[TODAY - timedelta(days=28)], sessions[TODAY], sessions[TODAY - timedelta(days=2)]
    assert first.status == "DONE" and first.completed_at is not None and first.aggregated_at is not None
    assert db.scalar(select(func.count()).select_from(SessionMetric).where(SessionMetric.session_id == first.id)) > 0
    editions = db.scalars(select(Report.edition).where(Report.session_id == first.id)).all()
    assert sorted(editions) == ["OWNER", "VET"]
    assert db.scalars(select(Report.status).where(Report.session_id == first.id)).all() == ["PENDING", "PENDING"]

    # 측정 중 회차: 결과가 있는 촬영만 넣고, 분석 중이던 촬영은 넣지 않는다
    assert today.status == "MEASURING"
    assert db.scalars(select(Shot.seq_no).where(Shot.session_id == today.id)).all() == [1]
    assert report.skipped_shots and "bori_d0 촬영 02" in report.skipped_shots[0]

    # 유효 통과가 없는 회차는 수치 없이 DONE이다(12.3)
    assert two_days.status == "DONE"
    assert (
        db.scalar(select(func.count()).select_from(SessionMetric).where(SessionMetric.session_id == two_days.id)) == 0
    )
    assert any("두 판본" in note and "bori_d2" in note for note in report.notes)

    vital = db.scalars(select(DogVital).where(DogVital.dog_id == dogs["보리"].id)).one()
    assert vital.session_id == first.id and vital.measured_on == TODAY - timedelta(days=28)
    dol_vital = db.scalars(select(DogVital).where(DogVital.dog_id == dogs["돌돌이"].id)).one()
    assert dol_vital.temp_c == Decimal("38.4") and dol_vital.weight_kg is None

    notes = {n.body: n for n in db.scalars(select(DogNote).where(DogNote.dog_id == dogs["보리"].id))}
    assert notes["시연용 예시 데이터"].session_id == first.id
    assert notes["시연용 예시 데이터"].created_at.date() == TODAY - timedelta(days=28)
    assert notes["계단 금지"].important is True


def test_shots_take_the_worker_result_path_and_get_angles_and_videos(
    db: Session, tmp_path: Path, fake_video: None
) -> None:
    root = _write(tmp_path)
    report, renders = _run(db, root, tmp_path)
    storage = get_storage()
    institution = _institution(db)
    first = _sessions(db)[TODAY - timedelta(days=28)]
    shots = {s.seq_no: s for s in db.scalars(select(Shot).where(Shot.session_id == first.id))}

    for shot in shots.values():
        assert shot.status == "DONE" and shot.analysis_key and shot.job_id == demo_job_id(shot.id)
        # 받은 분석 결과를 바이트 그대로 둔다
        name = "result_valid" if shot.seq_no == 1 else "result_partial"
        assert storage.read_bytes(shot.analysis_key) == (root / "shots" / f"{name}.analysis.json").read_bytes()
        assert shot_angles(db, storage, institution.id, shot.id).passes, "관절 각도 API가 비면 안 된다"

    with_video, without_video = shots[1], shots[2]
    assert with_video.video_status == "READY" and with_video.width == 1920 and with_video.fps == Decimal("59.94")
    assert storage.read_bytes(with_video.result_key) == b"rendered:not really a video"
    assert storage.read_bytes(with_video.original_key) == b"not really a video"
    # 저장소의 put_file은 파일을 옮기므로 사본을 넣는다. 받은 영상은 그대로 있어야 한다
    assert (tmp_path / "videos" / "a.mp4").read_bytes() == b"not really a video"
    assert without_video.video_status == "FAILED" and without_video.result_key is None
    assert renders.calls == ["a.mp4"] and report.rendered == 1


def test_same_video_and_keypoints_render_once(db: Session, tmp_path: Path, fake_video: None) -> None:
    demo = _demo()
    demo["sessions"][2]["shots"] = [_shot(1, "result_valid", video="a.mp4")]
    report, renders = _run(db, _write(tmp_path, demo), tmp_path)
    assert renders.calls == ["a.mp4"] and report.rendered == 2


def test_no_render_cache_means_no_result_videos(db: Session, tmp_path: Path, fake_video: None) -> None:
    root = _write(tmp_path)
    seed(db, get_storage(), load_data(root), today=TODAY, password=PASSWORD)
    first = _sessions(db)[TODAY - timedelta(days=28)]
    assert set(db.scalars(select(Shot.video_status).where(Shot.session_id == first.id))) == {"FAILED"}


# ---- 다시 넣기 ----


def test_second_run_needs_reset(db: Session, tmp_path: Path, fake_video: None) -> None:
    root = _write(tmp_path)
    _run(db, root, tmp_path)
    with pytest.raises(SeedDemoError, match="--reset"):
        _run(db, root, tmp_path)


def test_reset_replaces_only_the_demo_institution(
    db: Session, tmp_path: Path, fake_video: None, dog: Dog, staff: Staff
) -> None:
    root = _write(tmp_path)
    _run(db, root, tmp_path)
    old_dogs = set(db.scalars(select(Dog.id).where(Dog.institution_id == _institution(db).id)))
    # 시연 중에 실제로 올린 촬영 하나(분석 API에 작업이 있다)
    live = _sessions(db)[TODAY]
    db.add(Shot(session_id=live.id, seq_no=5, status="DONE", job_id="real-job-1", original_key="x/original.mp4",
                width=1920, height=1080, fps=Decimal("30"), duration_sec=Decimal("4"), bitrate_kbps=8000,
                codec="h264", uploaded_at=live.created_at))  # fmt: skip
    db.flush()
    other_sessions = db.scalar(select(func.count()).select_from(MeasureSession).where(MeasureSession.dog_id == dog.id))

    analysis = _Analysis()
    report, _ = _run(db, root, tmp_path, reset=True, analysis=analysis)

    institution = _institution(db)
    new_dogs = set(db.scalars(select(Dog.id).where(Dog.institution_id == institution.id)))
    assert new_dogs and not (new_dogs & old_dogs)
    assert report.purged_rows > 0 and report.kept_accounts == ["seed-admin", "seed-tech"]
    # 넣은 촬영의 번호는 분석 API에 묻지 않고, 실제로 올린 촬영만 지운다
    assert analysis.deleted == ["real-job-1"]
    log = db.scalars(select(PurgeLog).where(PurgeLog.target_id == institution.id)).one()
    assert log.scope == "INSTITUTION" and log.analysis_jobs_deleted == 1
    # 다른 기관은 그대로다
    assert db.get(Dog, dog.id) is not None
    assert db.scalar(select(func.count()).select_from(MeasureSession).where(MeasureSession.dog_id == dog.id)) == (
        other_sessions
    )
    assert db.get(Staff, staff.id) is not None


# ---- 막는 경우 ----


def test_refuses_a_code_used_by_another_institution(db: Session, tmp_path: Path) -> None:
    db.add(Institution(code=CODE, name="진짜 병원"))
    db.flush()
    with pytest.raises(SeedDemoError, match="다른 이름"):
        _run(db, _write(tmp_path), tmp_path)
    assert db.scalar(select(func.count()).select_from(Dog)) == 0


def test_refuses_a_login_id_of_another_institution(db: Session, tmp_path: Path, staff: Staff) -> None:
    demo = _demo(staff=[{"login_id": staff.login_id, "name": "남", "role": "CLIENT"}])
    for item in demo["histories"] + demo["vitals"] + demo["notes"] + demo["sessions"]:
        item["staff"] = staff.login_id
    with pytest.raises(SeedDemoError, match="다른 기관"):
        _run(db, _write(tmp_path, demo), tmp_path)


def test_a_failure_leaves_no_rows_and_no_files(db: Session, tmp_path: Path, fake_video: None) -> None:
    root = _write(tmp_path)
    # 앞의 회차(영상·분석 결과·각도 파일)를 쓴 뒤 세 번째 회차에서 실패한다
    (root / "shots" / "result_invalid.analysis.json").write_text("{깨진 JSON", encoding="utf-8")
    # 저장소 키가 UUID 넷이라 pytest의 긴 tmp_path 아래에서는 Windows 경로 길이(260자)를 넘는다
    store_root = Path(tempfile.mkdtemp(prefix="seed-demo-"))
    with pytest.raises(SeedDemoError, match="분석 결과를 읽지 못했습니다"):
        _run(db, root, tmp_path, storage=LocalStorage(store_root))
    assert db.scalar(select(func.count()).select_from(Institution).where(Institution.code == CODE)) == 0
    assert db.scalar(select(func.count()).select_from(Dog)) == 0
    assert not [p for p in store_root.rglob("*") if p.is_file()], "넣다 만 파일이 남으면 안 된다"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d["histories"][0].update(occurred_on="40일 전"), "D-n"),
        (lambda d: d["vitals"][0].update(dog="nobody"), "없는 반려견"),
        (lambda d: d["sessions"][0].update(status="FAILED"), "DONE 또는 MEASURING"),
        (lambda d: d["sessions"][0]["shots"][0].update(analysis="shots/none.json"), "파일이 없습니다"),
        (lambda d: d.update(format_version=2), "format_version"),
    ],
)
def test_bad_folders_are_refused_before_anything_is_written(db: Session, tmp_path: Path, change, message: str) -> None:
    demo = _demo()
    change(demo)
    with pytest.raises(SeedDemoError, match=message):
        _run(db, _write(tmp_path, demo), tmp_path)
    assert db.scalar(select(func.count()).select_from(Institution).where(Institution.code == CODE)) == 0


def test_parse_day_counts_back_from_the_given_day() -> None:
    assert parse_day("D-0", TODAY, where="x") == TODAY
    assert parse_day("D-28", TODAY, where="x") == date(2026, 10, 13)
    with pytest.raises(SeedDemoError):
        parse_day("D+1", TODAY, where="x")


def test_cli_asks_nothing_when_accounts_exist_and_reports(
    clean_tables: None, tmp_path: Path, fake_video: None, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _write(tmp_path)
    args = ["--data", str(root), "--videos", str(tmp_path / "videos"), "--no-render", "--today", TODAY.isoformat()]
    assert seed_demo.main([*args, "--password", PASSWORD]) == 0
    out = capsys.readouterr().out
    assert "반려견 2, 회차 3, 촬영 4" in out and "bori_d28" in out
    # 두 번째: 계정이 다 있으니 비밀번호를 묻지 않고, --reset 확인 문구가 틀리면 그만둔다
    monkeypatch.setattr("scripts.seed_demo.getpass.getpass", lambda prompt: pytest.fail("묻지 않아야 한다"))
    monkeypatch.setattr("builtins.input", lambda prompt: "no")
    assert seed_demo.main([*args, "--reset"]) == 1
    assert seed_demo.main([*args, "--reset", "--yes"]) == 0
    assert "지운 행" in capsys.readouterr().out
