"""촬영 상세·다시 분석·삭제·결과 영상 재생(13.3, 15.3, 15.6, 17.3 BE-06·10·11·12)."""

import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import make_signed_url, verify_signed_url
from app.models import MeasureSession, Shot, WalkPass
from app.services import shots as shot_service
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


# ---- 결과 영상 재생 (BE-12) ----

VIDEO_BYTES = bytes(range(256)) * 4  # 1,024바이트. Range로 자른 조각을 바이트 값으로 맞춰 본다


def _ready_shot(db: Session, dog, session: MeasureSession, seq_no: int = 1, data: bytes = VIDEO_BYTES) -> Shot:
    """결과 영상이 READY인 촬영. 파일은 저장소의 result_key 자리에 실제로 둔다."""
    shot = _shot(db, session, seq_no, "DONE")
    shot.video_status = "READY"
    shot.result_key = f"{shot_prefix(dog.institution_id, dog.id, session.id, shot.id)}result.mp4"
    shot.video_ready_at = datetime.now(UTC)
    db.flush()
    get_storage().write_bytes(shot.result_key, data)
    return shot


def _video_url(client: TestClient, headers: dict, shot: Shot) -> str:
    """촬영 상세가 준 video_url. 화면은 이 값을 <video src>에 그대로 넣는다(15.1)."""
    return client.get(f"/api/v1/shots/{shot.id}", headers=headers).json()["video_url"]


def _signed(path: str) -> str:
    return make_signed_url(path)[0]


def _not_found(response) -> bool:
    return response.status_code == 404 and response.json()["error"]["code"] == "NOT_FOUND"


def test_video_url_from_shot_detail_plays_without_a_token(
    client: TestClient, db: Session, auth_headers: dict, dog
) -> None:
    # 15.6: 상세가 준 video_url을 그대로 부르면 토큰 없이 video/mp4가 온다. Cache-Control은 private에 서명 유효 시간만큼
    session = _open_session(client, db, auth_headers, dog)
    shot = _ready_shot(db, dog, session)

    response = client.get(_video_url(client, auth_headers, shot))  # Authorization 없음

    assert response.status_code == 200
    assert response.headers["content-type"] == "video/mp4"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["cache-control"] == f"private, max-age={get_settings().FILE_URL_TTL_SEC}"
    assert int(response.headers["content-length"]) == len(VIDEO_BYTES)
    assert response.content == VIDEO_BYTES


def test_video_range_request_is_206_with_only_the_requested_bytes(
    client: TestClient, db: Session, auth_headers: dict, dog
) -> None:
    # 17.3 BE-12: 앞뒤로 넘기기. Range는 Starlette FileResponse가 처리한다(15.6)
    session = _open_session(client, db, auth_headers, dog)
    url = _video_url(client, auth_headers, _ready_shot(db, dog, session))
    size = len(VIDEO_BYTES)

    middle = client.get(url, headers={"Range": "bytes=100-355"})
    assert middle.status_code == 206
    assert middle.headers["content-range"] == f"bytes 100-355/{size}"
    assert middle.headers["content-type"] == "video/mp4"
    assert middle.content == VIDEO_BYTES[100:356]

    tail = client.get(url, headers={"Range": "bytes=-16"})  # 끝에서 16바이트
    assert tail.status_code == 206 and tail.content == VIDEO_BYTES[-16:]

    beyond = client.get(url, headers={"Range": f"bytes={size}-"})  # 파일 끝을 넘긴 구간
    assert beyond.status_code == 416 and beyond.headers["content-range"] == f"bytes */{size}"


def test_video_link_expired_or_tampered_is_403_before_looking_at_the_shot(
    client: TestClient, db: Session, auth_headers: dict, dog
) -> None:
    # 17.3 BE-12: 5분이 지나거나 sig를 한 글자만 바꿔도 403 FILE_LINK_EXPIRED.
    # 서명을 DB보다 먼저 보므로 없는 촬영도 403이다
    session = _open_session(client, db, auth_headers, dog)
    shot = _ready_shot(db, dog, session)
    path = f"/api/v1/shots/{shot.id}/video"
    query = parse_qs(urlsplit(_video_url(client, auth_headers, shot)).query)
    exp, sig = int(query["exp"][0]), query["sig"][0]
    flipped = sig[:-1] + ("0" if sig[-1] != "0" else "1")
    ttl = get_settings().FILE_URL_TTL_SEC
    expired, _ = make_signed_url(path, now=datetime.now(UTC) - timedelta(seconds=ttl + 1))
    other_path = f"/api/v1/shots/{uuid.uuid4()}/video"
    urls = {
        "만료": expired,
        "sig 한 글자 바꿈": f"{path}?exp={exp}&sig={flipped}",
        "exp만 늘림": f"{path}?exp={exp + 1}&sig={sig}",
        "exp가 정수 아님": f"{path}?exp={exp}x&sig={sig}",
        "exp 음수": f"{path}?exp=-{exp}&sig={sig}",
        "sig 없음": f"{path}?exp={exp}",
        "exp 없음": f"{path}?sig={sig}",
        "쿼리 없음": path,
        "다른 촬영의 서명": f"{path}?{urlsplit(_signed(other_path)).query}",
        "없는 촬영에 이 촬영의 서명": f"{other_path}?exp={exp}&sig={sig}",
    }
    for name, url in urls.items():
        response = client.get(url)
        assert response.status_code == 403, name
        assert response.json()["error"]["code"] == "FILE_LINK_EXPIRED", name
    assert client.get(f"{path}?exp={exp}&sig={sig}").status_code == 200  # 바른 서명은 그대로 열린다


def test_video_is_404_when_not_ready_gone_or_not_on_local_storage(
    client: TestClient, db: Session, auth_headers: dict, dog, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 15.6: 서명이 맞아도 video_status가 READY가 아니면 404. 촬영·파일이 없어도 404. 저장소가 S3면 이 API는 404(11.11)
    session = _open_session(client, db, auth_headers, dog)

    pending = _shot(db, session, 1, "DONE")  # video_status는 PENDING
    assert _not_found(client.get(_signed(f"/api/v1/shots/{pending.id}/video")))
    assert _not_found(client.get(_signed(f"/api/v1/shots/{uuid.uuid4()}/video")))  # 지워진 촬영
    assert client.get("/api/v1/shots/not-a-uuid/video?exp=1&sig=x").status_code == 404  # 15.1

    ready = _ready_shot(db, dog, session, seq_no=2)
    url = _video_url(client, auth_headers, ready)
    assert client.get(url).status_code == 200
    get_storage().delete(ready.result_key)
    assert _not_found(client.get(url))  # READY인데 파일이 없다

    on_s3 = _ready_shot(db, dog, session, seq_no=3)
    url = _video_url(client, auth_headers, on_s3)
    monkeypatch.setattr(shot_service, "get_storage", lambda: object())  # LocalStorage가 아닌 저장소
    assert _not_found(client.get(url))
