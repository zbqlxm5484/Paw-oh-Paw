"""LocalStorage: 서버 디스크(STORAGE_ROOT 아래)에 두는 저장소(11.11 local 열).

이 파일만 open()·os.replace()·shutil을 직접 쓴다. 다른 코드는 StorageService를 거친다(11.3).
"""

from __future__ import annotations

import os
import shutil
import uuid
from contextlib import AbstractContextManager, nullcontext
from datetime import datetime
from pathlib import Path

from app.core.security import make_signed_url
from app.storage.base import StorageError

HEALTH_PREFIX = ".health/"


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- 경로 ----

    def path(self, key: str) -> Path:
        """키의 실제 경로. local 파일 API(15.2의 16·21번)가 FileResponse에 넘긴다. 루트 밖으로 나가는 키는 거부한다."""
        if not key or key.startswith(("/", "\\")) or ".." in Path(key).parts:
            raise StorageError(f"잘못된 파일 키입니다: {key!r}")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise StorageError(f"저장소 밖을 가리키는 키입니다: {key!r}")
        return path

    def _prune_empty_dirs(self, directory: Path) -> None:
        """파일을 지운 뒤 빈 폴더를 루트 직전까지 지운다."""
        while directory != self.root and directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
            directory = directory.parent

    # ---- 쓰기·읽기 ----

    def put_file(self, src: Path, key: str) -> int:
        dst = self.path(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        size = src.stat().st_size
        try:
            os.replace(src, dst)  # 같은 볼륨이면 이름만 바꾼다
        except OSError:
            shutil.copyfile(src, dst)  # 다른 볼륨이면 복사한 뒤 지운다
            src.unlink()
        return size

    def write_bytes(self, key: str, data: bytes) -> None:
        dst = self.path(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        # 임시 이름은 짧게 둔다. 키가 UUID 네 단계라 Windows의 경로 길이 한도(260자)에 걸리기 쉽다.
        tmp = dst.parent / f".tmp-{uuid.uuid4().hex[:12]}"
        tmp.write_bytes(data)
        os.replace(tmp, dst)

    def read_bytes(self, key: str) -> bytes:
        return self.path(key).read_bytes()

    def local_copy(self, key: str) -> AbstractContextManager[Path]:
        return nullcontext(self.path(key))

    # ---- 지우기·세기 ----

    def delete(self, key: str | None) -> int:
        if key is None:
            return 0
        path = self.path(key)
        if not path.is_file():
            return 0
        size = path.stat().st_size
        path.unlink()
        self._prune_empty_dirs(path.parent)
        return size

    def _files_under(self, prefix: str) -> tuple[Path | None, list[Path]]:
        base = self.path(prefix.rstrip("/\\"))
        if not base.is_dir():
            return None, []
        return base, [p for p in base.rglob("*") if p.is_file()]

    def stat_prefix(self, prefix: str) -> tuple[int, int]:
        _base, files = self._files_under(prefix)
        return len(files), sum(p.stat().st_size for p in files)

    def delete_prefix(self, prefix: str) -> tuple[int, int]:
        base, files = self._files_under(prefix)
        if base is None:
            return 0, 0
        count, total = len(files), sum(p.stat().st_size for p in files)
        shutil.rmtree(base)
        self._prune_empty_dirs(base.parent)
        return count, total

    # ---- 주소·상태 ----

    def file_url(self, key: str, api_path: str, download_name: str | None = None) -> tuple[str, datetime]:
        url, expires_at = make_signed_url(api_path)
        if download_name is not None:
            url += "&download=true"  # download는 서명에 넣지 않는다(11.6)
        return url, expires_at

    def check_writable(self) -> None:
        """시험 파일을 쓰고 읽고 지운다. 실패하면 예외가 난다(/health가 잡아 503으로 답한다)."""
        key = f"{HEALTH_PREFIX}{uuid.uuid4().hex}.probe"
        self.write_bytes(key, b"ok")
        if self.read_bytes(key) != b"ok":
            raise StorageError("저장소에 쓴 내용을 다시 읽지 못했습니다")
        self.delete(key)
