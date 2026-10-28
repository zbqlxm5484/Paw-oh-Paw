"""회차 시작·조회·취소(12.5, 13.3, 15.6, 17.3 BE-04·BE-09·BE-10 일부)."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dates import today_local
from app.models import Dog, MeasureSession, Shot, WalkPass
from app.storage.base import get_storage
from app.storage.keys import session_prefix
from tests.conftest import bearer

SESSION_OUT_KEYS = {
    "id",
    "dog_id",
    "staff",
    "measured_on",
    "weight_kg",
    "size_class",
    "status",
    "fail_reason",
    "model_name",
    "model_version",
    "completed_at",
    "aggregated_at",
    "created_at",
}


def _start(client: TestClient, headers: dict, dog_id, **body):
    return client.post(f"/api/v1/dogs/{dog_id}/sessions", json=body, headers=headers)


def _shot(db: Session, session: MeasureSession, seq_no: int, status: str = "DONE") -> Shot:
    shot = Shot(
        session_id=session.id,
        seq_no=seq_no,
        status=status,
        original_key=f"k/{uuid.uuid4()}/original.mp4",
        width=1920,
        height=1080,
        fps=Decimal("30"),
        duration_sec=Decimal("4.5"),
        bitrate_kbps=8000,
        codec="h264",
        uploaded_at=datetime.now(UTC),
        analyzed_at=datetime.now(UTC) if status == "DONE" else None,
    )
    db.add(shot)
    db.flush()
    return shot


def _pass(db: Session, shot: Shot, pass_no: int, side: str, valid: bool, reason: str | None = None) -> WalkPass:
    row = WalkPass(
        shot_id=shot.id,
        pass_no=pass_no,
        camera_side=side,
        gait_type="TROT",
        is_valid=valid,
        exclude_reason=reason,
        start_frame=pass_no * 10,
        end_frame=pass_no * 10 + 9,
    )
    db.add(row)
    db.flush()
    return row


# ---- 회차 시작 (BE-04) ----


def test_start_session_defaults_to_today_and_null_weight(client: TestClient, auth_headers: dict, staff, dog) -> None:
    response = _start(client, auth_headers, dog.id)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == SESSION_OUT_KEYS
    assert body["status"] == "MEASURING"
    assert body["measured_on"] == today_local().isoformat()
    assert body["weight_kg"] is None
    assert body["size_class"] == "LARGE"  # 그날 체중이 없으면 등록 체중 28.4 kg으로
    assert body["dog_id"] == str(dog.id)
    assert body["staff"] == {"id": str(staff.id), "name": "담당자"}
    assert body["fail_reason"] is None and body["completed_at"] is None
    assert body["created_at"].endswith("Z")


def test_start_session_with_values(client: TestClient, auth_headers: dict, dog) -> None:
    response = _start(client, auth_headers, dog.id, measured_on="2026-10-01", weight_kg=28.1)
    assert response.status_code == 201
    assert response.json()["measured_on"] == "2026-10-01"
    assert response.json()["weight_kg"] == 28.1
    assert response.json()["size_class"] == "LARGE"


def test_session_size_class_follows_that_day_weight_not_the_dog(client: TestClient, auth_headers: dict, dog) -> None:
    """감량한 반려견(등록 28.4 kg LARGE → 그날 23.0 kg): 회차는 MEDIUM, 반려견은 그대로 LARGE(12.5 6번)."""
    response = _start(client, auth_headers, dog.id, weight_kg=23.0)
    assert response.status_code == 201
    assert response.json()["size_class"] == "MEDIUM"
    dog_out = client.get(f"/api/v1/dogs/{dog.id}", headers=auth_headers).json()
    assert (dog_out["size_class"], dog_out["weight_kg"]) == ("LARGE", 28.4)
    detail = client.get(f"/api/v1/sessions/{response.json()['id']}", headers=auth_headers).json()
    assert detail["size_class"] == "MEDIUM"
    assert detail["dog"]["size_class"] == "LARGE"


def test_session_size_class_uses_manual_dog_size(client: TestClient, db: Session, auth_headers: dict, dog) -> None:
    dog.size_class = "SMALL"
    dog.size_class_manual = True
    db.flush()
    response = _start(client, auth_headers, dog.id, weight_kg=30.0)
    assert response.status_code == 201
    assert response.json()["size_class"] == "SMALL"  # 직접 지정한 체급은 체중과 상관없다


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"measured_on": str(today_local() + timedelta(days=1))}, "measured_on"),
        ({"weight_kg": 0.4}, "weight_kg"),
        ({"weight_kg": 100.01}, "weight_kg"),
    ],
)
def test_start_session_input_rules(client: TestClient, auth_headers: dict, dog, body: dict, field: str) -> None:
    response = _start(client, auth_headers, dog.id, **body)
    assert response.status_code == 422
    assert [f["field"] for f in response.json()["error"]["detail"]["fields"]] == [field]


def test_second_start_is_409_with_open_session_id(client: TestClient, auth_headers: dict, dog) -> None:
    first = _start(client, auth_headers, dog.id).json()["id"]
    second = _start(client, auth_headers, dog.id)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "SESSION_ALREADY_OPEN"
    assert second.json()["error"]["detail"] == {"session_id": first}


def test_start_session_for_other_institution_dog_is_404(
    client: TestClient, db: Session, auth_headers: dict, other_staff
) -> None:
    theirs = Dog(
        institution_id=other_staff.institution_id,
        name="남의개",
        breed="믹스",
        weight_kg=Decimal("5"),
        size_class="SMALL",
    )
    db.add(theirs)
    db.flush()
    other = _start(client, auth_headers, theirs.id)
    missing = _start(client, auth_headers, uuid.uuid4())
    assert other.status_code == missing.status_code == 404
    assert other.json() == missing.json()


# ---- 회차 조회 (BE-07·09) ----


def test_session_detail_shape(client: TestClient, auth_headers: dict, dog) -> None:
    session_id = _start(client, auth_headers, dog.id).json()["id"]
    response = client.get(f"/api/v1/sessions/{session_id}", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == SESSION_OUT_KEYS | {"dog", "progress", "notices", "shots"}
    assert body["dog"] == {
        "id": str(dog.id),
        "name": "보리",
        "breed": "골든 리트리버",
        "weight_kg": 28.4,
        "size_class": "LARGE",
    }
    recommended = get_settings().RECOMMENDED_PASSES
    assert body["progress"] == {
        "LEFT": {"valid_passes": 0, "recommended": recommended},
        "RIGHT": {"valid_passes": 0, "recommended": recommended},
    }
    assert body["notices"] == [] and body["shots"] == []


def test_session_detail_other_institution_is_404(client: TestClient, auth_headers: dict, dog, other_staff) -> None:
    session_id = _start(client, auth_headers, dog.id).json()["id"]
    other = client.get(f"/api/v1/sessions/{session_id}", headers=bearer(other_staff))
    missing = client.get(f"/api/v1/sessions/{uuid.uuid4()}", headers=bearer(other_staff))
    assert other.status_code == missing.status_code == 404
    assert other.json() == missing.json()


def test_progress_notices_and_shot_list(client: TestClient, db: Session, auth_headers: dict, dog) -> None:
    session = db.get(MeasureSession, _start(client, auth_headers, dog.id).json()["id"])
    done = _shot(db, session, 1, "DONE")
    _pass(db, done, 2, "LEFT", True)
    _pass(db, done, 1, "LEFT", True)
    _pass(db, done, 3, "RIGHT", False, "RUNNING")
    pending = _shot(db, session, 2, "UPLOADED")
    _pass(db, pending, 1, "RIGHT", True)  # DONE이 아닌 촬영의 통과는 세지 않는다

    body = client.get(f"/api/v1/sessions/{session.id}", headers=auth_headers).json()
    assert body["progress"]["LEFT"]["valid_passes"] == 2
    assert body["progress"]["RIGHT"]["valid_passes"] == 0
    assert [n["code"] for n in body["notices"]] == ["ONE_SIDE_ONLY"]
    assert body["notices"][0]["message"]

    assert [s["seq_no"] for s in body["shots"]] == [2, 1]  # 최신이 위
    assert body["shots"][0]["passes"] == []  # UPLOADED면 빈 배열
    done_out = body["shots"][1]
    assert [p["pass_no"] for p in done_out["passes"]] == [1, 2, 3]
    assert done_out["passes"][2]["exclude_reason"] == {
        "code": "RUNNING",
        "message": done_out["passes"][2]["exclude_reason"]["message"],
    }
    assert done_out["passes"][0]["exclude_reason"] is None
    assert done_out["uploaded_at"].endswith("Z") and done_out["analyzed_at"].endswith("Z")

    recommended = get_settings().RECOMMENDED_PASSES
    more = _shot(db, session, 3, "DONE")
    for n in range(1, recommended + 1):
        _pass(db, more, n, "RIGHT", True)
    for n in range(1, recommended - 1):
        _pass(db, more, recommended + n, "LEFT", True)
    body = client.get(f"/api/v1/sessions/{session.id}", headers=auth_headers).json()
    assert body["progress"] == {
        "LEFT": {"valid_passes": recommended, "recommended": recommended},
        "RIGHT": {"valid_passes": recommended, "recommended": recommended},
    }
    assert [n["code"] for n in body["notices"]] == ["RECOMMENDED_MET"]


def test_session_detail_query_count_does_not_grow_with_shots(
    client: TestClient, db: Session, engine, auth_headers: dict, dog
) -> None:
    # 15.1: 촬영·통과는 selectinload로 한 번에 읽는다(N+1 금지). 촬영이 늘어도 SELECT 수가 같다
    session = db.get(MeasureSession, _start(client, auth_headers, dog.id).json()["id"])
    session_id = session.id  # expire_all() 뒤에 session.id를 읽으면 그 refresh SELECT까지 세게 된다

    def selects_for_one_detail_call() -> int:
        statements: list[str] = []

        def record(conn, cursor, statement, parameters, context, executemany) -> None:
            statements.append(statement)

        db.expire_all()
        event.listen(engine, "before_cursor_execute", record)
        try:
            assert client.get(f"/api/v1/sessions/{session_id}", headers=auth_headers).status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", record)
        return sum(1 for statement in statements if statement.lstrip().upper().startswith("SELECT"))

    first = _shot(db, session, 1, "DONE")
    _pass(db, first, 1, "LEFT", True)
    with_one_shot = selects_for_one_detail_call()
    assert with_one_shot > 0

    for seq_no in range(2, 9):
        more = _shot(db, session, seq_no, "DONE")
        for pass_no in range(1, 5):
            _pass(
                db, more, pass_no, "LEFT" if pass_no % 2 else "RIGHT", pass_no != 4, "RUNNING" if pass_no == 4 else None
            )
    assert selects_for_one_detail_call() == with_one_shot


# ---- 측정 취소 (BE-10) ----


def test_cancel_session_deletes_rows_and_files(client: TestClient, db: Session, auth_headers: dict, dog) -> None:
    session = db.get(MeasureSession, _start(client, auth_headers, dog.id).json()["id"])
    shot = _shot(db, session, 1, "DONE")
    _pass(db, shot, 1, "LEFT", True)
    prefix = session_prefix(dog.institution_id, dog.id, session.id)
    get_storage().write_bytes(f"{prefix}{shot.id}/original.mp4", b"video")
    dog.baseline_session_id = session.id
    db.flush()

    response = client.delete(f"/api/v1/sessions/{session.id}", headers=auth_headers)
    assert response.status_code == 204
    assert get_storage().stat_prefix(prefix) == (0, 0)
    assert db.scalar(select(MeasureSession.id).where(MeasureSession.id == session.id)) is None
    assert db.scalar(select(Shot.id).where(Shot.id == shot.id)) is None
    assert db.scalar(select(WalkPass.id).where(WalkPass.shot_id == shot.id)) is None
    db.refresh(dog)
    assert dog.baseline_session_id is None

    assert client.get(f"/api/v1/sessions/{session.id}", headers=auth_headers).status_code == 404
    assert client.get(f"/api/v1/dogs/{dog.id}", headers=auth_headers).json()["open_session_id"] is None
    assert _start(client, auth_headers, dog.id).status_code == 201  # 취소하면 다시 시작할 수 있다


def test_cancel_session_rules(client: TestClient, db: Session, auth_headers: dict, dog, other_staff) -> None:
    session = db.get(MeasureSession, _start(client, auth_headers, dog.id).json()["id"])
    _shot(db, session, 1, "SUBMITTED")
    in_progress = client.delete(f"/api/v1/sessions/{session.id}", headers=auth_headers)
    assert in_progress.status_code == 409
    assert in_progress.json()["error"]["code"] == "SHOT_IN_PROGRESS"

    other = client.delete(f"/api/v1/sessions/{session.id}", headers=bearer(other_staff))
    assert other.status_code == 404

    session.status = "DONE"
    db.flush()
    closed = client.delete(f"/api/v1/sessions/{session.id}", headers=auth_headers)
    assert closed.status_code == 409
    assert closed.json()["error"]["code"] == "SESSION_CLOSED"
