"""파일 키(7절)와 LocalStorage(11.11)."""

import shutil
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.storage import keys
from app.storage.base import StorageError, get_storage
from app.storage.local import LocalStorage

INST, DOG, SESSION, SHOT, REPORT = (uuid.uuid4() for _ in range(5))


def test_keys_follow_section_7_format() -> None:
    assert keys.session_prefix(INST, DOG, SESSION) == f"{INST}/{DOG}/{SESSION}/"
    assert keys.original_key(INST, DOG, SESSION, SHOT, "MP4") == f"{INST}/{DOG}/{SESSION}/{SHOT}/original.mp4"
    assert keys.original_key(INST, DOG, SESSION, SHOT, ".mov").endswith("/original.mov")
    assert keys.result_key(INST, DOG, SESSION, SHOT).endswith(f"/{SHOT}/result.mp4")
    assert keys.analysis_key(INST, DOG, SESSION, SHOT).endswith(f"/{SHOT}/analysis.json")
    assert keys.report_key(INST, DOG, SESSION, REPORT) == f"{INST}/{DOG}/{SESSION}/reports/{REPORT}.pdf"
    with pytest.raises(ValueError):
        keys.original_key(INST, DOG, SESSION, SHOT, "avi")


@pytest.fixture
def storage() -> Iterator[LocalStorage]:
    # pytest의 tmp_path는 경로가 길어서 UUID 네 단계 키를 붙이면 Windows의 경로 길이 한도(260자)에 걸린다.
    # 그래서 짧은 임시 폴더를 쓴다.
    root = Path(tempfile.mkdtemp(prefix="cf-"))
    yield LocalStorage(root / "f")
    shutil.rmtree(root, ignore_errors=True)


def test_put_file_moves_the_temp_file(storage: LocalStorage, tmp_path: Path) -> None:
    src = tmp_path / "upload.bin"
    src.write_bytes(b"x" * 10)
    assert storage.put_file(src, "a/b/original.mp4") == 10
    assert not src.exists()
    assert storage.path("a/b/original.mp4").read_bytes() == b"x" * 10
    # 같은 키에 다시 넣으면 덮어쓴다
    src.write_bytes(b"y" * 3)
    assert storage.put_file(src, "a/b/original.mp4") == 3
    assert storage.read_bytes("a/b/original.mp4") == b"yyy"


def test_write_read_delete_and_prune_empty_dirs(storage: LocalStorage) -> None:
    storage.write_bytes("i/d/s/x/analysis.json", b"{}")
    assert storage.read_bytes("i/d/s/x/analysis.json") == b"{}"
    assert storage.delete("i/d/s/x/analysis.json") == 2
    assert not (storage.root / "i").exists()  # 빈 폴더는 지운다
    assert storage.delete("i/d/s/x/analysis.json") == 0
    assert storage.delete(None) == 0


def test_delete_prefix_and_stat_prefix(storage: LocalStorage) -> None:
    prefix = keys.session_prefix(INST, DOG, SESSION)
    storage.write_bytes(f"{prefix}{SHOT}/original.mp4", b"a" * 5)
    storage.write_bytes(f"{prefix}{SHOT}/analysis.json", b"b" * 7)
    storage.write_bytes(f"{prefix}reports/{REPORT}.pdf", b"c" * 9)
    storage.write_bytes(keys.dog_prefix(INST, DOG) + "other/keep.txt", b"keep")

    assert storage.stat_prefix(prefix) == (3, 21)
    assert storage.delete_prefix(prefix) == (3, 21)
    assert storage.stat_prefix(prefix) == (0, 0)
    assert storage.delete_prefix(prefix) == (0, 0)
    assert storage.read_bytes(keys.dog_prefix(INST, DOG) + "other/keep.txt") == b"keep"


@pytest.mark.parametrize("bad", ["../x", "/abs/x", "a/../../x", ""])
def test_keys_outside_root_are_rejected(storage: LocalStorage, bad: str) -> None:
    with pytest.raises(StorageError):
        storage.path(bad)


def test_local_copy_is_the_real_path(storage: LocalStorage) -> None:
    storage.write_bytes("k/original.mp4", b"v")
    with storage.local_copy("k/original.mp4") as path:
        assert path == storage.path("k/original.mp4")
        assert path.read_bytes() == b"v"


def test_file_url_is_signed_and_download_flag_is_outside_signature(storage: LocalStorage) -> None:
    api_path = f"/api/v1/shots/{SHOT}/video"
    url, expires_at = storage.file_url("k", api_path)
    assert url.startswith(f"{api_path}?exp=") and "&sig=" in url
    assert expires_at.tzinfo is not None
    download, _ = storage.file_url("k", f"/api/v1/reports/{REPORT}/file", download_name="보고서.pdf")
    assert download.endswith("&download=true")


def test_check_writable_leaves_nothing_behind(storage: LocalStorage) -> None:
    storage.check_writable()
    assert storage.stat_prefix(".health/") == (0, 0)
    assert not (storage.root / ".health").exists()


def test_get_storage_follows_settings() -> None:
    storage = get_storage()
    assert isinstance(storage, LocalStorage)
    assert storage.root == Path(get_settings().STORAGE_ROOT).resolve()
    assert get_storage() is storage
