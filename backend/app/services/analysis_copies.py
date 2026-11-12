"""분석 API 사본 지우기(6절, 7절 보관과 파기, 12.4 잠금, 15.6, 15.9, S15P31A404-199·271).

분석 API는 작업마다 영상·결과·관절점 사본을 들고 있다. 팀 서비스가 촬영 행을 지우거나 job_id를 비우면 그 사본을
다시 찾을 수 없으므로, 그 전에 여기서 지운다. 부르는 곳은 자료 파기(services/purge.py), 촬영 삭제·다시 분석
(services/shots.py), 측정 취소(services/sessions.py)다.

- 촬영 단위로 지운다(v1.46, 조유진 258의 DELETE /analyses?shot_id=). 분석 API는 제출 때 받은 촬영 ID를 작업마다
  적어 두므로, 팀 서비스가 작업 ID를 모르는 작업도 지워진다. 그런 작업은 제출 응답을 못 받고 다시 보냈을 때,
  제출 직후 워커가 죽었을 때 생긴다.
- 팀 서비스가 아는 작업(shot.job_id)이 분석 API의 답에 없으면 작업 단위(DELETE /analyses/{id})로 한 번 더 부른다.
  이미 없는 작업이면 404라 성공이다. 촬영 ID 없이 적힌 작업을 놓치지 않으려는 것이고, mock 모드에서 실제 작업을
  지운 것으로 치지 않게 막는 검사(MockAnalysisClient.delete)도 이 호출에 걸린다.
- 워커가 아직 가져가지 않은 촬영(UPLOADED, job_id 없음)은 부르지 않는다. 분석 API에 보낸 적이 없어 작업이 없다
  (다시 분석은 사본을 지운 뒤에 UPLOADED로 돌린다). 분석 API가 꺼져 있어도 그런 촬영은 지우고 취소할 수 있다.
- 작업 ID가 없는 촬영을 먼저 부른다. 팀 서비스가 모르는 작업이 아직 돌고 있으면 409인데, 그 답을 다른 촬영의
  사본을 지우기 전에 받으려는 것이다.
- 분석 API가 옛 판이라 촬영 단위 지우기가 없으면(405) 그 호출의 남은 촬영은 아는 작업만 작업 단위로 지운다.
  그동안은 모르는 작업이 남는다.
- 분석 API는 HTTP라 느릴 수 있다. 부르는 쪽은 행을 잠그기 전에 부르고, 잠근 뒤에는 그사이 달라진 촬영만 다시
  부른다(12.4 잠금, 199 리뷰 박규원). 잠금을 쥔 채 오래 기다리면 워커의 주 반복이 같은 회차 행에서 멈추기 때문이다.
  달라졌는지는 ShotCopy 전체로 본다. 워커가 촬영을 가져가면 submitted_at이, 제출에 실패하면 attempt_count가,
  성공하면 job_id가 바뀌므로, 값이 그대로면 그사이 새 작업이 생기지 않았다.
- 처음 실패한 곳에서 멈춘다. 지운 작업은 다시 부르면 빈 목록(작업 단위는 404)이라 성공이므로 이어서 끝난다.
- 분석 API가 아직 분석 중이라고 답하면(409 JOB_IN_PROGRESS) 409 SHOT_IN_PROGRESS, 그 밖의 실패는 503
  ANALYSIS_UNAVAILABLE이다. 팀 서비스가 시간 초과로 이미 FAILED로 둔 촬영도 분석 API에서는 아직 돌고 있을 수 있어,
  그 경우는 로그에 따로 적는다(199 리뷰 조유진). 팀 서비스가 모르는 작업이 아직 돌고 있을 때도 여기다.
- deadline은 워커의 자동 파기만 넘긴다(time.monotonic() 기준). 넘기면 OutOfTime을 내고, 남은 것은 다음 차례에 한다.
  cleared도 워커의 자동 파기만 넘긴다. 끝낸 촬영과 그때 지운 작업을 적어 두어, 다음 차례에 그 촬영을 다시 부르지
  않는다. 촬영 단위 지우기는 분석 API의 작업을 모두 훑으므로, 적어 두지 않으면 촬영이 많은 기관은 차례마다 앞에서
  끝낸 촬영을 다시 훑다가 시간 상한에 닿아 끝나지 않는다.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from app.clients.analysis import AnalysisClient, AnalysisClientError
from app.core.errors import AppError, ErrorCode
from app.models import Shot
from app.models.enums import ShotStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShotCopy:
    """사본을 지우려고 읽은 촬영 한 건. 워커가 이 촬영을 가져가거나 보내면 값이 하나는 달라진다(모듈 설명)."""

    shot_id: uuid.UUID
    job_id: str | None
    status: str
    attempt_count: int
    submitted_at: datetime | None

    @classmethod
    def of(cls, shot: Shot) -> ShotCopy:
        return cls(shot.id, shot.job_id or None, shot.status, shot.attempt_count, shot.submitted_at)

    @property
    def never_sent(self) -> bool:
        """워커가 아직 가져가지 않았다. 분석 API에 작업이 없다."""
        return self.status == ShotStatus.UPLOADED and self.job_id is None


# 끝낸 촬영 → 그때 지운 작업 ID. 워커가 자동 파기를 이어서 할 때 쓴다(모듈 설명)
Cleared = dict[ShotCopy, frozenset[str]]


class OutOfTime(Exception):
    """워커의 자동 파기가 시간 상한(WORKER_SWEEP_MAX_SEC)에 닿았다. 오류가 아니라 다음 차례로 미룬다는 뜻이다."""


def read_shot_copies(db: Session, *where: ColumnElement[bool]) -> list[ShotCopy]:
    """조건에 맞는 촬영을 ShotCopy로 읽는다. 잠그지 않는다."""
    query = (
        select(Shot.id, Shot.job_id, Shot.status, Shot.attempt_count, Shot.submitted_at)
        .where(*where)
        .order_by(Shot.created_at, Shot.id)
    )
    return [ShotCopy(shot_id, job_id or None, *rest) for shot_id, job_id, *rest in db.execute(query)]


def delete_shot_copies(
    analysis: AnalysisClient | None,
    shots: Sequence[ShotCopy],
    *,
    deadline: float | None = None,
    cleared: Cleared | None = None,
) -> set[str]:
    """촬영마다 분석 API 사본을 지우고, 지운 작업 ID를 돌려준다. 아는 작업이 이미 없던 것도 넣는다."""
    jobs: set[str] = set()
    targets = sorted((shot for shot in shots if not shot.never_sent), key=lambda shot: shot.job_id is not None)
    if not targets:
        return jobs
    if analysis is None:
        raise ValueError("분석 API에 보낸 촬영이 있는 파기에는 분석 클라이언트가 필요합니다")
    by_shot = True  # 405를 받으면 이 호출의 남은 촬영은 작업 단위로만 지운다
    for done, shot in enumerate(targets):
        if cleared is not None and shot in cleared:
            jobs |= cleared[shot]
            continue
        if deadline is not None and time.monotonic() >= deadline:
            logger.info("analysis copy deletion paused at the time limit done=%d/%d", done, len(targets))
            raise OutOfTime
        handled: set[str] = set()
        try:
            if by_shot:
                try:
                    handled = set(analysis.delete_shot(shot.shot_id))
                except AnalysisClientError as error:
                    if not error.shot_delete_missing:
                        raise
                    by_shot = False
                    # 분석 API가 아직 옛 판이다. 팀 서비스가 모르는 작업은 남는다
                    logger.warning("analysis API has no shot-level delete (405); deleting known jobs by id instead")
            if shot.job_id and shot.job_id not in handled:
                analysis.delete(shot.job_id)
                handled.add(shot.job_id)
        except AnalysisClientError as error:
            if error.job_in_progress:
                # 팀 서비스의 촬영은 FAILED(ANALYSIS_TIMEOUT)인데 분석 API에서는 아직 도는 경우, 팀 서비스가 모르는
                # 작업(제출 응답을 못 받은 것)이 아직 도는 경우가 여기다
                logger.warning(
                    "analysis delete refused: the analysis API is still processing a job (JOB_IN_PROGRESS) "
                    "shot=%s done=%d/%d",
                    shot.shot_id,
                    done,
                    len(targets),
                )
                raise AppError(ErrorCode.SHOT_IN_PROGRESS) from None
            logger.warning(
                "analysis delete failed status=%s shot=%s done=%d/%d",
                error.status_code,
                shot.shot_id,
                done,
                len(targets),
            )
            raise AppError(ErrorCode.ANALYSIS_UNAVAILABLE) from None
        jobs |= handled
        if cleared is not None and by_shot:  # 작업 단위로만 지운 촬영은 끝낸 것으로 적지 않는다(모르는 작업이 남는다)
            cleared[shot] = frozenset(handled)
    return jobs
