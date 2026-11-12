"""StorageService 규약과 get_storage() (명세 11.11).

구현은 LocalStorage(서버 디스크)와 S3Storage(작업 단위 11) 두 개이고, STORAGE_BACKEND로 고른다.
Spring에 빗대면 인터페이스 하나에 구현체 둘을 설정으로 갈아 끼우는 것이다.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class StorageError(Exception):
    """저장소 설정·키가 잘못되었을 때."""


class StorageService(Protocol):
    def put_file(self, src: Path, key: str) -> int:
        """검사를 마친 임시 파일이나 워커 출력 파일을 키 위치에 넣고 바이트 수를 돌려준다. 같은 키가 있으면 덮어쓴다."""
        ...

    def write_bytes(self, key: str, data: bytes) -> None: ...

    def read_bytes(self, key: str) -> bytes: ...

    def local_copy(self, key: str) -> AbstractContextManager[Path]:
        """저장된 파일을 로컬 경로로 읽어야 할 때(결과 영상 그리기, 분석 API 제출). with 블록을 나가면 정리된다."""
        ...

    def delete(self, key: str | None) -> int:
        """파일 하나를 지우고 바이트 수를 돌려준다. 없으면 0."""
        ...

    def delete_prefix(self, prefix: str) -> tuple[int, int]:
        """접두어 아래를 모두 지우고 (파일 수, 바이트 수)를 돌려준다."""
        ...

    def stat_prefix(self, prefix: str) -> tuple[int, int]:
        """접두어 아래의 (파일 수, 바이트 수). 파기 dry_run에 쓴다."""
        ...

    def file_url(
        self, key: str, api_path: str, download_name: str | None = None, *, now: datetime | None = None
    ) -> tuple[str, datetime]:
        """화면에 줄 주소와 만료 시각(FILE_URL_TTL_SEC 뒤). now를 주면 그 시각이 기준이다(두 주소의 만료를 맞출 때)."""
        ...

    def check_writable(self) -> None:
        """/health의 저장소 검사. 실패하면 예외."""
        ...


@lru_cache
def _storage_for(backend: str, root: str) -> StorageService:
    if backend == "local":
        from app.storage.local import LocalStorage

        return LocalStorage(Path(root))
    # TODO(작업 단위 11): S3Storage(STORAGE_BACKEND=s3)
    raise StorageError(f"아직 지원하지 않는 저장소입니다: {backend}")


def get_storage() -> StorageService:
    """STORAGE_BACKEND에 따라 LocalStorage 또는 S3Storage를 한 번 만들어 재사용한다."""
    settings = get_settings()
    return _storage_for(settings.STORAGE_BACKEND, settings.STORAGE_ROOT)
