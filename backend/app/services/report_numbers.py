"""보고서 수치 대조의 기준값(8절 7번 첫 항목, 12.4 "보고서 한 건", S15P31A404-196).

워커가 자식 프로세스에서 받은 "실린 숫자 목록"(report.numbers.ListedNumber)을 맞출 기준이다. 6절 "결과 저장 원칙"대로
DB의 session_metric 값이 기준이고, 다리 비교(왼쪽·오른쪽·차이·대칭 지수)는 결과 조회와 같은 함수
(session_results.limb_compare)로 계산해 report.verify의 키로 묶는다. 좌우 계산을 여기서 다시 쓰지 않으므로 계산은
한곳이다(12.3, 10절 Q6). 측정 불가 행(value NULL)은 숫자가 아니라 기준에 들어가지 않는다.
직전 회차 비교 표의 직전 값·차이는 보고서 입력을 만들 때 쓴 직전 회차의 session_metric 값이 기준이다(272).
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SessionMetric
from app.report.verify import NumberKey, previous_reference
from app.services.session_results import limb_compare

PAIR_KINDS = ("left", "right", "diff", "symmetry_index")


def _rows(db: Session, session_id: uuid.UUID) -> list[SessionMetric]:
    return list(
        db.scalars(
            select(SessionMetric)
            .where(SessionMetric.session_id == session_id)
            .execution_options(populate_existing=True)
        )
    )


def _limb_values(rows: list[SessionMetric]) -> dict[tuple[str, str, str], float | None]:
    return {(row.gait_type, row.metric_code, row.limb): None if row.value is None else float(row.value) for row in rows}


def reference_numbers(
    db: Session, session_id: uuid.UUID, previous_id: uuid.UUID | None = None
) -> dict[NumberKey, float]:
    """회차의 session_metric 행 → 대조 기준값. 행을 DB에서 새로 읽는다(만드는 동안 바뀌었을 수 있다).

    previous_id는 보고서 입력에 넣은 직전 회차다. 주면 그 회차의 값(previous)과 두 회차의 차이(change)도 기준에 넣는다.
    그사이 직전 회차가 지워졌으면 그 기준이 없어 대조에서 걸린다(지워진 회차의 값을 실은 PDF를 내보내지 않는다).
    """
    rows = _rows(db, session_id)
    reference: dict[NumberKey, float] = {}
    by_gait: dict[str, list[SessionMetric]] = defaultdict(list)
    for row in rows:
        by_gait[row.gait_type].append(row)
        if row.value is not None:
            reference[(row.gait_type, row.metric_code, row.limb, "metric")] = float(row.value)
    for gait_type, gait_rows in by_gait.items():
        for entry in limb_compare(gait_rows):
            values = (entry.left, entry.right, entry.diff, entry.symmetry_index)
            for kind, value in zip(PAIR_KINDS, values, strict=True):
                # numbers.py와 같은 규칙: 왼쪽·오른쪽 값은 비교할 수 없어도 싣고, 차이·대칭 지수는 비교할 수 있을 때만
                if value is not None and (entry.comparable or kind in ("left", "right")):
                    reference[(gait_type, entry.metric_code, entry.pair, kind)] = value
    if previous_id is not None:
        reference.update(previous_reference(_limb_values(rows), _limb_values(_rows(db, previous_id))))
    return reference
