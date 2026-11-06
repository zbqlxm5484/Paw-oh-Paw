"""상태·종류 값 (명세 12.2, 12.5 상태·종류 값).

DB에는 PostgreSQL ENUM 타입 대신 VARCHAR(20) + CHECK 제약으로 둔다.
값 목록은 여기 한 곳에서만 정하고, 모델의 CHECK 제약도 이 목록으로 만든다.
값을 더하거나 빼면 Alembic 마이그레이션에서 그 CHECK 제약을 다시 만들어야 한다.
"""

from enum import StrEnum

from sqlalchemy import CheckConstraint


class StaffRole(StrEnum):
    """저장하는 역할(11.6). ADMIN·STAFF는 크림오프 쪽, CLIENT는 고객 기관 담당자. GUEST는 저장하지 않는다."""

    ADMIN = "ADMIN"
    STAFF = "STAFF"
    CLIENT = "CLIENT"


class EffectiveRole(StrEnum):
    """계산한 역할(11.6 effective_role). 계약이 끝난 CLIENT는 GUEST. 응답과 화면 분기에만 쓰고 DB에는 없다."""

    ADMIN = "ADMIN"
    STAFF = "STAFF"
    CLIENT = "CLIENT"
    GUEST = "GUEST"


class ContractStatus(StrEnum):
    """기관 계약 상태(11.6). 저장하지 않고 contract_ends_at과 오늘(APP_TIMEZONE)로 계산한다."""

    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"


class SizeClass(StrEnum):
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"


class Sex(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    MALE_NEUTERED = "MALE_NEUTERED"
    FEMALE_SPAYED = "FEMALE_SPAYED"


class FocusLimb(StrEnum):
    """관심 다리: 왼앞·오른앞·왼뒤·오른뒤"""

    LF = "LF"
    RF = "RF"
    LH = "LH"
    RH = "RH"


class DogStage(StrEnum):
    """반려견 단계(12.5 차트 자료): 수술 전·재활 중·종결"""

    PRE = "PRE"
    REHAB = "REHAB"
    DONE = "DONE"


class HistoryKind(StrEnum):
    """진단 이력의 종류: 진단·수술·재활"""

    DIAGNOSIS = "DIAGNOSIS"
    SURGERY = "SURGERY"
    REHAB = "REHAB"


class HistorySite(StrEnum):
    """진단 이력의 부위: 네 다리와 척추(SP)"""

    LF = "LF"
    RF = "RF"
    LH = "LH"
    RH = "RH"
    SP = "SP"


class NoteCategory(StrEnum):
    """메모·진료 기록의 분류. S·O·A·P는 진료 기록, 나머지는 메모(주의·보호자·예약·기타)다."""

    SUBJECTIVE = "S"
    OBJECTIVE = "O"
    ASSESSMENT = "A"
    PLAN = "P"
    CAUTION = "CAUTION"
    GUARDIAN = "GUARDIAN"
    BOOKING = "BOOKING"
    OTHER = "OTHER"


CHART_CATEGORIES = frozenset({"S", "O", "A", "P"})
MEMO_CATEGORIES = frozenset(member.value for member in NoteCategory) - CHART_CATEGORIES


class Limb(StrEnum):
    """회차 수치의 다리. NONE은 몸 전체 수치(walk_speed, gait_cycles)."""

    LF = "LF"
    RF = "RF"
    LH = "LH"
    RH = "RH"
    NONE = "NONE"


class CameraSide(StrEnum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class GaitType(StrEnum):
    """평보·속보·측대보·기타"""

    WALK = "WALK"
    TROT = "TROT"
    PACE = "PACE"
    OTHER = "OTHER"


class SessionStatus(StrEnum):
    MEASURING = "MEASURING"
    AGGREGATING = "AGGREGATING"
    DONE = "DONE"
    FAILED = "FAILED"


class ShotStatus(StrEnum):
    UPLOADED = "UPLOADED"
    SUBMITTED = "SUBMITTED"
    ANALYZING = "ANALYZING"
    DONE = "DONE"
    FAILED = "FAILED"


class Validity(StrEnum):
    VALID = "VALID"
    PARTIAL = "PARTIAL"
    INVALID = "INVALID"


class VideoStatus(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"


class ReportEdition(StrEnum):
    """보호자용·수의사용"""

    OWNER = "OWNER"
    VET = "VET"


class ReportStatus(StrEnum):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    DONE = "DONE"
    FAILED = "FAILED"


class DogBadgeCode(StrEnum):
    """홈 배지(12.5 홈 배지·변동). DB에 저장하지 않고 응답에만 쓴다."""

    SURGERY = "SURGERY"
    DIAGNOSIS = "DIAGNOSIS"
    IMPORTANT_NOTE = "IMPORTANT_NOTE"


class DogChangeCode(StrEnum):
    """최근 변동(12.5 홈 배지·변동). 적힌 순서가 같은 날 안의 정렬 순서다."""

    RESHOOT_NEEDED = "RESHOOT_NEEDED"
    GAIT_WORSE = "GAIT_WORSE"
    GAIT_BETTER = "GAIT_BETTER"
    SURGERY_ADDED = "SURGERY_ADDED"
    IMPORTANT_NOTE = "IMPORTANT_NOTE"


class PurgeScope(StrEnum):
    DOG = "DOG"
    INSTITUTION = "INSTITUTION"
    ALL = "ALL"


def values_in(column: str, enum_cls: type[StrEnum]) -> str:
    """CHECK 조건 문자열. 예: "status IN ('MEASURING', 'AGGREGATING', 'DONE', 'FAILED')" """
    values = ", ".join(f"'{member.value}'" for member in enum_cls)
    return f"{column} IN ({values})"


def check_in(column: str, enum_cls: type[StrEnum], name: str) -> CheckConstraint:
    """12.2 DDL과 같은 이름의 CHECK 제약을 만든다."""
    return CheckConstraint(values_in(column, enum_cls), name=name)
