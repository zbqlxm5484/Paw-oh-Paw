"""계약이 끝난 기관의 자동 파기(7절, 12.5, S15P31A404-199).

계약 종료일에서 CONTRACT_RETENTION_DAYS(90일)가 지나면 워커가 그 기관의 측정 자료(반려견과 그 아래 전부, 휴지통
포함)와 가입 계정(CLIENT)을 지운다. 기관과 디바이스 코드는 남긴다. 계약을 다시 맺으면 같은 코드로 새로 가입한다.
자료 파기(services/purge.py)의 INSTITUTION을 include_accounts로 불러 순서·오류·purge_log가 같다.

대상은 `contract_ends_at < 오늘 − 90일`이다. 종료일이 오늘 − 90일인 기관은 다음 날부터 대상이다(13.6의 입력 규칙이
오늘 − 90일까지 받는 것과 맞물린다).
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import date, timedelta

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClient
from app.core.dates import CONTRACT_RETENTION_DAYS, today_local
from app.core.errors import AppError, ErrorCode
from app.models import Dog, Institution, Staff
from app.models.enums import PurgeScope, StaffRole
from app.services.analysis_copies import OutOfTime
from app.services.purge import SweepResult, purge
from app.storage.base import StorageService

logger = logging.getLogger(__name__)

# 자동 파기가 한 번에 보는 기관 수. 남은 것은 다음 차례에 본다
SWEEP_BATCH = 5


def _cutoff(today: date | None) -> date:
    return (today or today_local()) - timedelta(days=CONTRACT_RETENTION_DAYS)


def due_institution_ids(db: Session, *, today: date | None = None, limit: int | None = None) -> list[uuid.UUID]:
    """자동 파기 대상 기관: 계약이 끝난 지 90일이 지났고 지울 것(반려견 또는 가입 계정)이 남은 기관. 오래된 순서."""
    has_dog = exists().where(Dog.institution_id == Institution.id)
    has_account = exists().where(Staff.institution_id == Institution.id, Staff.role == StaffRole.CLIENT.value)
    query = (
        select(Institution.id)
        .where(
            Institution.contract_ends_at.is_not(None),
            Institution.contract_ends_at < _cutoff(today),
            or_(has_dog, has_account),
        )
        .order_by(Institution.contract_ends_at, Institution.id)
    )
    if limit is not None:
        query = query.limit(limit)
    return list(db.scalars(query))


def purge_expired_contracts(
    db: Session,
    storage: StorageService,
    analysis: AnalysisClient,
    *,
    today: date | None = None,
    limit: int = SWEEP_BATCH,
    deadline: float | None = None,
) -> SweepResult:
    """계약이 끝난 지 90일이 지난 기관의 자료와 가입 계정을 지운다(워커). 지운 기관 수, 못 지운 기관 수, 시간 상한에
    닿았는지를 돌려준다.

    종료일이 없는 기관(기한 없음)은 대상이 아니다. 지울 것이 남은 기관만 고르므로 다 지운 기관을 다시 보지 않고
    purge_log도 다시 남기지 않는다. 기관마다 savepoint 안에서 지우고 지울 때마다 commit해 잠금을 바로 푼다. 하나가
    실패해도 앞에서 지운 것은 남는다. 후보를 읽은 뒤 계약을 연장했을 수 있으므로, 기관 행을 잠근 뒤 종료일을 다시
    본다(연장은 그 commit을 기다린다). 그동안 그 기관의 가입·등록까지 막지 않게 FOR NO KEY UPDATE로 잠근다.
    분석 API가 응답하지 않으면 남은 기관도 같은 이유로 실패할 테니 거기서 멈춘다. deadline(time.monotonic() 기준)을
    넘기면 남은 것을 다음 차례로 미룬다.
    """
    institution_ids = due_institution_ids(db, today=today, limit=limit)
    purged = failed = 0
    for index, institution_id in enumerate(institution_ids):
        if deadline is not None and time.monotonic() >= deadline:
            return SweepResult(purged, failed, out_of_time=True)
        try:
            with db.begin_nested():
                still_due = db.scalar(
                    select(Institution.id)
                    .where(
                        Institution.id == institution_id,
                        Institution.contract_ends_at.is_not(None),
                        Institution.contract_ends_at < _cutoff(today),
                    )
                    .with_for_update(key_share=True)  # FOR NO KEY UPDATE: 종료일 수정만 기다리게 한다
                )
                if still_due is None:
                    continue  # 그사이 계약을 연장했다
                purge(
                    db,
                    storage,
                    PurgeScope.INSTITUTION,
                    analysis=analysis,
                    institution_id=institution_id,
                    dry_run=False,
                    executed_by=None,
                    include_accounts=True,
                    deadline=deadline,
                )
            db.commit()  # 기관 하나 지울 때마다 잠금을 푼다
            purged += 1
        except OutOfTime:
            return SweepResult(purged, failed, out_of_time=True)
        except AppError as error:
            failed += 1
            logger.warning("contract sweep could not purge an institution code=%s", error.code.value)
            if error.code == ErrorCode.ANALYSIS_UNAVAILABLE:
                failed += len(institution_ids) - index - 1  # 남은 것도 못 지운 것으로 센다
                break
    return SweepResult(purged, failed)
