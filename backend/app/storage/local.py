"""LocalStorage: 서버 디스크(STORAGE_ROOT 아래)에 두는 저장소(11.11 local 열).

이 파일만 open()·os.replace()·shutil을 직접 쓴다. 다른 코드는 StorageService를 거친다(11.3).
"""

from __future__ import annotations

import os
import shutil
import time
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from datetime import datetime
from pathlib import Path

from app.core.security import make_signed_url
from app.storage.base import StorageError

HEALTH_PREFIX = ".health/"
WRITE_ATTEMPTS = 4  # 쓰는 중에 폴더가 지워졌을 때 해 보는 횟수(_write_in_place)
WRITE_RETRY_SEC = 0.02  # 다시 하기 전에 쉬는 시간. 횟수만큼 늘린다


def _size(path: Path) -> int:
    """파일 크기. 세는 중에 다른 요청이 지웠으면 0."""
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


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
        if os.name == "nt" and not path.is_relative_to(self.root):
            # Windows(NTFS)에서만: 다른 요청이 지우는 중인 경로를 resolve()하면 \?\C:\$Extend\$Deleted\... 가
            # 돌아온다. 그때는 글자로만 정리한 경로를 쓴다(".."은 위에서 이미 막았다). 운영(Linux)에는 없는 일이다
            path = Path(os.path.normpath(self.root / key))
        if path == self.root:
            # "."·"./"처럼 루트 자신을 가리키는 키. delete_prefix(".")가 저장소 전체를 지우는 일을 막는다
            raise StorageError(f"저장소 루트 자체를 가리키는 키입니다: {key!r}")
        if not path.is_relative_to(self.root):
            raise StorageError(f"저장소 밖을 가리키는 키입니다: {key!r}")
        return path

    def _prune_empty_dirs(self, directory: Path) -> None:
        """파일을 지운 뒤 빈 폴더를 루트 직전까지 지운다.

        요청 여럿이 같은 폴더 아래에서 함께 쓰고 지운다(S15P31A404-274). 비었는지 먼저 보고 지우면 그사이 다른
        요청이 그 폴더를 지우거나 파일을 넣을 수 있으므로, 바로 rmdir을 부르고 결과로 가른다. 이미 없으면 위 폴더로
        넘어가고, 비어 있지 않거나 지울 수 없으면 거기서 멈춘다.
        """
        while directory != self.root:
            try:
                directory.rmdir()
            except FileNotFoundError:
                pass  # 다른 요청이 먼저 지웠다
            except OSError:
                return  # 비어 있지 않다
            directory = directory.parent

    def _write_in_place(self, dst: Path, write: Callable[[], None]) -> None:
        """dst의 폴더를 만들고 write를 부른다.

        폴더를 만든 직후에는 비어 있어서, 같은 때 돌던 다른 요청의 빈 폴더 정리가 그 폴더를 지울 수 있다. 그러면
        write가 FileNotFoundError를 내므로(Windows는 지워지는 중인 폴더에 PermissionError를 낸다) 잠깐 쉬고 폴더를
        다시 만들어 다시 한다. 마지막에도 같으면 그대로 올린다.
        """
        for attempt in range(WRITE_ATTEMPTS):
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                write()
                return
            except (FileNotFoundError, PermissionError):
                if attempt == WRITE_ATTEMPTS - 1:
                    raise
                time.sleep(WRITE_RETRY_SEC * (attempt + 1))

    # ---- 쓰기·읽기 ----

    def put_file(self, src: Path, key: str) -> int:
        dst = self.path(key)
        size = src.stat().st_size  # src가 없으면 여기서 끝난다. 아래의 FileNotFoundError는 dst 폴더가 없다는 뜻이다

        def move() -> None:
            try:
                os.replace(src, dst)  # 같은 볼륨이면 이름만 바꾼다
            except FileNotFoundError:
                raise
            except OSError:
                shutil.copyfile(src, dst)  # 다른 볼륨이면 복사한 뒤 지운다
                src.unlink()

        self._write_in_place(dst, move)
        return size

    def write_bytes(self, key: str, data: bytes) -> None:
        dst = self.path(key)
        # 임시 이름은 짧게 둔다. 키가 UUID 네 단계라 Windows의 경로 길이 한도(260자)에 걸리기 쉽다.
        tmp = dst.parent / f".tmp-{uuid.uuid4().hex[:12]}"

        def write() -> None:
            tmp.write_bytes(data)
            os.replace(tmp, dst)

        self._write_in_place(dst, write)

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
        try:
            size = path.stat().st_size
            path.unlink()
        except FileNotFoundError:
            return 0  # 그사이 다른 요청이 지웠다
        self._prune_empty_dirs(path.parent)
        return size

    def _files_under(self, prefix: str) -> tuple[Path | None, list[Path]]:
        base = self.path(prefix.rstrip("/\\"))
        if not base.is_dir():
            return None, []
        try:
            return base, [p for p in base.rglob("*") if p.is_file()]
        except FileNotFoundError:
            return None, []  # 훑는 중에 다른 요청이 통째로 지웠다

    def stat_prefix(self, prefix: str) -> tuple[int, int]:
        _base, files = self._files_under(prefix)
        return len(files), sum(_size(p) for p in files)

    def delete_prefix(self, prefix: str) -> tuple[int, int]:
        base, files = self._files_under(prefix)
        if base is None:
            return 0, 0
        count, total = len(files), sum(_size(p) for p in files)
        try:
            shutil.rmtree(base)
        except FileNotFoundError:
            pass  # 그사이 다른 요청이 지웠다. 지우려던 것이 없으니 끝난 것이다
        self._prune_empty_dirs(base.parent)
        return count, total

    # ---- 주소·상태 ----

    def file_url(
        self, key: str, api_path: str, download_name: str | None = None, *, now: datetime | None = None
    ) -> tuple[str, datetime]:
        url, expires_at = make_signed_url(api_path, now=now)
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
