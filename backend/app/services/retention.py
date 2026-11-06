"""계약이 끝난 기관의 자동 파기(7절, 12.5, S15P31A404-199).

계약 종료일에서 CONTRACT_RETENTION_DAYS(90일)가 지나면 워커가 그 기관의 측정 자료(반려견과 그 아래 전부, 휴지통
포함)와 가입 계정(CLIENT)을 지운다. 기관과 디바이스 코드는 남긴다. 계약을 다시 맺으면 같은 코드로 새로 가입한다.
자료 파기(services/purge.py)의 INSTITUTION을 include_accounts로 불러 순서·오류·purge_log가 같다.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClient
from app.core.dates import CONTRACT_RETENTION_DAYS, today_local
from app.core.errors import AppError, ErrorCode
from app.models import Dog, Institution, Staff
from app.models.enums import PurgeScope, StaffRole
from app.services.purge import purge
from app.storage.base import StorageService

logger = logging.getLogger(__name__)

# 자동 파기가 한 번에 보는 기관 수. 남은 것은 다음 차례에 본다
SWEEP_BATCH = 5


def purge_expired_contracts(
    db: Session,
    storage: StorageService,
    analysis: AnalysisClient,
    *,
    today: date | None = None,
    limit: int = SWEEP_BATCH,
) -> tuple[int, int]:
    """계약이 끝난 지 90일이 지난 기관의 자료와 가입 계정을 지운다(워커). (지운 기관 수, 못 지운 기관 수).

    종료일이 없는 기관(기한 없음)은 대상이 아니다. 지울 것이 남은 기관만 고르므로 다 지운 기관을 다시 보지 않고
    purge_log도 다시 남기지 않는다. 기관마다 savepoint 안에서 지워, 하나가 실패해도 앞에서 지운 것은 남는다.
    분석 API가 응답하지 않으면 남은 기관도 같은 이유로 실패할 테니 거기서 멈춘다.
    """
    cutoff = (today or today_local()) - timedelta(days=CONTRACT_RETENTION_DAYS)
    has_dog = exists().where(Dog.institution_id == Institution.id)
    has_account = exists().where(Staff.institution_id == Institution.id, Staff.role == StaffRole.CLIENT.value)
    institution_ids = db.scalars(
        select(Institution.id)
        .where(
            Institution.contract_ends_at.is_not(None),
            Institution.contract_ends_at < cutoff,
            or_(has_dog, has_account),
        )
        .order_by(Institution.contract_ends_at, Institution.id)
        .limit(limit)
    ).all()
    purged = failed = 0
    for institution_id in institution_ids:
        try:
            with db.begin_nested():
                purge(
                    db,
                    storage,
                    PurgeScope.INSTITUTION,
                    analysis=analysis,
                    institution_id=institution_id,
                    dry_run=False,
                    executed_by=None,
                    include_accounts=True,
                )
            purged += 1
        except AppError as error:
            failed += 1
            logger.warning("contract sweep could not purge an institution code=%s", error.code.value)
            if error.code == ErrorCode.ANALYSIS_UNAVAILABLE:
                failed += len(institution_ids) - purged - failed
                break
    return purged, failed
