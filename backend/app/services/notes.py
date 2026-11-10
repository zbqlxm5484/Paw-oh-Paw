"""메모·진료 기록(BE-30, 12.5 차트 자료, 13.9, 15.11). 지우지 않고, 고치면 고치기 전 내용을 이력으로 남긴다.

반려견은 services/dogs.in_institution으로 거른다(다른 기관·휴지통은 404). 쓴 담당자는 로그인한 담당자다.
본문은 로그에 남기지 않는다(11.8). flush()까지만 한다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError, ErrorCode
from app.models import Dog, DogNote, DogNoteRevision, MeasureSession
from app.models.enums import CHART_CATEGORIES, MEMO_CATEGORIES
from app.schemas.chart import NoteItemIn, NoteOut, NoteRevisionOut, NoteUpdate
from app.services.dogs import get_dog, in_institution

# GET /dogs/{dog_id}/notes의 kind → 분류 묶음(15.11)
KINDS = {"memo": MEMO_CATEGORIES, "chart": CHART_CATEGORIES}


def _invalid(field: str, kind: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, {"fields": [{"field": field, "type": kind}]})


def _revision_counts(db: Session, note_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """메모별 고친 횟수. GROUP BY 한 번으로 센다(15.1 N+1 금지)."""
    if not note_ids:
        return {}
    rows = db.execute(
        select(DogNoteRevision.note_id, func.count())
        .where(DogNoteRevision.note_id.in_(note_ids))
        .group_by(DogNoteRevision.note_id)
    ).all()
    return {note_id: count for note_id, count in rows}


def _to_out(note: DogNote, revision_count: int) -> NoteOut:
    return NoteOut.model_validate(note).model_copy(update={"revision_count": revision_count})


def _check_session(db: Session, dog: Dog, session_id: uuid.UUID | None) -> None:
    """session_id는 같은 반려견의 회차여야 한다. 아니면 422(13.9)."""
    if session_id is None:
        return
    found = db.scalar(select(MeasureSession.id).where(MeasureSession.id == session_id, MeasureSession.dog_id == dog.id))
    if found is None:
        raise _invalid("session_id", "not_found")


def list_notes(
    db: Session,
    institution_id: uuid.UUID,
    dog_id: uuid.UUID,
    *,
    kind: str | None,
    session_id: uuid.UUID | None,
    page: int,
    size: int,
) -> tuple[list[NoteOut], int]:
    """목록(15.11). 쓴 시각 내림차순. kind는 memo 또는 chart, session_id를 주면 그 회차에 단 것만."""
    dog = get_dog(db, institution_id, dog_id)
    conditions = [DogNote.dog_id == dog.id]
    if kind is not None:
        conditions.append(DogNote.category.in_(KINDS[kind]))
    if session_id is not None:
        conditions.append(DogNote.session_id == session_id)
    notes = db.scalars(
        select(DogNote)
        .options(joinedload(DogNote.staff))
        .where(*conditions)
        .order_by(DogNote.created_at.desc(), DogNote.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    total = db.scalar(select(func.count()).select_from(DogNote).where(*conditions)) or 0
    counts = _revision_counts(db, [note.id for note in notes])
    return [_to_out(note, counts.get(note.id, 0)) for note in notes], total


def create_notes(
    db: Session,
    *,
    institution_id: uuid.UUID,
    staff_id: uuid.UUID,
    dog_id: uuid.UUID,
    session_id: uuid.UUID | None,
    items: list[NoteItemIn],
) -> list[NoteOut]:
    """한 건 또는 여러 건을 같은 시각으로 쓴다(15.11). 보낸 순서로 돌려준다."""
    dog = get_dog(db, institution_id, dog_id)
    _check_session(db, dog, session_id)
    now = datetime.now(UTC)  # 묶음의 created_at을 똑같이 맞추고, 요청마다 다르게 하려고 DB 기본값을 쓰지 않는다
    notes = [
        DogNote(
            dog_id=dog.id,
            session_id=session_id,
            category=item.category.value,
            body=item.body,
            important=item.important,
            staff_id=staff_id,
            created_at=now,
            updated_at=now,
        )
        for item in items
    ]
    db.add_all(notes)
    db.flush()
    return [_to_out(note, 0) for note in notes]


def _get_note(db: Session, institution_id: uuid.UUID, note_id: uuid.UUID, *, for_update: bool = False) -> DogNote:
    """없거나 다른 기관이거나 휴지통에 있는 반려견의 메모면 똑같이 404(15.1)."""
    query = (
        select(DogNote).join(Dog, DogNote.dog_id == Dog.id).where(DogNote.id == note_id, in_institution(institution_id))
    )
    if for_update:
        query = query.with_for_update(of=DogNote)
    note = db.scalars(query).one_or_none()
    if note is None:
        raise AppError(ErrorCode.NOT_FOUND)
    return note


def update_note(
    db: Session, *, institution_id: uuid.UUID, staff_id: uuid.UUID, note_id: uuid.UUID, data: NoteUpdate
) -> NoteOut:
    """보낸 것만 바꾼다(13.9). 고치기 전 내용을 이력에 한 줄 남기고, 바뀐 값이 없으면 아무것도 하지 않는다(12.5).

    분류는 같은 종류 안에서만 바꾼다(메모는 메모끼리, 진료 기록은 S·O·A·P끼리). 아니면 422.
    행을 잠그고 읽어, 두 사람이 동시에 고쳐도 이력이 한 줄씩 순서대로 남는다.
    """
    note = _get_note(db, institution_id, note_id, for_update=True)
    changes = data.model_dump(exclude_unset=True)
    body = changes.get("body", note.body)
    category = changes["category"].value if "category" in changes else note.category
    important = changes.get("important", note.important)
    if (category in CHART_CATEGORIES) != (note.category in CHART_CATEGORIES):
        raise _invalid("category", "kind_mismatch")

    if (body, category, important) != (note.body, note.category, note.important):
        now = datetime.now(UTC)
        db.add(
            DogNoteRevision(
                note_id=note.id,
                body=note.body,
                category=note.category,
                important=note.important,
                staff_id=note.staff_id,
                revised_at=now,
            )
        )
        note.body, note.category, note.important = body, category, important
        note.staff_id = staff_id
        note.updated_at = now
        db.flush()
        db.refresh(note)
    return _to_out(note, _revision_counts(db, [note.id]).get(note.id, 0))


def list_revisions(db: Session, institution_id: uuid.UUID, note_id: uuid.UUID) -> list[NoteRevisionOut]:
    """고치기 전 내용들, 최근에 바뀐 것부터(15.11)."""
    note = _get_note(db, institution_id, note_id)
    rows = db.scalars(
        select(DogNoteRevision)
        .options(joinedload(DogNoteRevision.staff))
        .where(DogNoteRevision.note_id == note.id)
        .order_by(DogNoteRevision.revised_at.desc(), DogNoteRevision.id.desc())
    ).all()
    return [NoteRevisionOut.model_validate(row) for row in rows]
