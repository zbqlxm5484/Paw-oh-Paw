"""촬영 상세·다시 분석·삭제(13.3, 15.3, 15.6, 17.3 BE-06·10·11·12 일부)."""

import uuid
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_signed_url
from app.models import MeasureSession, Shot, WalkPass
from app.storage.base import get_storage
from app.storage.keys import shot_prefix
from app.worker.main import run_once
from tests.conftest import bearer
from tests.test_sessions import _pass, _shot, _start
from tests.test_worker import FakeClient, _settings
from tests.test_worker import _session as _worker_session
from tests.test_worker import _shot as _worker_shot

SHOT_OUT_KEYS = {
    "id",
    "seq_no",
    "status",
    "fail_reason",
    "validity",
    "validity_reason",
    "video_status",
    "below_min_spec",
    "passes",
    "uploaded_at",
    "analyzed_at",
}
DETAIL_ONLY_KEYS = {
    "width",
    "height",
    "fps",
    "duration_sec",
    "bitrate_kbps",
    "codec",
    "model_name",
    "model_version",
    "submitted_at",
    "video_ready_at",
    "video_url",
    "url_expires_at",
}


def _open_session(client: TestClient, db: Session, headers: dict, dog) -> MeasureSession:
    return db.get(MeasureSession, _start(client, headers, dog.id).json()["id"])


# ---- 촬영 상세 (BE-08·11·12) ----


def test_shot_detail_shape_and_passes(client: TestClient, db: Session, auth_headers: dict, dog) -> None:
    # 17.3 BE-11: 통과별 start_frame·end_frame·exclude_reason이 저장된 값과 같다. BE-12: 원본 주소·키는 어디에도 없다
    session = _open_session(client, db, auth_headers, dog)
    shot = _shot(db, session, 1, "DONE")
    shot.validity, shot.model_name, shot.model_version = "PARTIAL", "fs-v4", "0.1.0/v1"
    shot.submitted_at = datetime.now(UTC)
    _pass(db, shot, 2, "RIGHT", False, "RUNNING")
    _pass(db, shot, 1, "LEFT", True)
    db.flush()

    response = client.get(f"/api/v1/shots/{shot.id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == SHOT_OUT_KEYS | DETAIL_ONLY_KEYS
    assert body["id"] == str(shot.id) and body["status"] == "DONE" and body["validity"] == "PARTIAL"
    assert (body["width"], body["height"], body["codec"], body["bitrate_kbps"]) == (1920, 1080, "h264", 8000)
    assert body["fps"] == 30.0 and body["duration_sec"] == 4.5  # NUMERIC → JSON 숫자(15.1)
    assert (body["model_name"], body["model_version"]) == ("fs-v4", "0.1.0/v1")
    assert body["submitted_at"].endswith("Z") and body["analyzed_at"].endswith("Z")
    assert body["video_status"] == "PENDING" and body["video_url"] is None and body["url_expires_at"] is None
    assert [
        (p["pass_no"], p["camera_side"], p["is_valid"], p["start_frame"], p["end_frame"]) for p in body["passes"]
    ] == [
        (1, "LEFT", True, 10, 19),
        (2, "RIGHT", False, 20, 29),
    ]
    assert body["passes"][1]["exclude_reason"]["code"] == "RUNNING" and body["passes"][1]["exclude_reason"]["message"]
    assert "original" not in response.text and shot.original_key not in response.text


def test_shot_detail_signs_the_video_url_only_when_ready(
    client: TestClient, db: Session, auth_headers: dict, dog
) -> None:
    # 15.3: video_url은 video_status가 READY일 때만 서명 URL(11.6)이고 url_expires_at은 그 만료 시각이다
    session = _open_session(client, db, auth_headers, dog)
    shot = _shot(db, session, 1, "DONE")
    shot.video_status = "READY"
    shot.result_key = f"{shot_prefix(dog.institution_id, dog.id, session.id, shot.id)}result.mp4"
    shot.video_ready_at = datetime.now(UTC)
    db.flush()

    body = client.get(f"/api/v1/shots/{shot.id}", headers=auth_headers).json()

    path = f"/api/v1/shots/{shot.id}/video"
    parts = urlsplit(body["video_url"])
    query = parse_qs(parts.query)
    assert parts.path == path and set(query) == {"exp", "sig"}
    exp, sig = int(query["exp"][0]), query["sig"][0]
    assert verify_signed_url(path, exp, sig)
    assert not verify_signed_url(path, exp, sig[:-1] + ("0" if sig[-1] != "0" else "1"))  # 한 글자만 바꿔도 안 열린다
    assert datetime.fromisoformat(body["url_expires_at"].replace("Z", "+00:00")) == datetime.fromtimestamp(exp, UTC)
    assert body["video_ready_at"].endswith("Z")
    assert "result.mp4" not in response_text(body)  # 파일 키는 응답에 없다


def response_text(body: dict) -> str:
    import json

    return json.dumps(body, ensure_ascii=False)


def test_shot_detail_not_found_cases(client: TestClient, db: Session, auth_headers: dict, dog, other_staff) -> None:
    session = _open_session(client, db, auth_headers, dog)
    shot = _shot(db, session, 1, "UPLOADED")
    assert client.get(f"/api/v1/shots/{shot.id}", headers=bearer(other_staff)).status_code == 404  # 다른 기관
    assert client.get(f"/api/v1/shots/{uuid.uuid4()}", headers=auth_headers).status_code == 404
    assert client.get("/api/v1/shots/not-a-uuid", headers=auth_headers).status_code == 404  # 15.1


# ---- 다시 분석 (BE-10) ----


def test_retry_resets_the_failed_shot_and_the_worker_sends_it_again(
    client: TestClient, db: Session, auth_headers: dict, dog, staff
) -> None:
    # 15.6: fail_reason·job_id를 비우고 attempt_count 0, video_status PENDING, 남은 통과 행 삭제.
    # 17.3 BE-06: 다시 분석하면 워커가 처음부터 다시 보낸다
    session = _worker_session(db, dog, staff)
    shot = _worker_shot(
        db,
        session,
        1,
        "FAILED",
        fail_reason="ANALYSIS_SUBMIT_FAILED",
        job_id="old-job",
        attempt_count=3,
        video_status="FAILED",
    )
    db.add(
        WalkPass(
            shot_id=shot.id, pass_no=1, camera_side="LEFT", gait_type="TROT", is_valid=True, start_frame=0, end_frame=9
        )
    )
    db.flush()

    response = client.post(f"/api/v1/shots/{shot.id}/retry", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == SHOT_OUT_KEYS
    assert body["status"] == "UPLOADED" and body["fail_reason"] is None and body["passes"] == []
    assert body["video_status"] == "PENDING"
    db.expire_all()
    row = db.get(Shot, shot.id)
    assert (row.status, row.fail_reason, row.job_id, row.attempt_count, row.video_status) == (
        "UPLOADED",
        None,
        None,
        0,
        "PENDING",
    )
    assert db.scalar(select(WalkPass.id).where(WalkPass.shot_id == shot.id)) is None

    analysis = FakeClient()
    stats = run_once(db, analysis, _settings(), get_storage())
    assert stats.claimed == 1 and stats.submitted == 1
    db.expire_all()
    row = db.get(Shot, shot.id)
    assert row.status == "SUBMITTED" and row.job_id == "job-1" and row.attempt_count == 1


@pytest.mark.parametrize("status", ["UPLOADED", "SUBMITTED", "ANALYZING", "DONE"])
def test_retry_requires_a_failed_shot(client: TestClient, db: Session, auth_headers: dict, dog, status: str) -> None:
    session = _open_session(client, db, auth_headers, dog)
    shot = _shot(db, session, 1, status)
    response = client.post(f"/api/v1/shots/{shot.id}/retry", headers=auth_headers)
    assert response.status_code == 409 and response.json()["error"]["code"] == "SHOT_NOT_FAILED"
    db.expire_all()
    assert db.get(Shot, shot.id).status == status


def test_retry_rules_closed_session_and_other_institution(
    client: TestClient, db: Session, auth_headers: dict, dog, other_staff
) -> None:
    session = _open_session(client, db, auth_headers, dog)
    shot = _shot(db, session, 1, "FAILED")
    assert client.post(f"/api/v1/shots/{shot.id}/retry", headers=bearer(other_staff)).status_code == 404

    session.status = "DONE"
    db.flush()
    closed = client.post(f"/api/v1/shots/{shot.id}/retry", headers=auth_headers)
    assert closed.status_code == 409 and closed.json()["error"]["code"] == "SESSION_CLOSED"
    db.expire_all()
    assert db.get(Shot, shot.id).status == "FAILED"


# ---- 촬영 삭제 (BE-10) ----


def test_delete_shot_removes_its_files_and_rows_and_keeps_other_seq_no(
    client: TestClient, db: Session, auth_headers: dict, dog
) -> None:
    # 12.5·15.6: 파일 → 통과 → 촬영 순서로 지우고, 남은 촬영의 seq_no는 다시 매기지 않는다. 17.3 BE-10: 파일이 사라진다
    session = _open_session(client, db, auth_headers, dog)
    first = _shot(db, session, 1, "DONE")
    _pass(db, first, 1, "LEFT", True)
    second = _shot(db, session, 2, "DONE")
    _pass(db, second, 1, "RIGHT", True)
    storage = get_storage()
    first_prefix = shot_prefix(dog.institution_id, dog.id, session.id, first.id)
    second_prefix = shot_prefix(dog.institution_id, dog.id, session.id, second.id)
    storage.write_bytes(f"{first_prefix}original.mp4", b"video")
    storage.write_bytes(f"{first_prefix}analysis.json", b"{}")
    storage.write_bytes(f"{second_prefix}original.mp4", b"v")

    response = client.delete(f"/api/v1/shots/{first.id}", headers=auth_headers)

    assert response.status_code == 204
    assert storage.stat_prefix(first_prefix) == (0, 0)
    assert storage.stat_prefix(second_prefix) == (1, 1)  # 다른 촬영의 파일은 그대로
    assert db.scalar(select(Shot.id).where(Shot.id == first.id)) is None
    assert db.scalar(select(WalkPass.id).where(WalkPass.shot_id == first.id)) is None
    db.expire_all()
    assert db.get(Shot, second.id).seq_no == 2 and len(db.get(Shot, second.id).passes) == 1
    detail = client.get(f"/api/v1/sessions/{session.id}", headers=auth_headers).json()
    assert [s["seq_no"] for s in detail["shots"]] == [2]
    assert client.get(f"/api/v1/shots/{first.id}", headers=auth_headers).status_code == 404
    assert client.delete(f"/api/v1/shots/{first.id}", headers=auth_headers).status_code == 404


@pytest.mark.parametrize("status", ["SUBMITTED", "ANALYZING"])
def test_delete_shot_in_progress_is_409(client: TestClient, db: Session, auth_headers: dict, dog, status: str) -> None:
    # 13.3: 분석 중인 촬영을 지우면 워커가 없는 행에 결과를 쓰려 하므로 막는다
    session = _open_session(client, db, auth_headers, dog)
    shot = _shot(db, session, 1, status)
    response = client.delete(f"/api/v1/shots/{shot.id}", headers=auth_headers)
    assert response.status_code == 409 and response.json()["error"]["code"] == "SHOT_IN_PROGRESS"
    assert db.scalar(select(Shot.id).where(Shot.id == shot.id)) == shot.id


@pytest.mark.parametrize("status", ["UPLOADED", "DONE", "FAILED"])
def test_delete_shot_allowed_statuses(client: TestClient, db: Session, auth_headers: dict, dog, status: str) -> None:
    session = _open_session(client, db, auth_headers, dog)
    shot = _shot(db, session, 1, status)
    assert client.delete(f"/api/v1/shots/{shot.id}", headers=auth_headers).status_code == 204
    assert db.scalar(select(Shot.id).where(Shot.id == shot.id)) is None


def test_delete_shot_rules_closed_session_and_other_institution(
    client: TestClient, db: Session, auth_headers: dict, dog, other_staff
) -> None:
    session = _open_session(client, db, auth_headers, dog)
    shot = _shot(db, session, 1, "DONE")
    assert client.delete(f"/api/v1/shots/{shot.id}", headers=bearer(other_staff)).status_code == 404

    session.status = "DONE"
    db.flush()
    closed = client.delete(f"/api/v1/shots/{shot.id}", headers=auth_headers)
    assert closed.status_code == 409 and closed.json()["error"]["code"] == "SESSION_CLOSED"
    assert db.scalar(select(Shot.id).where(Shot.id == shot.id)) == shot.id
