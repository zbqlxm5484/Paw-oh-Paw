"""분석 API 사본 지우기(6절, 7절 보관과 파기, 12.4 잠금, 15.6, 15.9, S15P31A404-199·271).

분석 API는 작업마다 영상·결과·관절점 사본을 들고 있다. 팀 서비스가 촬영 행을 지우거나 job_id를 비우면 그 사본을
다시 찾을 수 없으므로, 그 전에 여기서 지운다. 부르는 곳은 자료 파기(services/purge.py), 촬영 삭제·다시 분석
(services/shots.py), 측정 취소(services/sessions.py)다.

- 촬영 단위로 지운다(v1.45, 조유진 258의 DELETE /analyses?shot_id=). 분석 API는 제출 때 받은 촬영 ID를 작업마다
  적어 두므로, 팀 서비스가 작업 ID를 모르는 작업도 지워진다. 그런 작업은 제출 응답을 못 받고 다시 보냈을 때,
  제출 직후 워커가 죽었을 때 생긴다.
- 팀 서비스가 아는 작업(shot.job_id)이 분석 API의 답에 없으면 작업 단위(DELETE /analyses/{id})로 한 번 더 부른다.
  이미 없는 작업이면 404라 성공이다. 촬영 ID 없이 적힌 작업을 놓치지 않으려는 것이고, mock 모드에서 실제 작업을
  지운 것으로 치지 않게 막는 검사(MockAnalysisClient.delete)도 이 호출에 걸린다.
- 분석 API가 옛 판이라 촬영 단위 지우기가 없으면(405) 아는 작업만 작업 단위로 지운다. 그동안은 모르는 작업이 남는다.
- 분석 API는 HTTP라 느릴 수 있다. 부르는 쪽은 행을 잠그기 전에 부르고, 잠근 뒤에는 그사이 달라진 촬영만 다시
  부른다(12.4 잠금, 199 리뷰 박규원). 잠금을 쥔 채 오래 기다리면 워커의 주 반복이 같은 회차 행에서 멈추기 때문이다.
- 처음 실패한 곳에서 멈춘다. 지운 작업은 다시 부르면 빈 목록(작업 단위는 404)이라 성공이므로 이어서 끝난다.
- 분석 API가 아직 분석 중이라고 답하면(409 JOB_IN_PROGRESS) 409 SHOT_IN_PROGRESS, 그 밖의 실패는 503
  ANALYSIS_UNAVAILABLE이다. 팀 서비스가 시간 초과로 이미 FAILED로 둔 촬영도 분석 API에서는 아직 돌고 있을 수 있어,
  그 경우는 로그에 따로 적는다(199 리뷰 조유진). 팀 서비스가 모르는 작업이 아직 돌고 있을 때도 여기다.
- deadline은 워커의 자동 파기만 넘긴다(time.monotonic() 기준). 넘기면 OutOfTime을 내고, 남은 것은 다음 차례에 한다.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Sequence

from app.clients.analysis import AnalysisClient, AnalysisClientError
from app.core.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)

# (촬영 ID, 팀 서비스가 아는 작업 ID). 제출한 적이 없거나 작업 ID를 못 받은 촬영은 None이다
ShotJob = tuple[uuid.UUID, str | None]


class OutOfTime(Exception):
    """워커의 자동 파기가 시간 상한(WORKER_SWEEP_MAX_SEC)에 닿았다. 오류가 아니라 다음 차례로 미룬다는 뜻이다."""


def _delete_one(analysis: AnalysisClient, shot_id: uuid.UUID, job_id: str | None) -> set[str]:
    """촬영 하나의 사본을 지우고, 지웠거나 이미 없던 작업 ID를 돌려준다."""
    try:
        handled = set(analysis.delete_shot(shot_id))
    except AnalysisClientError as error:
        if not error.shot_delete_missing:
            raise
        # 분석 API가 아직 옛 판이다. 팀 서비스가 모르는 작업은 남는다
        logger.warning("analysis API has no shot-level delete (405); deleting the known job only shot=%s", shot_id)
        handled = set()
    if job_id and job_id not in handled:
        analysis.delete(job_id)
        handled.add(job_id)
    return handled


def delete_shot_copies(
    analysis: AnalysisClient | None, shots: Sequence[ShotJob], *, deadline: float | None = None
) -> set[str]:
    """촬영마다 분석 API 사본을 지우고, 지운 작업 ID를 돌려준다. 아는 작업이 이미 없던 것도 넣는다."""
    jobs: set[str] = set()
    if not shots:
        return jobs
    if analysis is None:
        raise ValueError("촬영이 있는 파기에는 분석 클라이언트가 필요합니다")
    for done, (shot_id, job_id) in enumerate(shots):
        if deadline is not None and time.monotonic() >= deadline:
            logger.info("analysis copy deletion paused at the time limit done=%d/%d", done, len(shots))
            raise OutOfTime
        try:
            jobs |= _delete_one(analysis, shot_id, job_id)
        except AnalysisClientError as error:
            if error.job_in_progress:
                # 팀 서비스의 촬영은 FAILED(ANALYSIS_TIMEOUT)인데 분석 API에서는 아직 도는 경우, 팀 서비스가 모르는
                # 작업(제출 응답을 못 받은 것)이 아직 도는 경우가 여기다
                logger.warning(
                    "analysis delete refused: the analysis API is still processing a job (JOB_IN_PROGRESS) "
                    "shot=%s done=%d/%d",
                    shot_id,
                    done,
                    len(shots),
                )
                raise AppError(ErrorCode.SHOT_IN_PROGRESS) from None
            logger.warning(
                "analysis delete failed status=%s shot=%s done=%d/%d", error.status_code, shot_id, done, len(shots)
            )
            raise AppError(ErrorCode.ANALYSIS_UNAVAILABLE) from None
    return jobs
