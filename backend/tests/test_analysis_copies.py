"""분석 API 사본 지우기(services/analysis_copies.py, 6절·7절·15.9, S15P31A404-271).

촬영 단위로 지우고(조유진 258), 아는 작업이 답에 없을 때만 작업 단위로 한 번 더 부른다. DB를 쓰지 않는다.
호출처(자료 파기, 촬영 삭제·다시 분석, 측정 취소)는 test_purge.py·test_shots.py·test_sessions.py가 본다.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.clients.analysis import AnalysisClientError, MockAnalysisClient, SubmitInfo
from app.core.errors import AppError
from app.services.analysis_copies import Cleared, OutOfTime, ShotCopy, delete_shot_copies
from tests.test_purge import _FakeAnalysis

A, B, C = (uuid.UUID(int=n) for n in (1, 2, 3))
OLD_API = AnalysisClientError("405", retryable=False, status_code=405)


def _shot(shot_id: uuid.UUID, job_id: str | None = None, status: str | None = None, attempts: int = 1) -> ShotCopy:
    """분석 API에 보낸 적이 있는 촬영. 작업 ID가 없으면 제출 응답을 못 받고 끝난 것(FAILED)이다."""
    status = status or ("DONE" if job_id else "FAILED")
    return ShotCopy(shot_id, job_id, status, attempts, datetime(2026, 11, 10, tzinfo=UTC))


def _error(status: int | None) -> AnalysisClientError:
    return AnalysisClientError("거절", status_code=status)


def test_every_job_of_the_shot_goes_and_a_known_job_in_the_answer_is_not_called_again() -> None:
    fake = _FakeAnalysis()
    fake.shot_jobs = {A: ["job-a", "lost-a"], B: ["lost-b"]}
    fake.hook = lambda job_id: pytest.fail(f"작업 단위로 또 불렀다: {job_id}")
    assert delete_shot_copies(fake, [_shot(A, "job-a"), _shot(B), _shot(C)]) == {"job-a", "lost-a", "lost-b"}
    # 작업 ID가 없는 촬영도, 지울 것이 없는 촬영도 부른다. 작업 ID가 없는 촬영이 먼저다
    assert fake.shot_calls == [B, C, A]


def test_a_known_job_missing_from_the_answer_is_deleted_by_its_id() -> None:
    # 촬영 ID 없이 적힌 작업이거나 이미 없는 작업이다. 뒤쪽이면 404라 성공이고, 어느 쪽이든 지운 것으로 센다
    fake = _FakeAnalysis()
    fake.shot_jobs = {A: ["lost-a"]}
    assert delete_shot_copies(fake, [_shot(A, "job-a")]) == {"lost-a", "job-a"}
    assert fake.deleted == ["lost-a", "job-a"]


def test_a_shot_the_worker_never_took_is_not_asked_about() -> None:
    """UPLOADED이고 작업 ID가 없으면 분석 API에 보낸 적이 없다. 분석 API가 꺼져 있어도 지울 수 있어야 한다."""
    waiting = ShotCopy(A, None, "UPLOADED", 0, None)
    assert delete_shot_copies(None, [waiting]) == set()  # 클라이언트도 필요 없다
    fake = _FakeAnalysis()
    fake.shot_error = _error(None)
    assert delete_shot_copies(fake, [waiting]) == set() and fake.shot_calls == []
    # 가져간 뒤에는(SUBMITTED부터) 부른다. 부르는 쪽이 진행 중 촬영을 먼저 거르지만, 여기서 건너뛰지는 않는다
    with pytest.raises(AppError):
        delete_shot_copies(fake, [replace(waiting, status="FAILED", attempt_count=3)])


def test_nothing_to_do_needs_no_client_but_sent_shots_do() -> None:
    assert delete_shot_copies(None, []) == set()
    with pytest.raises(ValueError, match="분석 클라이언트"):
        delete_shot_copies(None, [_shot(A)])


def test_an_unknown_job_still_running_refuses_before_other_copies_are_deleted() -> None:
    """작업 ID가 없는 촬영을 먼저 부른다. 모르는 작업이 돌고 있어 409면 다른 촬영의 사본은 그대로다."""
    fake = _FakeAnalysis()
    fake.shot_fail[B] = _error(409)
    with pytest.raises(AppError) as caught:
        delete_shot_copies(fake, [_shot(A, "job-a"), _shot(B)])
    assert caught.value.code == "SHOT_IN_PROGRESS"
    assert fake.shot_calls == [B] and fake.deleted == []


def test_an_old_analysis_api_gets_the_known_jobs_only_and_is_asked_once() -> None:
    fake = _FakeAnalysis()
    fake.shot_error = OLD_API
    assert delete_shot_copies(fake, [_shot(A, "job-a"), _shot(B), _shot(C, "job-c")]) == {"job-a", "job-c"}
    assert fake.shot_calls == [B]  # 405를 한 번 받으면 남은 촬영은 촬영 단위로 부르지 않는다
    assert fake.deleted == ["job-a", "job-c"]


def test_an_old_analysis_api_that_refuses_the_known_job_still_stops() -> None:
    fake = _FakeAnalysis()
    fake.shot_error = OLD_API
    fake.fail["job-a"] = _error(409)
    with pytest.raises(AppError) as caught:
        delete_shot_copies(fake, [_shot(A, "job-a")])
    assert caught.value.code == "SHOT_IN_PROGRESS"


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (409, "SHOT_IN_PROGRESS"),
        (500, "ANALYSIS_UNAVAILABLE"),
        (401, "ANALYSIS_UNAVAILABLE"),
        (None, "ANALYSIS_UNAVAILABLE"),
    ],
)
@pytest.mark.parametrize("where", ["shot", "job"])
def test_a_refusal_stops_at_the_first_failure(status: int | None, code: str, where: str) -> None:
    fake = _FakeAnalysis()
    if where == "shot":
        fake.shot_fail[B] = _error(status)
    else:
        fake.fail["job-b"] = _error(status)
    with pytest.raises(AppError) as caught:
        delete_shot_copies(fake, [_shot(A, "job-a"), _shot(B, "job-b"), _shot(C, "job-c")])
    assert caught.value.code == code
    assert fake.deleted == ["job-a"] and C not in fake.shot_calls  # 뒤의 촬영은 부르지 않는다


def test_a_passed_deadline_stops_before_the_next_call() -> None:
    fake = _FakeAnalysis()
    with pytest.raises(OutOfTime):
        delete_shot_copies(fake, [_shot(A, "job-a")], deadline=time.monotonic() - 1)
    assert fake.shot_calls == [] and fake.deleted == []
    assert delete_shot_copies(fake, [_shot(A, "job-a")], deadline=time.monotonic() + 60) == {"job-a"}


def test_a_resumed_sweep_does_not_ask_again_about_shots_it_finished() -> None:
    """워커의 자동 파기가 시간 상한에 닿았다가 이어서 할 때. 끝낸 촬영을 다시 부르면 큰 기관은 끝나지 않는다."""
    fake = _FakeAnalysis()
    fake.shot_jobs = {A: ["job-a", "lost-a"]}
    shots = [_shot(A, "job-a"), _shot(B, "job-b")]
    cleared: Cleared = {}
    fake.fail["job-b"] = _error(None)  # 첫 차례는 두 번째 촬영에서 멈춘다
    with pytest.raises(AppError):
        delete_shot_copies(fake, shots, cleared=cleared)
    assert list(cleared) == [shots[0]]

    fake.fail.clear()
    fake.shot_calls.clear()
    assert delete_shot_copies(fake, shots, cleared=cleared) == {"job-a", "lost-a", "job-b"}  # 앞에서 지운 것도 센다
    assert fake.shot_calls == [B]

    # 그사이 워커가 그 촬영을 다시 보냈으면(값이 달라졌으면) 끝낸 것으로 치지 않는다
    fake.shot_calls.clear()
    again = replace(shots[0], attempt_count=2)
    delete_shot_copies(fake, [again], cleared=cleared)
    assert fake.shot_calls == [A]


def test_a_sweep_against_an_old_analysis_api_remembers_nothing() -> None:
    # 작업 단위로만 지운 촬영에는 모르는 작업이 남아 있을 수 있다. 분석 API가 새 판이 된 뒤 다시 불러야 한다
    fake = _FakeAnalysis()
    fake.shot_error = OLD_API
    cleared: Cleared = {}
    delete_shot_copies(fake, [_shot(A, "job-a")], cleared=cleared)
    assert cleared == {}


def test_mock_mode_still_refuses_a_job_it_did_not_make(tmp_path: Path) -> None:
    """API 프로세스가 설정이 빠져 mock으로 떠 있을 때, 실제 작업의 사본을 지운 것으로 치고 행을 지우면 안 된다(6절)."""
    mock = MockAnalysisClient(0)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0")
    own = mock.submit(video, SubmitInfo(shot_id=A, size_class="MEDIUM"))
    assert delete_shot_copies(mock, [_shot(A, own), _shot(B)]) == {own}
    with pytest.raises(AppError) as caught:
        delete_shot_copies(mock, [_shot(A, "3f2a9c1e5b7d4e8a9c217d4e5f6a8b90")])
    assert caught.value.code == "ANALYSIS_UNAVAILABLE"
