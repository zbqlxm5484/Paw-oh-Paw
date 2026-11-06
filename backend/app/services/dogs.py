"""반려견 업무 규칙(12.5, 13.2, 15.5). 모든 조회는 기관 ID로 거르고 휴지통의 반려견을 뺀다(11.6, 12.5).

Spring의 @Service. 첫 인자는 DB 세션이고 flush()까지만 한다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import get_settings
from app.core.dates import today_local
from app.core.errors import AppError, ErrorCode
from app.models import Dog, DogVital, MeasureSession
from app.models.enums import SessionStatus
from app.schemas.chart import VitalOut
from app.schemas.dogs import DogCreate, DogOut, DogUpdate
from app.services import dog_home
from app.services.size_class import classify_size

# 휴지통에 넣고 이 날수가 지나면 워커가 영구 삭제한다(12.5)
TRASH_RETENTION_DAYS = 30


def in_institution(institution_id: uuid.UUID, *, trash: bool = False):
    """담당자에게 보이는 반려견의 SQL 조건: 자기 기관이고 휴지통에 없다. trash면 휴지통에 있는 것만(12.5)."""
    trashed = Dog.deleted_at.is_not(None) if trash else Dog.deleted_at.is_(None)
    return (Dog.institution_id == institution_id) & trashed


@dataclass(frozen=True)
class DogStats:
    """DogOut에 붙는 회차 요약(15.3): 회차 수, 가장 최근 측정일, 측정 중인 회차 ID."""

    session_count: int
    last_measured_on: date | None
    open_session_id: uuid.UUID | None


def classify(weight_kg: Decimal) -> str:
    """설정의 기준 체중으로 classify_size를 부른다(12.5: 체중만 본다)."""
    settings = get_settings()
    return classify_size(
        weight_kg,
        small_max_kg=Decimal(str(settings.SIZE_SMALL_MAX_KG)),
        medium_max_kg=Decimal(str(settings.SIZE_MEDIUM_MAX_KG)),
    )


def phone_last4(phone: str | None) -> str | None:
    """연락처의 숫자 중 뒤 4자리(15.3). 숫자가 4개보다 적으면 있는 만큼, 연락처가 없으면 None."""
    if phone is None:
        return None
    return "".join(char for char in phone if char.isdigit())[-4:]


def set_stage(dog: Dog, stage: str) -> bool:
    """단계를 바꾼다(12.5 차트 자료). 값이 바뀔 때만 stage_changed_on에 오늘(한국 날짜)을 적고 True를 돌려준다."""
    if dog.stage == stage:
        return False
    dog.stage = stage
    dog.stage_changed_on = today_local()
    return True


def latest_vitals(db: Session, dog_ids: list[uuid.UUID]) -> dict[uuid.UUID, VitalOut]:
    """반려견별 가장 최근 날짜의 바이탈(15.3 latest_vital). 쿼리 한 번으로 읽어 N+1을 피한다(15.1).

    반려견마다 가장 늦은 날짜를 GROUP BY로 구해 다시 붙인다. 하루 한 줄(uq_dog_vital_day)이라 반려견마다 한 행이다.
    """
    if not dog_ids:
        return {}
    latest = (
        select(DogVital.dog_id.label("dog_id"), func.max(DogVital.measured_on).label("measured_on"))
        .where(DogVital.dog_id.in_(dog_ids))
        .group_by(DogVital.dog_id)
        .subquery()
    )
    rows = db.scalars(
        select(DogVital)
        .options(joinedload(DogVital.staff))
        .join(latest, (DogVital.dog_id == latest.c.dog_id) & (DogVital.measured_on == latest.c.measured_on))
    ).all()
    return {row.dog_id: VitalOut.model_validate(row) for row in rows}


def to_dog_out(
    dog: Dog,
    stats: DogStats,
    *,
    in_list: bool = False,
    latest_vital: VitalOut | None = None,
    home: dog_home.DogHome | None = None,
) -> DogOut:
    """in_list면 보호자 연락처 전체를 빼고 뒤 4자리만 준다(15.3). home은 홈 배지·변동(없으면 빈 값)."""
    home = home or dog_home.DogHome()
    return DogOut.model_validate(dog).model_copy(
        update={
            "badges": home.badges,
            "changes": home.changes,
            "last_symmetry": home.last_symmetry,
            "owner_phone": None if in_list else dog.owner_phone,
            "owner_phone_last4": phone_last4(dog.owner_phone),
            "latest_vital": latest_vital,
            "session_count": stats.session_count,
            "last_measured_on": stats.last_measured_on,
            "open_session_id": stats.open_session_id,
            "purge_at": dog.deleted_at + timedelta(days=TRASH_RETENTION_DAYS) if dog.deleted_at else None,
        }
    )


def _stats_subquery():
    """반려견별 회차 수와 가장 최근 측정일. GROUP BY 한 번으로 세어 N+1을 피한다(15.1)."""
    return (
        select(
            MeasureSession.dog_id.label("dog_id"),
            func.count().label("session_count"),
            func.max(MeasureSession.measured_on).label("last_measured_on"),
        )
        .group_by(MeasureSession.dog_id)
        .subquery()
    )


def _open_session_subquery():
    """MEASURING 회차의 ID. 반려견마다 많아야 하나다(13.3)."""
    return (
        select(MeasureSession.id)
        .where(MeasureSession.dog_id == Dog.id, MeasureSession.status == SessionStatus.MEASURING.value)
        .order_by(MeasureSession.created_at.desc())
        .limit(1)
        .correlate(Dog)
        .scalar_subquery()
    )


def _dogs_query(institution_id: uuid.UUID, *, trash: bool = False):
    """반려견 + 회차 요약. 정렬은 15.5: 최근 측정일 내림차순(NULLS LAST, 안 잰 반려견은 뒤), 같으면 등록 시각.

    trash면 휴지통의 반려견만, 최근에 넣은 것부터다.
    """
    stats = _stats_subquery()
    order = (stats.c.last_measured_on.desc().nulls_last(), Dog.created_at.desc(), Dog.id.desc())
    if trash:
        order = (Dog.deleted_at.desc(), Dog.id.desc())
    return (
        select(
            Dog,
            func.coalesce(stats.c.session_count, 0).label("session_count"),
            stats.c.last_measured_on.label("last_measured_on"),
            _open_session_subquery().label("open_session_id"),
        )
        .outerjoin(stats, stats.c.dog_id == Dog.id)
        .where(in_institution(institution_id, trash=trash))
        .order_by(*order)
    )


def list_dogs(
    db: Session,
    institution_id: uuid.UUID,
    *,
    q: str | None,
    page: int,
    size: int,
    trash: bool = False,
    changed_within_days: int | None = None,
) -> tuple[list[DogOut], int]:
    """목록·검색(15.5). q는 이름·동물번호·보호자 이름 중 하나에 포함되면 찾고(대소문자 무시) %·_는 이스케이프한다.

    연락처로는 찾지 않는다. trash면 휴지통 목록. 항목의 보호자 연락처는 뒤 4자리만 준다.

    changed_within_days를 주면 그 기간에 변동(12.5 홈 배지·변동)이 있는 반려견만 준다. 기관의 후보를 먼저 추려
    변동을 계산하고, 변동이 있는 ID로 목록을 거른다. 휴지통 목록에서는 홈 배지·변동을 계산하지 않는다.
    """
    query = _dogs_query(institution_id, trash=trash)
    count_query = select(func.count()).select_from(Dog).where(in_institution(institution_id, trash=trash))
    today = today_local()
    days = changed_within_days or dog_home.CHANGE_DAYS
    homes: dict[uuid.UUID, dog_home.DogHome] | None = None
    if changed_within_days is not None and not trash:
        candidates = dog_home.candidate_ids(db, in_institution(institution_id), days=days, today=today)
        homes = dog_home.load(db, candidates, days=days, today=today)
        changed = Dog.id.in_([dog_id for dog_id, home in homes.items() if home.changes])
        query = query.where(changed)
        count_query = count_query.where(changed)
    if q:
        matches = or_(
            Dog.name.icontains(q, autoescape=True),
            Dog.chart_no.icontains(q, autoescape=True),
            Dog.owner_name.icontains(q, autoescape=True),
        )
        query = query.where(matches)
        count_query = count_query.where(matches)
    rows = db.execute(query.offset((page - 1) * size).limit(size)).all()
    total = db.scalar(count_query) or 0
    dog_ids = [row[0].id for row in rows]
    vitals = latest_vitals(db, dog_ids)
    if homes is None:
        homes = {} if trash else dog_home.load(db, dog_ids, days=days, today=today)
    items = [
        to_dog_out(
            dog,
            DogStats(session_count, last_measured_on, open_session_id),
            in_list=True,
            latest_vital=vitals.get(dog.id),
            home=homes.get(dog.id),
        )
        for dog, session_count, last_measured_on, open_session_id in rows
    ]
    return items, total


def get_dog(
    db: Session,
    institution_id: uuid.UUID,
    dog_id: uuid.UUID,
    *,
    include_trashed: bool = False,
    for_update: bool = False,
) -> Dog:
    """없거나 다른 기관이거나 휴지통에 있는 반려견이면 똑같이 404 NOT_FOUND(15.1).

    include_trashed는 자료 파기만 쓴다. 휴지통에 있든 없든 그 기관의 반려견이면 돌려준다.
    for_update면 반려견 행을 잠그고 잠근 뒤의 값으로 돌려준다(12.4 잠금: 휴지통에 넣기, 자료 파기).
    """
    condition = Dog.institution_id == institution_id if include_trashed else in_institution(institution_id)
    query = select(Dog).where(Dog.id == dog_id, condition)
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    dog = db.scalars(query).one_or_none()
    if dog is None:
        raise AppError(ErrorCode.NOT_FOUND)
    return dog


def get_dog_out(db: Session, institution_id: uuid.UUID, dog_id: uuid.UUID) -> DogOut:
    row = db.execute(_dogs_query(institution_id).where(Dog.id == dog_id)).one_or_none()
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND)
    dog, session_count, last_measured_on, open_session_id = row
    return to_dog_out(
        dog,
        DogStats(session_count, last_measured_on, open_session_id),
        latest_vital=latest_vitals(db, [dog.id]).get(dog.id),
        home=dog_home.load(db, [dog.id], days=dog_home.CHANGE_DAYS, today=today_local()).get(dog.id),
    )


def create_dog(db: Session, institution_id: uuid.UUID, data: DogCreate) -> Dog:
    """size_class를 보내지 않으면 체중으로 정하고, 보내면 그 값을 쓰며 size_class_manual=TRUE(15.5)."""
    manual = data.size_class is not None
    dog = Dog(
        institution_id=institution_id,
        name=data.name,
        breed=data.breed,
        weight_kg=data.weight_kg,
        size_class=data.size_class.value if data.size_class is not None else classify(data.weight_kg),
        size_class_manual=manual,
        birth_year=data.birth_year,
        sex=data.sex.value if data.sex is not None else None,
        rehab_start_date=data.rehab_start_date,
        focus_limb=data.focus_limb.value if data.focus_limb is not None else None,
        memo=data.memo,
        chart_no=data.chart_no,
        owner_name=data.owner_name,
        owner_phone=data.owner_phone,
        stage=data.stage.value,
    )
    db.add(dog)
    db.flush()
    db.refresh(dog)
    return dog


def _check_baseline(db: Session, dog: Dog, session_id: uuid.UUID) -> None:
    """기준 회차는 같은 반려견의 DONE 회차여야 한다. 아니면 400 BASELINE_INVALID(13.2)."""
    found = db.scalar(
        select(MeasureSession.id).where(
            MeasureSession.id == session_id,
            MeasureSession.dog_id == dog.id,
            MeasureSession.status == SessionStatus.DONE.value,
        )
    )
    if found is None:
        raise AppError(ErrorCode.BASELINE_INVALID)


def update_dog(db: Session, institution_id: uuid.UUID, dog_id: uuid.UUID, data: DogUpdate) -> Dog:
    """보낸 필드만 바꾼다(15.5). 체급 규칙은 12.5:
    - size_class 값을 보내면 그 값 + manual=TRUE. null을 보내면 manual=FALSE로 돌리고 저장된 체중으로 다시 분류.
    - weight_kg를 바꾸면 manual=FALSE일 때만 새 체중으로 다시 분류. breed는 체급과 상관없다.
    - weight_kg와 size_class가 함께 오면 size_class가 이긴다.
    단계(stage)는 값이 바뀔 때만 stage_changed_on을 오늘로 적는다(12.5 차트 자료).
    낙관적 잠금(12.5, BE-25): 보낸 version이 저장된 값과 다르면 409 DOG_MODIFIED이고 아무것도 바뀌지 않는다.
    읽은 뒤 flush 사이에 다른 요청이 먼저 저장해도 ORM의 WHERE version = :old가 빈손으로 끝나므로(StaleDataError)
    같은 409다.
    """
    dog = get_dog(db, institution_id, dog_id)
    if data.version != dog.version:
        raise AppError(ErrorCode.DOG_MODIFIED)
    changes = data.model_dump(exclude_unset=True)
    changes.pop("version")

    if "baseline_session_id" in changes:
        session_id = changes.pop("baseline_session_id")
        if session_id is not None:
            _check_baseline(db, dog, session_id)
        dog.baseline_session_id = session_id

    if "stage" in changes:
        set_stage(dog, changes.pop("stage").value)

    size_class = changes.pop("size_class", "unset")
    weight_changed = "weight_kg" in changes and changes["weight_kg"] != dog.weight_kg

    for field, value in changes.items():
        setattr(dog, field, value.value if hasattr(value, "value") else value)

    if size_class != "unset":
        if size_class is not None:
            dog.size_class = size_class.value if hasattr(size_class, "value") else size_class
            dog.size_class_manual = True
        else:
            dog.size_class_manual = False
            dog.size_class = classify(dog.weight_kg)
    elif weight_changed and not dog.size_class_manual:
        dog.size_class = classify(dog.weight_kg)

    try:
        db.flush()
    except StaleDataError:
        raise AppError(ErrorCode.DOG_MODIFIED) from None
    db.refresh(dog)
    return dog
