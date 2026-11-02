"""환경 변수 읽기 (명세 16절).

코드는 os.environ을 직접 읽지 않고 이 파일의 설정 클래스만 쓴다.
- DbSettings: DB 접속만. Alembic과 scripts/seed.py는 이것만 읽어서, JWT 비밀키 없이도 테이블을 만들 수 있다.
- Settings: 16절 표의 모든 변수. API 서버와 워커가 쓴다.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# 16절 "상수로 두는 값": 세부명세서가 정한 값이라 환경 변수가 아니라 코드 상수로 둔다.
MIN_SPEC_WIDTH = 640
MIN_SPEC_HEIGHT = 360
MIN_SPEC_FPS = 30
MIN_SPEC_BITRATE_KBPS = 4000
ALLOWED_CODECS = ("h264", "hevc")
ASPECT_16_9_TOLERANCE = 0.02

SECRET_MIN_LENGTH = 32

# env_ignore_empty: .env에 "S3_BUCKET=" 처럼 값을 비워 두면 적지 않은 것으로 보고 기본값을 쓴다.
_ENV = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True)


class DbSettings(BaseSettings):
    """DB 접속 값. 예: postgresql+pg8000://creamoff:비밀번호@localhost:5432/creamoff"""

    model_config = _ENV

    DATABASE_URL: SecretStr
    TEST_DATABASE_URL: SecretStr | None = None

    @field_validator("DATABASE_URL")
    @classmethod
    def postgres_url(cls, value: SecretStr) -> SecretStr:
        url = value.get_secret_value().strip()
        if not url:
            raise ValueError("값이 비어 있습니다")
        if not url.startswith("postgresql+pg8000://"):
            raise ValueError("postgresql+pg8000://로 시작해야 합니다(11.1)")
        return value


class Settings(DbSettings):
    """16절 표의 모든 변수. 이름과 기본값은 표와 같다."""

    JWT_SECRET: SecretStr
    JWT_EXPIRE_HOURS: int = 12
    FILE_URL_SECRET: SecretStr
    FILE_URL_TTL_SEC: int = 300
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    APP_TIMEZONE: str = "Asia/Seoul"

    STORAGE_ROOT: str = "/data/files"
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    S3_BUCKET: str | None = None
    S3_REGION: str = "ap-northeast-2"
    S3_PREFIX: str = ""
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: SecretStr | None = None

    UPLOAD_TMP_DIR: str = "/data/tmp"
    UPLOAD_MAX_MB: int = 100
    VIDEO_MIN_SEC: float = 1
    VIDEO_MAX_SEC: float = 30
    FFPROBE_PATH: str = "ffprobe"
    FFMPEG_PATH: str = "ffmpeg"

    ANALYSIS_API_MODE: Literal["mock", "http"] = "mock"
    ANALYSIS_API_BASE_URL: str | None = None
    ANALYSIS_API_KEY: SecretStr = SecretStr("")
    ANALYSIS_HTTP_TIMEOUT_SEC: float = 30
    ANALYSIS_TIMEOUT_SEC: float = 600
    ANALYSIS_SUBMIT_MAX_ATTEMPTS: int = 3
    MOCK_ANALYSIS_DELAY_SEC: float = 5

    WORKER_POLL_INTERVAL_SEC: float = 2
    # 16절: 둘 다 1 이상. 0이면 워커가 오류 없이 아무것도 가져가지 않으므로 시작 자체를 막는다
    WORKER_MAX_IN_FLIGHT: int = Field(16, ge=1)
    WORKER_MAX_IN_FLIGHT_PER_INSTITUTION: int = Field(4, ge=1)
    # 결과 영상 프로세스 풀의 크기(12.4). 0이면 결과 영상이 영영 PENDING이므로 같은 이유로 시작을 막는다
    WORKER_RENDER_CONCURRENCY: int = Field(1, ge=1)

    RECOMMENDED_PASSES: int = 8
    SIZE_SMALL_MAX_KG: float = 10
    SIZE_MEDIUM_MAX_KG: float = 25
    BREEDS_FILE: str = "config/breeds.yaml"
    TOLERANCE_FILE: str = "config/tolerance.yaml"
    MESSAGES_FILE: str = "messages/ko.yaml"
    LOG_LEVEL: str = "INFO"
    METRICS_ENABLED: bool = False
    # 16절: /docs·/redoc·/openapi.json 시험 화면. 개발 환경에서만 true. 기업에 주는 공식 명세는 docs/openapi.yaml 하나다
    API_DOCS_ENABLED: bool = False
    # 11.6 인증 캐시: 담당자 스냅샷을 프로세스 메모리에 두는 시간(초). 0이면 요청마다 DB를 읽는다(테스트)
    AUTH_CACHE_TTL_SEC: int = Field(60, ge=0)
    # 13.6: 디바이스 코드 하나의 계정 상한으로 관리자가 줄 수 있는 최댓값
    DEVICE_CODE_MAX_ACCOUNTS: int = Field(10, ge=1)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        # 16절: 쉼표로 여러 개를 받는다. pydantic-settings는 list를 JSON으로 읽으므로 직접 나눈다.
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("CORS_ORIGINS")
    @classmethod
    def no_wildcard(cls, value: list[str]) -> list[str]:
        if "*" in value:
            raise ValueError("CORS_ORIGINS에 *는 쓸 수 없습니다")
        return value

    @field_validator("JWT_SECRET", "FILE_URL_SECRET")
    @classmethod
    def long_enough(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < SECRET_MIN_LENGTH:
            raise ValueError(f"{SECRET_MIN_LENGTH}자 이상이어야 합니다")
        return value

    @model_validator(mode="after")
    def cross_checks(self) -> "Settings":
        if self.JWT_SECRET.get_secret_value() == self.FILE_URL_SECRET.get_secret_value():
            raise ValueError("FILE_URL_SECRET은 JWT_SECRET과 달라야 합니다")
        if self.STORAGE_BACKEND == "s3" and not self.S3_BUCKET:
            raise ValueError("STORAGE_BACKEND=s3이면 S3_BUCKET이 필요합니다")
        if self.ANALYSIS_API_MODE == "http" and not self.ANALYSIS_API_BASE_URL:
            raise ValueError("ANALYSIS_API_MODE=http이면 ANALYSIS_API_BASE_URL이 필요합니다")
        return self


class SettingsError(RuntimeError):
    """필수 환경 변수가 비었거나 잘못되었을 때. 메시지에 문제 변수 이름이 들어간다(16절)."""


def _describe(error: ValidationError) -> str:
    lines = ["환경 변수 설정이 잘못되어 시작할 수 없습니다:"]
    for item in error.errors(include_input=False, include_url=False):
        name = ".".join(str(part) for part in item["loc"]) or "(설정 전체)"
        message = "값이 없습니다(.env에 적으세요)" if item["type"] == "missing" else item["msg"]
        lines.append(f"  - {name}: {message}")
    return "\n".join(lines)


@lru_cache
def get_db_settings() -> DbSettings:
    try:
        return DbSettings()  # type: ignore[call-arg]
    except ValidationError as error:
        raise SettingsError(_describe(error)) from None


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as error:
        raise SettingsError(_describe(error)) from None
