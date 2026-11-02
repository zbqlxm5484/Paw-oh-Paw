"""분석 클라이언트(명세 6절). 팀 서비스는 분석 API를 직접 부르지 않고 이 한 겹을 거친다.

- `AnalysisClient`: 워커가 쓰는 네 동작. submit(영상, 촬영 정보) → 작업 ID, get_status → 상태, get_result → 결과 JSON,
  get_keypoints → 관절점 파일 JSON.
- `HttpAnalysisClient`: 조유진의 분석 API(analysis_api/, 결과 JSON v1 docs/analysisApi/resultFormat.md)를 HTTP로 부른다.
  개발 환경과 기업 GPU 서버는 주소(ANALYSIS_API_BASE_URL)만 다르다.
- `MockAnalysisClient`: 분석 API 없이 견본 JSON(fixtures/)을 MOCK_ANALYSIS_DELAY_SEC 뒤 돌려준다.
  화면·워커·보고서를 먼저 만들고, 시연 날 분석 서버가 안 될 때의 대비다.

Spring에 빗대면 AnalysisClient는 인터페이스이고 두 클래스는 @Profile("mock"/"http")로 갈아 끼우는 구현체다.
클라이언트 두 클래스는 분석 API가 준 값을 그대로 돌려준다. 그 값(소문자 판정·보행·카메라 쪽, 사유 코드)을 우리
코드(14절)로 바꾸는 대응표는 이 모듈 끝의 map_* 함수이고(14.3), 결과를 DB에 넣는 services/analysis_results.py가
쓴다.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx

from app.core.config import Settings, get_settings
from app.core.errors import JudgeReason
from app.models.enums import CameraSide, GaitType, Validity

logger = logging.getLogger(__name__)

# 견본 JSON. 조유진의 analysis_api/samples(결과 JSON v1, 11-02)를 그대로 복사한 것이고,
# result_valid.json만 같은 형식으로 더 만들었다.
# 견본이 같은지는 tests/test_analysis_api_samples.py가 본다(S15P31A404-189).
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
MOCK_CASES = ("valid", "partial", "invalid", "failed")
JOB_ID_PREFIX = "mock"

# 13.1에서 받는 확장자 두 가지. 분석 API는 content-type이 video/로 시작해야 받는다.
VIDEO_CONTENT_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime"}

JobState = Literal["queued", "running", "done", "failed"]
JOB_STATES: tuple[JobState, ...] = ("queued", "running", "done", "failed")


# 인증 키 문제. 촬영의 잘못이 아니라 워커는 attempt_count를 올리지 않고 로그만 남긴 뒤 그 바퀴의 제출을 멈춘다(12.4)
AUTH_FAILED_STATUSES = (401, 403)
# 작업이 분석 API에 없다(재시작으로 잃었거나 보관 기간이 지남). 상태·결과 조회에서 받으면 워커는 바로 FAILED다(12.4)
JOB_GONE_STATUSES = (404, 410)


class AnalysisClientError(Exception):
    """분석 API를 부르지 못했거나(연결·시간 초과) 예상 밖 응답을 받았을 때.

    retryable이 True면 다시 보내면 될 수 있는 실패(연결 실패, 시간 초과, 5xx, 깨진 응답, 408·429)라 워커가
    attempt_count를 올리고 다음 바퀴에 다시 보낸다(12.4). False면 분석 API가 요청 자체를 거부한 것(400·413·415 같은
    4xx)이라 몇 번을 보내도 같으므로 워커는 바로 FAILED로 둔다(87 MR 리뷰 제안 A). 401·403은 요청이 아니라 설정
    문제라 거부로 보지 않고 auth_failed로 따로 알린다. status_code는 HTTP 응답일 때만 있다.
    """

    def __init__(self, message: str, *, retryable: bool = True, status_code: int | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code

    @property
    def auth_failed(self) -> bool:
        """인증 키(ANALYSIS_API_KEY)가 틀렸다. 촬영마다 다시 보내도 같고, 촬영을 실패시킬 일도 아니다."""
        return self.status_code in AUTH_FAILED_STATUSES

    @property
    def job_gone(self) -> bool:
        """상태·결과 조회에서 작업이 없다고 답했다. 기다려도 오지 않으므로 바로 끝낸다."""
        return self.status_code in JOB_GONE_STATUSES


@dataclass(frozen=True)
class SubmitInfo:
    """제출할 때 meta로 함께 보내는 촬영 정보. 분석 API는 무시해도 되고(추적용), 체급은 소형견 처리에 쓴다."""

    shot_id: uuid.UUID
    size_class: str


@dataclass(frozen=True)
class AnalysisStatus:
    """GET /analyses/{id}의 요약. state가 failed면 error_code·error_message에 분석 API의 원래 사유가 있다."""

    state: JobState
    error_code: str | None = None
    error_message: str | None = None
    model_name: str | None = None
    model_version: str | None = None


class AnalysisClient(Protocol):
    def submit(self, video: Path, info: SubmitInfo) -> str:
        """영상을 등록하고 작업 ID를 돌려준다. 못 보내면 AnalysisClientError."""
        ...

    def get_status(self, job_id: str) -> AnalysisStatus: ...

    def get_result(self, job_id: str) -> dict[str, Any]:
        """완료된 작업의 결과 JSON(받은 그대로). 아직 안 끝났으면 AnalysisClientError."""
        ...

    def get_keypoints(self, job_id: str) -> dict[str, Any]:
        """완료된 작업의 관절점 파일 JSON(프레임별 22점·각도)."""
        ...


# ---- 공통 ----


def _status_from_payload(payload: dict[str, Any]) -> AnalysisStatus:
    state = payload.get("status")
    if state not in JOB_STATES:
        raise AnalysisClientError(f"분석 API가 모르는 상태값을 보냈습니다: {state!r}")
    error = payload.get("error") or {}
    model = payload.get("model") or {}
    return AnalysisStatus(
        state=state,
        error_code=error.get("code"),
        error_message=error.get("message"),
        model_name=model.get("name"),
        model_version=model.get("version"),
    )


def load_fixture(name: str) -> dict[str, Any]:
    """fixtures/{name}.json을 새 dict로 읽는다. 부르는 쪽이 고쳐 써도 다음 호출에 영향이 없다."""
    path = FIXTURES_DIR / f"{name}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise AnalysisClientError(f"견본 파일이 없습니다: {path}") from e


# ---- Mock ----


class MockAnalysisClient:
    """견본 JSON을 delay_sec 뒤 돌려준다.

    상태를 메모리에 두지 않는다. 작업 ID 안에 경우(case)·제출 시각·촬영 ID를 넣어 두어, 워커를 껐다 켜도(17.3 BE-06)
    다른 인스턴스가 받아도 같은 답을 낸다. 시간 흐름: delay의 절반까지 queued, 그다음 running, delay가 지나면 done
    (failed 경우는 failed).
    """

    def __init__(self, delay_sec: float, case: str = "valid") -> None:
        if case not in MOCK_CASES:
            raise ValueError(f"Mock 경우는 {MOCK_CASES} 중 하나여야 합니다: {case!r}")
        self.delay_sec = max(float(delay_sec), 0.0)
        self.case = case

    def submit(self, video: Path, info: SubmitInfo) -> str:
        if not video.is_file():
            raise AnalysisClientError(f"보낼 영상 파일이 없습니다: {video}")
        submitted_ms = int(time.time() * 1000)
        return f"{JOB_ID_PREFIX}-{self.case}-{submitted_ms}-{info.shot_id}"

    @staticmethod
    def parse_job_id(job_id: str) -> tuple[str, float, uuid.UUID]:
        """(경우, 제출 시각(초), 촬영 ID). Mock이 만든 ID가 아니면 AnalysisClientError."""
        parts = job_id.split("-", 3)
        if len(parts) != 4 or parts[0] != JOB_ID_PREFIX or parts[1] not in MOCK_CASES:
            raise AnalysisClientError(f"Mock 작업 ID가 아닙니다: {job_id!r}")
        try:
            return parts[1], int(parts[2]) / 1000, uuid.UUID(parts[3])
        except ValueError as e:
            raise AnalysisClientError(f"Mock 작업 ID가 아닙니다: {job_id!r}") from e

    def _state(self, job_id: str) -> tuple[str, JobState, uuid.UUID]:
        case, submitted_at, shot_id = self.parse_job_id(job_id)
        elapsed = time.time() - submitted_at
        if elapsed < self.delay_sec / 2:
            return case, "queued", shot_id
        if elapsed < self.delay_sec:
            return case, "running", shot_id
        return case, ("failed" if case == "failed" else "done"), shot_id

    def get_status(self, job_id: str) -> AnalysisStatus:
        case, state, shot_id = self._state(job_id)
        if state == "failed":
            payload = load_fixture("status_failed")
        else:
            payload = {"status": state, "model": load_fixture(f"result_{case}")["model"]}
        payload["status"] = state
        return _status_from_payload(payload)

    def _done_case(self, job_id: str) -> tuple[str, uuid.UUID]:
        case, state, shot_id = self._state(job_id)
        if state != "done":
            # 분석 API의 409 NOT_READY에 해당한다
            raise AnalysisClientError(f"아직 분석이 끝나지 않았습니다: {job_id} ({state})")
        return case, shot_id

    def get_result(self, job_id: str) -> dict[str, Any]:
        case, shot_id = self._done_case(job_id)
        result = load_fixture(f"result_{case}")
        result["id"] = job_id
        result["shot_id"] = str(shot_id)
        return result

    def get_keypoints(self, job_id: str) -> dict[str, Any]:
        self._done_case(job_id)
        return load_fixture("keypoints")


# ---- HTTP ----


class HttpAnalysisClient:
    """조유진 분석 API. 모든 오류는 AnalysisClientError 하나로 낸다(연결 실패, 시간 초과, 4xx·5xx, 깨진 JSON).

    4xx(401·403·408·429 제외)는 retryable=False다. 요청 자체가 잘못된 것이라 다시 보내도 같기 때문이다. 401·403은
    auth_failed, 404·410은 job_gone으로 워커가 따로 다룬다.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout_sec: float = 30,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        # 인증 헤더는 X-API-Key로 확정(조유진, 87 MR 리뷰 10-26).
        # 키가 비어 있으면 헤더를 보내지 않고, 분석 API도 그때는 인증을 끈다
        headers = {"X-API-Key": api_key} if api_key else {}
        self._client = httpx.Client(base_url=base_url, headers=headers, timeout=timeout_sec, transport=transport)

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return self._client.request(method, path, **kwargs)
        except httpx.HTTPError as e:  # 연결 실패, 시간 초과, 잘못된 주소
            raise AnalysisClientError(f"분석 API 호출 실패: {method} {path}: {e.__class__.__name__}: {e}") from e

    @staticmethod
    def _json(response: httpx.Response, *, expected: int) -> dict[str, Any]:
        status = response.status_code
        if status != expected:
            # 4xx는 요청이 잘못된 것이라 다시 보내도 같다. 408(시간 초과)·429(너무 잦음)는 다시 보낼 수 있고,
            # 401·403은 요청이 아니라 키 설정 문제라 거부로 보지 않는다(auth_failed)
            rejected = 400 <= status < 500 and status not in (*AUTH_FAILED_STATUSES, 408, 429)
            raise AnalysisClientError(
                f"분석 API 응답 {status} (기대 {expected}): {_error_summary(response)}",
                retryable=not rejected,
                status_code=status,
            )
        try:
            body = response.json()
        except ValueError as e:
            raise AnalysisClientError("분석 API 응답이 JSON이 아닙니다") from e
        if not isinstance(body, dict):
            raise AnalysisClientError("분석 API 응답이 JSON 객체가 아닙니다")
        return body

    def submit(self, video: Path, info: SubmitInfo) -> str:
        content_type = VIDEO_CONTENT_TYPES.get(video.suffix.lower(), "video/mp4")
        meta = json.dumps({"shot_id": str(info.shot_id), "size_class": info.size_class})
        try:
            stream = video.open("rb")  # StorageService.local_copy가 만든 임시 복사본이다(11.11)
        except OSError as e:
            raise AnalysisClientError(f"보낼 영상 파일을 열 수 없습니다: {video}") from e
        with stream:
            response = self._request(
                "POST", "/analyses", files={"video": (video.name, stream, content_type)}, data={"meta": meta}
            )
        body = self._json(response, expected=202)
        job_id = body.get("id")
        if not isinstance(job_id, str) or not job_id:
            raise AnalysisClientError(f"분석 API가 작업 ID를 주지 않았습니다: {body!r}")
        return job_id

    def get_status(self, job_id: str) -> AnalysisStatus:
        response = self._request("GET", f"/analyses/{job_id}")
        return _status_from_payload(self._json(response, expected=200))

    def get_result(self, job_id: str) -> dict[str, Any]:
        response = self._request("GET", f"/analyses/{job_id}/result")
        return self._json(response, expected=200)

    def get_keypoints(self, job_id: str) -> dict[str, Any]:
        response = self._request("GET", f"/analyses/{job_id}/files/keypoints")
        return self._json(response, expected=200)


def _error_summary(response: httpx.Response) -> str:
    """분석 API의 {"error": {"code", "message"}}에서 코드와 문구만 뽑는다. 영상 내용은 로그에 남기지 않는다(11.8)."""
    try:
        error = response.json().get("error") or {}
    except (ValueError, AttributeError):
        return response.text[:200]
    return f"{error.get('code')}: {error.get('message')}"


# ---- 설정값으로 고르기 ----


def build_analysis_client(settings: Settings | None = None) -> AnalysisClient:
    """ANALYSIS_API_MODE가 mock이면 MockAnalysisClient, http면 HttpAnalysisClient(16절)."""
    settings = settings or get_settings()
    if settings.ANALYSIS_API_MODE == "mock":
        return MockAnalysisClient(settings.MOCK_ANALYSIS_DELAY_SEC)
    assert settings.ANALYSIS_API_BASE_URL  # config.py가 http 모드에서 비어 있으면 서버를 못 켜게 막는다
    return HttpAnalysisClient(
        settings.ANALYSIS_API_BASE_URL,
        settings.ANALYSIS_API_KEY.get_secret_value(),
        settings.ANALYSIS_HTTP_TIMEOUT_SEC,
    )


# ---- 14절 대응표 (14.3) ----
#
# 분석 API의 소문자 값을 우리 코드로 바꾼다. 클라이언트는 받은 그대로 돌려주고, 결과를 저장하는 쪽
# (services/analysis_results.py)이 이 함수들로 바꾼다. 모르는 사유 코드는 UNKNOWN_REASON으로 두고 원래 코드를 로그에
# 남긴다(17.3 BE-08).

VALIDITY_MAP = {"valid": Validity.VALID.value, "partial": Validity.PARTIAL.value, "invalid": Validity.INVALID.value}
GAIT_MAP = {
    "walk": GaitType.WALK.value,
    "trot": GaitType.TROT.value,
    "pace": GaitType.PACE.value,
    "other": GaitType.OTHER.value,
}
CAMERA_SIDE_MAP = {"left": CameraSide.LEFT.value, "right": CameraSide.RIGHT.value}
# 촬영 판정 사유가 비어 있을 때. PARTIAL의 null은 "유효 통과는 기준 수 이상인데 제외된 통과가 있다"는 뜻이라 그대로
# 두고(조유진 유효 판별 규칙 초안 4.2, MR !30), INVALID만 NO_VALID_PASS로 채운다. VALID는 사유가 없다
DEFAULT_VALIDITY_REASON = {Validity.INVALID.value: JudgeReason.NO_VALID_PASS.value}
KNOWN_REASONS = frozenset(member.value for member in JudgeReason)


def map_validity(value: Any) -> str | None:
    """valid·partial·invalid → VALID·PARTIAL·INVALID. 모르는 값이면 None(부르는 쪽이 형식 오류로 처리한다)."""
    return VALIDITY_MAP.get(value.lower()) if isinstance(value, str) else None


def map_camera_side(value: Any) -> str | None:
    """left·right → LEFT·RIGHT. 모르는 값이면 None."""
    return CAMERA_SIDE_MAP.get(value.lower()) if isinstance(value, str) else None


def map_gait(value: Any) -> str:
    """walk·trot·pace → WALK·TROT·PACE. 비어 있거나(제외된 통과) 모르는 값이면 OTHER(walk_pass.gait_type은 NOT NULL)."""
    if isinstance(value, str):
        return GAIT_MAP.get(value.lower(), GaitType.OTHER.value)
    return GaitType.OTHER.value


def map_reason(code: Any, *, shot_id: uuid.UUID, where: str) -> str:
    """14.3 사유 코드. 목록에 없으면 UNKNOWN_REASON으로 두고 원래 코드를 로그에 남긴다."""
    if isinstance(code, str) and code.upper() in KNOWN_REASONS:
        return code.upper()
    logger.warning("unknown reason code %r in %s shot=%s; stored as UNKNOWN_REASON", code, where, shot_id)
    return JudgeReason.UNKNOWN_REASON.value
