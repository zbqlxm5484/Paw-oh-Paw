"""GET /api/v1/health — 서버 상태(15.9, BE-20). 인증 없음. Docker 상태 검사가 부른다.

DB 접속(SELECT 1)과 저장소 쓰기 검사(11.11 check_writable)를 한다. 하나라도 실패하면 503이고 실패한 항목이 "error"다.
"""

import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app import __version__
from app.core.db import get_engine
from app.schemas.health import HealthOut
from app.storage.base import get_storage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["운영"])


def _db_ok() -> bool:
    """DB에 붙어 SELECT 1이 되면 True. 어떤 예외든 잡아 False로 답한다(503 응답 자체가 알림이다)."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as error:
        # 예외 메시지에는 주소·값이 들어갈 수 있어 종류만 남긴다(11.8)
        logger.warning("health: db check failed (%s)", type(error).__name__)
        return False
    return True


def _storage_ok() -> bool:
    """저장소 검사에서 난 모든 예외를 잡아 error로 답한다(11.11)."""
    try:
        get_storage().check_writable()
    except Exception as error:
        logger.warning("health: storage check failed (%s)", type(error).__name__)
        return False
    return True


@router.get("/health", response_model=HealthOut, responses={503: {"model": HealthOut}})
def health(response: Response) -> HealthOut:
    db_ok = _db_ok()
    storage_ok = _storage_ok()
    if not (db_ok and storage_ok):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthOut(
        status="ok" if db_ok and storage_ok else "error",
        db="ok" if db_ok else "error",
        storage="ok" if storage_ok else "error",
        version=__version__,
    )
