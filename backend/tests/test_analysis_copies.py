"""분석 API 사본 지우기(services/analysis_copies.py, 6절·7절·15.9, S15P31A404-271).

촬영 단위로 지우고(조유진 258), 아는 작업이 답에 없을 때만 작업 단위로 한 번 더 부른다. DB를 쓰지 않는다.
호출처(자료 파기, 촬영 삭제·다시 분석, 측정 취소)는 test_purge.py·test_shots.py·test_sessions.py가 본다.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest

from app.clients.analysis import AnalysisClientError, MockAnalysisClient, SubmitInfo
from app.core.errors import AppError
from app.services.analysis_copies import OutOfTime, delete_shot_copies
from tests.test_purge import _FakeAnalysis

A, B, C = (uuid.UUID(int=n) for n in (1, 2, 3))


def _error(status: int | None) -> AnalysisClientError:
    return AnalysisClientError("거절", status_code=status)


def test_every_job_of_the_shot_goes_and_a_known_job_in_the_answer_is_not_called_again() -> None:
    fake = _FakeAnalysis()
    fake.shot_jobs = {A: ["job-a", "lost-a"], B: ["lost-b"]}
    fake.hook = lambda job_id: pytest.fail(f"작업 단위로 또 불렀다: {job_id}")
    assert delete_shot_copies(fake, [(A, "job-a"), (B, None), (C, None)]) == {"job-a", "lost-a", "lost-b"}
    assert fake.shot_calls == [A, B, C]  # 작업 ID가 없는 촬영도, 지울 것이 없는 촬영도 부른다


def test_a_known_job_missing_from_the_answer_is_deleted_by_its_id() -> None:
    # 촬영 ID 없이 적힌 작업이거나 이미 없는 작업이다. 뒤쪽이면 404라 성공이고, 어느 쪽이든 지운 것으로 센다
    fake = _FakeAnalysis()
    fake.shot_jobs = {A: ["lost-a"]}
    assert delete_shot_copies(fake, [(A, "job-a")]) == {"lost-a", "job-a"}
    assert fake.deleted == ["lost-a", "job-a"]


def test_nothing_to_do_needs_no_client_but_shots_do() -> None:
    assert delete_shot_copies(None, []) == set()
    with pytest.raises(ValueError, match="분석 클라이언트"):
        delete_shot_copies(None, [(A, None)])


def test_an_old_analysis_api_gets_the_known_jobs_only() -> None:
    fake = _FakeAnalysis()
    fake.shot_error = AnalysisClientError("405", retryable=False, status_code=405)
    assert delete_shot_copies(fake, [(A, "job-a"), (B, None)]) == {"job-a"}
    assert fake.shot_calls == [A, B] and fake.deleted == ["job-a"]


def test_an_old_analysis_api_that_refuses_the_known_job_still_stops() -> None:
    fake = _FakeAnalysis()
    fake.shot_error = AnalysisClientError("405", retryable=False, status_code=405)
    fake.fail["job-a"] = _error(409)
    with pytest.raises(AppError) as caught:
        delete_shot_copies(fake, [(A, "job-a")])
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
        delete_shot_copies(fake, [(A, "job-a"), (B, "job-b"), (C, "job-c")])
    assert caught.value.code == code
    assert fake.deleted == ["job-a"] and C not in fake.shot_calls  # 뒤의 촬영은 부르지 않는다


def test_a_passed_deadline_stops_before_the_next_call() -> None:
    fake = _FakeAnalysis()
    with pytest.raises(OutOfTime):
        delete_shot_copies(fake, [(A, "job-a")], deadline=time.monotonic() - 1)
    assert fake.shot_calls == [] and fake.deleted == []
    assert delete_shot_copies(fake, [(A, "job-a")], deadline=time.monotonic() + 60) == {"job-a"}


def test_mock_mode_still_refuses_a_job_it_did_not_make(tmp_path: Path) -> None:
    """API 프로세스가 설정이 빠져 mock으로 떠 있을 때, 실제 작업의 사본을 지운 것으로 치고 행을 지우면 안 된다(6절)."""
    mock = MockAnalysisClient(0)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0")
    own = mock.submit(video, SubmitInfo(shot_id=A, size_class="MEDIUM"))
    assert delete_shot_copies(mock, [(A, own), (B, None)]) == {own}
    with pytest.raises(AppError) as caught:
        delete_shot_copies(mock, [(A, "3f2a9c1e5b7d4e8a9c217d4e5f6a8b90")])
    assert caught.value.code == "ANALYSIS_UNAVAILABLE"
