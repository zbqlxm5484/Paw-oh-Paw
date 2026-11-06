"""분석 API 사본 지우기(6절, 7절 보관과 파기, 12.4 잠금, 15.6, 15.9, S15P31A404-199).

분석 API는 작업마다 영상·결과·관절점 사본을 들고 있다. 팀 서비스가 촬영 행을 지우거나 job_id를 비우면 그 사본을
다시 찾을 수 없으므로, 그 전에 여기서 지운다. 부르는 곳은 자료 파기(services/purge.py), 촬영 삭제·다시 분석
(services/shots.py), 측정 취소(services/sessions.py)다.

- 분석 API는 HTTP라 느릴 수 있다. 부르는 쪽은 행을 잠그기 전에 부르고, 잠근 뒤에는 그사이 새로 생긴 작업만 다시
  부른다(12.4 잠금, 199 리뷰 박규원). 잠금을 쥔 채 오래 기다리면 워커의 주 반복이 같은 회차 행에서 멈추기 때문이다.
- 처음 실패한 곳에서 멈춘다. 지운 작업은 다시 부르면 404라 성공이므로 이어서 끝난다.
- 분석 API가 아직 분석 중이라고 답하면(409 JOB_IN_PROGRESS) 409 SHOT_IN_PROGRESS, 그 밖의 실패는 503
  ANALYSIS_UNAVAILABLE이다. 팀 서비스가 시간 초과로 이미 FAILED로 둔 촬영도 분석 API에서는 아직 돌고 있을 수 있어,
  그 경우는 로그에 따로 적는다(199 리뷰 조유진).
- deadline은 워커의 자동 파기만 넘긴다(time.monotonic() 기준). 넘기면 OutOfTime을 내고, 남은 것은 다음 차례에 한다.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence

from app.clients.analysis import AnalysisClient, AnalysisClientError
from app.core.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)


class OutOfTime(Exception):
    """워커의 자동 파기가 시간 상한(WORKER_SWEEP_MAX_SEC)에 닿았다. 오류가 아니라 다음 차례로 미룬다는 뜻이다."""


def delete_copies(analysis: AnalysisClient | None, job_ids: Sequence[str], *, deadline: float | None = None) -> None:
    """작업마다 분석 API 사본을 지운다. 이미 없는 작업(404·410)은 성공이다(clients/analysis.py)."""
    if not job_ids:
        return
    if analysis is None:
        raise ValueError("분석 작업이 있는 파기에는 분석 클라이언트가 필요합니다")
    for done, job_id in enumerate(job_ids):
        if deadline is not None and time.monotonic() >= deadline:
            logger.info("analysis copy deletion paused at the time limit done=%d/%d", done, len(job_ids))
            raise OutOfTime
        try:
            analysis.delete(job_id)
        except AnalysisClientError as error:
            if error.job_in_progress:
                # 팀 서비스의 촬영은 FAILED(ANALYSIS_TIMEOUT)인데 분석 API에서는 아직 도는 경우가 여기다
                logger.warning(
                    "analysis delete refused: the analysis API is still processing a job (JOB_IN_PROGRESS) done=%d/%d",
                    done,
                    len(job_ids),
                )
                raise AppError(ErrorCode.SHOT_IN_PROGRESS) from None
            logger.warning("analysis delete failed status=%s done=%d/%d", error.status_code, done, len(job_ids))
            raise AppError(ErrorCode.ANALYSIS_UNAVAILABLE) from None
