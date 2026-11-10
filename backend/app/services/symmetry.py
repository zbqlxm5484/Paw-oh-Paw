"""대칭 점수(12.3). 회차 하나의 좌우 균형을 0~100의 정수 하나로 줄인 값이고, 100에 가까울수록 좌우가 비슷하다.

대칭 점수 = 100 − 평균(대상 쌍의 대칭 지수). 저장하지 않고 session_metric 행에서 계산한다.
회차 결과(15.7)는 이미 읽은 행으로, 측정 이력(15.8)과 반려견 목록(15.5)은 회차 여러 개를 쿼리 한 번으로 계산한다.
두 길 모두 score_of 하나를 거치므로 값이 같다.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import SessionMetric
from app.models.enums import GaitType, Limb

# 점수에 넣는 쌍: (수치 코드, 왼쪽 다리, 오른쪽 다리). 웹 화면의 계산과 같다(통합본 9-2)
SCORE_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("rom_stifle", Limb.LH.value, Limb.RH.value),
    ("rom_hip", Limb.LH.value, Limb.RH.value),
    ("rom_elbow", Limb.LF.value, Limb.RF.value),
    ("stride_length", Limb.LH.value, Limb.RH.value),
    ("stance_ratio", Limb.LH.value, Limb.RH.value),
)
SCORE_CODES = tuple(dict.fromkeys(code for code, _, _ in SCORE_PAIRS))
# 보행 유형 하나만 쓴다. 이 순서로, 대상 수치의 행이 있는 첫 유형이다
SCORE_GAITS = (GaitType.TROT.value, GaitType.WALK.value, GaitType.OTHER.value)

Pair = tuple[Decimal | None, Decimal | None]


def score_of(pairs_by_gait: Mapping[str, Sequence[Pair]]) -> int | None:
    """보행 유형별 (왼쪽, 오른쪽) 값들 → 대칭 점수. 키가 있는 유형만 "행이 있는 유형"으로 본다.

    두 값이 다 있고 합이 0이 아닌 쌍만 평균에 넣는다. 넣을 쌍이 없으면 None이다(0점이 아니다).
    대칭 지수는 반올림하지 않은 값으로 평균하고, 점수만 정수로 반올림한다. 0보다 작아지면 0이다.
    """
    gait = next((name for name in SCORE_GAITS if name in pairs_by_gait), None)
    if gait is None:
        return None
    indexes = [
        abs(left - right) / ((left + right) / 2) * 100
        for left, right in pairs_by_gait[gait]
        if left is not None and right is not None and left + right != 0
    ]
    if not indexes:
        return None
    score = Decimal(100) - sum(indexes, Decimal(0)) / len(indexes)
    return int(max(score, Decimal(0)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def session_score(metrics: Iterable[SessionMetric]) -> int | None:
    """이미 읽은 회차 수치 행으로 계산한다(15.7 회차 결과)."""
    values: dict[tuple[str, str, str], Decimal | None] = {}
    gaits: set[str] = set()
    for row in metrics:
        if row.metric_code in SCORE_CODES:
            gaits.add(row.gait_type)
            values[(row.gait_type, row.metric_code, row.limb)] = row.value
    return score_of(
        {
            gait: [
                (values.get((gait, code, left)), values.get((gait, code, right))) for code, left, right in SCORE_PAIRS
            ]
            for gait in gaits
        }
    )


def session_scores(db: Session, session_ids: Sequence[uuid.UUID] | Select) -> dict[uuid.UUID, int | None]:
    """회차 여러 개의 대칭 점수를 쿼리 한 번으로(15.1 N+1 금지). 대상 수치의 행이 없는 회차는 결과에 없다.

    회차·보행 유형마다 한 줄로 접어(쌍마다 왼쪽·오른쪽 값을 열로) 받는다. session_ids에는 ID 목록이나 ID를 고르는
    SELECT를 넣는다.
    """
    if not isinstance(session_ids, Select) and not session_ids:
        return {}
    columns = []
    for code, left, right in SCORE_PAIRS:
        for limb in (left, right):
            columns.append(
                func.max(SessionMetric.value).filter(SessionMetric.metric_code == code, SessionMetric.limb == limb)
            )
    rows = db.execute(
        select(SessionMetric.session_id, SessionMetric.gait_type, *columns)
        .where(SessionMetric.session_id.in_(session_ids), SessionMetric.metric_code.in_(SCORE_CODES))
        .group_by(SessionMetric.session_id, SessionMetric.gait_type)
    ).all()
    by_session: dict[uuid.UUID, dict[str, list[Pair]]] = {}
    for session_id, gait_type, *values in rows:
        by_session.setdefault(session_id, {})[gait_type] = list(zip(values[0::2], values[1::2], strict=True))
    return {session_id: score_of(pairs) for session_id, pairs in by_session.items()}
