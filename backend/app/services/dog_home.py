"""홈 배지·최근 변동·가장 최근 대칭 점수(BE-32, 명세 12.5 홈 배지·변동, 15.3 DogOut).

저장하지 않고 조회할 때 계산한다. 반려견이 몇 마리든 load 한 번은 쿼리 다섯 번이다(15.1 N+1 금지).
글은 만들지 않는다. 코드와 재료(이름·부위·날짜)만 주고 화면이 글을 만든다.
이 모듈은 services/dogs.py가 부르므로 dogs를 import하지 않는다(거르는 조건은 인자로 받는다).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy import ColumnElement, distinct, exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.dates import local_zone
from app.models import Dog, DogHistory, DogNote, MeasureSession, Shot, WalkPass
from app.models.enums import DogBadgeCode, DogChangeCode, HistoryKind, SessionStatus, Validity
from app.schemas.dogs import DogBadgeOut, DogChangeOut, DogHistoryBriefOut
from app.services.symmetry import session_scores

# changed_within_days를 보내지 않았을 때 변동을 보는 날수
CHANGE_DAYS = 7
# 대칭 점수가 이만큼 이상 달라지면 좋아짐·나빠짐으로 본다(웹 화면의 기준과 같다)
GAIT_CHANGE_POINTS = 3
FINISHED = (SessionStatus.DONE.value, SessionStatus.FAILED.value)
BADGE_KINDS = (HistoryKind.SURGERY.value, HistoryKind.DIAGNOSIS.value)
CHANGE_ORDER = {code: position for position, code in enumerate(DogChangeCode)}


@dataclass(frozen=True)
class DogHome:
    badges: list[DogBadgeOut] = field(default_factory=list)
    changes: list[DogChangeOut] = field(default_factory=list)
    last_symmetry: int | None = None
    last_surgery: DogHistoryBriefOut | None = None
    last_diagnosis: DogHistoryBriefOut | None = None


def _since(today: date, days: int) -> date:
    """기간의 첫날. N일 전 그날을 포함한다."""
    return today - timedelta(days=days)


def candidate_ids(db: Session, dog_condition: ColumnElement[bool], *, days: int, today: date) -> list[uuid.UUID]:
    """기간 안에 변동이 있을 수 있는 반려견의 ID. 수술·중요 메모·끝난 회차 중 하나가 기간 안에 있다.

    끝난 회차가 기간 안에 하나라도 있으면 가장 최근에 끝난 회차도 기간 안이므로 빠지는 반려견이 없다.
    변동이 실제로 있는지는 load가 정한다(회차가 있어도 변동이 없을 수 있다).
    """
    since = _since(today, days)
    since_at = datetime.combine(since, time.min, tzinfo=local_zone())
    query = select(Dog.id).where(
        dog_condition,
        or_(
            exists().where(
                DogHistory.dog_id == Dog.id,
                DogHistory.kind == HistoryKind.SURGERY.value,
                DogHistory.occurred_on >= since,
            ),
            exists().where(DogNote.dog_id == Dog.id, DogNote.important.is_(True), DogNote.created_at >= since_at),
            exists().where(
                MeasureSession.dog_id == Dog.id,
                MeasureSession.status.in_(FINISHED),
                MeasureSession.measured_on >= since,
            ),
        ),
    )
    return list(db.scalars(query).all())


def _latest_history(db: Session, dog_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, dict[str, tuple]]:
    """반려견·종류(수술, 진단)마다 가장 최근 한 줄: {반려견: {종류: (이름, 부위, 날짜)}}."""
    rank = (
        func.row_number()
        .over(
            partition_by=(DogHistory.dog_id, DogHistory.kind),
            order_by=(DogHistory.occurred_on.desc(), DogHistory.created_at.desc(), DogHistory.id.desc()),
        )
        .label("rank")
    )
    ranked = (
        select(DogHistory.dog_id, DogHistory.kind, DogHistory.title, DogHistory.site, DogHistory.occurred_on, rank)
        .where(DogHistory.dog_id.in_(dog_ids), DogHistory.kind.in_(BADGE_KINDS))
        .subquery()
    )
    found: dict[uuid.UUID, dict[str, tuple]] = {}
    for dog_id, kind, title, site, occurred_on, _ in db.execute(select(ranked).where(ranked.c.rank == 1)):
        found.setdefault(dog_id, {})[kind] = (title, site, occurred_on)
    return found


def _latest_important_note(db: Session, dog_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, date]:
    """중요 표시가 켜진 메모·진료 기록 중 가장 최근 것을 쓴 날(한국 날짜)."""
    rows = db.execute(
        select(DogNote.dog_id, func.max(DogNote.created_at))
        .where(DogNote.dog_id.in_(dog_ids), DogNote.important.is_(True))
        .group_by(DogNote.dog_id)
    )
    zone = local_zone()
    return {dog_id: created_at.astimezone(zone).date() for dog_id, created_at in rows}


def _finished_sessions(db: Session, dog_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[tuple]]:
    """반려견마다 끝난 회차(DONE·FAILED)를 12.5 순서로: (회차 ID, status, measured_on)."""
    rows = db.execute(
        select(MeasureSession.dog_id, MeasureSession.id, MeasureSession.status, MeasureSession.measured_on)
        .where(MeasureSession.dog_id.in_(dog_ids), MeasureSession.status.in_(FINISHED))
        .order_by(MeasureSession.measured_on, MeasureSession.created_at, MeasureSession.id)
    )
    found: dict[uuid.UUID, list[tuple]] = {}
    for dog_id, session_id, status, measured_on in rows:
        found.setdefault(dog_id, []).append((session_id, status, measured_on))
    return found


def _shot_stats(db: Session, session_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
    """회차마다 (INVALID 촬영 수, 유효 통과 수). 촬영이 없는 회차는 결과에 없다."""
    if not session_ids:
        return {}
    rows = db.execute(
        select(
            Shot.session_id,
            func.count(distinct(Shot.id)).filter(Shot.validity == Validity.INVALID.value),
            func.count(WalkPass.id).filter(WalkPass.is_valid.is_(True)),
        )
        .outerjoin(WalkPass, WalkPass.shot_id == Shot.id)
        .where(Shot.session_id.in_(session_ids))
        .group_by(Shot.session_id)
    )
    return {session_id: (invalid, used) for session_id, invalid, used in rows}


def _badges(history: dict[str, tuple], noted_on: date | None) -> list[DogBadgeOut]:
    badges: list[DogBadgeOut] = []
    for kind, code in (
        (HistoryKind.SURGERY.value, DogBadgeCode.SURGERY),
        (HistoryKind.DIAGNOSIS.value, DogBadgeCode.DIAGNOSIS),
    ):
        if kind in history:
            title, site, occurred_on = history[kind]
            badges.append(DogBadgeOut(code=code, title=title, site=site, on=occurred_on))
            break  # 수술이 있으면 진단 배지는 주지 않는다
    if noted_on is not None:
        badges.append(DogBadgeOut(code=DogBadgeCode.IMPORTANT_NOTE, on=noted_on))
    return badges


def _brief(history: dict[str, tuple], kind: HistoryKind) -> DogHistoryBriefOut | None:
    """가장 최근 수술·진단 한 줄(15.3). 배지와 달리 수술이 있어도 진단을 가리지 않는다."""
    found = history.get(kind.value)
    if found is None:
        return None
    title, site, occurred_on = found
    return DogHistoryBriefOut(occurred_on=occurred_on, title=title, site=site)


def load(db: Session, dog_ids: Sequence[uuid.UUID], *, days: int, today: date) -> dict[uuid.UUID, DogHome]:
    """반려견들의 홈 배지·변동·가장 최근 대칭 점수. 규칙은 명세 12.5 홈 배지·변동."""
    if not dog_ids:
        return {}
    since = _since(today, days)
    history = _latest_history(db, dog_ids)
    noted = _latest_important_note(db, dog_ids)
    sessions = _finished_sessions(db, dog_ids)
    scores = session_scores(
        db,
        select(MeasureSession.id).where(
            MeasureSession.dog_id.in_(dog_ids), MeasureSession.status == SessionStatus.DONE.value
        ),
    )
    # 가장 최근에 끝난 회차가 기간 안인 것만 촬영·통과를 센다
    recent = {dog_id: rows[-1] for dog_id, rows in sessions.items() if rows[-1][2] >= since}
    stats = _shot_stats(
        db, [session_id for session_id, status, _ in recent.values() if status == SessionStatus.DONE.value]
    )

    homes: dict[uuid.UUID, DogHome] = {}
    for dog_id in dog_ids:
        changes: list[DogChangeOut] = []
        surgery = history.get(dog_id, {}).get(HistoryKind.SURGERY.value)
        if surgery is not None and surgery[2] >= since:
            changes.append(DogChangeOut(code=DogChangeCode.SURGERY_ADDED, on=surgery[2]))
        noted_on = noted.get(dog_id)
        if noted_on is not None and noted_on >= since:
            changes.append(DogChangeOut(code=DogChangeCode.IMPORTANT_NOTE, on=noted_on))

        scored = [
            (session_id, scores[session_id])
            for session_id, _, _ in sessions.get(dog_id, ())
            if scores.get(session_id) is not None
        ]
        if dog_id in recent:
            session_id, status, measured_on = recent[dog_id]
            invalid, used = stats.get(session_id, (0, 0))
            if status == SessionStatus.FAILED.value or used == 0 or invalid > 0:
                changes.append(DogChangeOut(code=DogChangeCode.RESHOOT_NEEDED, on=measured_on))
            if len(scored) >= 2 and scored[-1][0] == session_id:
                delta = scored[-1][1] - scored[-2][1]
                if abs(delta) >= GAIT_CHANGE_POINTS:
                    code = DogChangeCode.GAIT_BETTER if delta > 0 else DogChangeCode.GAIT_WORSE
                    changes.append(DogChangeOut(code=code, on=measured_on, delta=delta))

        changes.sort(key=lambda change: (-change.on.toordinal(), CHANGE_ORDER[change.code]))
        homes[dog_id] = DogHome(
            badges=_badges(history.get(dog_id, {}), noted_on),
            changes=changes,
            last_symmetry=scored[-1][1] if scored else None,
            last_surgery=_brief(history.get(dog_id, {}), HistoryKind.SURGERY),
            last_diagnosis=_brief(history.get(dog_id, {}), HistoryKind.DIAGNOSIS),
        )
    return homes
