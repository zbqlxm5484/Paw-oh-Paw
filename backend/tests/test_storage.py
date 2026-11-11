"""파일 키(7절)와 LocalStorage(11.11)."""

import shutil
import tempfile
import threading
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


@pytest.mark.parametrize("bad", ["../x", "/abs/x", "a/../../x", "", ".", "./", "a/.."])
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


def test_delete_prefix_never_removes_the_root(storage: LocalStorage) -> None:
    # 69 MR 리뷰: "."은 루트 자신이라 delete_prefix(".")가 저장소 전체를 지울 수 있었다
    storage.write_bytes("k/a.txt", b"x")
    for prefix in (".", "./", ""):
        with pytest.raises(StorageError):
            storage.delete_prefix(prefix)
    assert storage.root.is_dir() and storage.read_bytes("k/a.txt") == b"x"


# ---- 동시에 쓰고 지우기(S15P31A404-274) ----


def test_prune_goes_on_when_another_request_removed_the_folder_first(storage: LocalStorage) -> None:
    # 두 요청이 같은 빈 폴더를 정리하면 늦은 쪽은 이미 없는 폴더를 만난다. 오류 없이 위 폴더로 넘어가야 한다
    (storage.root / "e" / "a").mkdir(parents=True)  # e/a/b는 다른 요청이 먼저 지웠다
    storage._prune_empty_dirs(storage.root / "e" / "a" / "b")
    assert not (storage.root / "e").exists()

    storage.write_bytes("i/d/s/keep.txt", b"x")
    storage._prune_empty_dirs(storage.root / "i" / "d" / "gone")
    assert storage.read_bytes("i/d/s/keep.txt") == b"x"  # 비어 있지 않은 폴더에서 멈춘다
    assert storage.root.is_dir()


def test_delete_of_a_file_removed_meanwhile_is_not_an_error(storage: LocalStorage, monkeypatch) -> None:
    storage.write_bytes("i/d/a.txt", b"x")
    path = storage.path("i/d/a.txt")
    original = Path.stat

    def stat_after_removal(self: Path, *args, **kwargs):  # is_file()과 stat() 사이에 다른 요청이 지운 경우
        if self == path and not kwargs:
            self.unlink(missing_ok=True)
        return original(self, *args, **kwargs)

    assert path.is_file()
    monkeypatch.setattr(Path, "stat", stat_after_removal)
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    assert storage.delete("i/d/a.txt") == 0


def test_many_threads_write_and_delete_under_one_folder(storage: LocalStorage) -> None:
    # 같은 기관 폴더 아래에서 올리기·지우기가 겹친다. 빈 폴더 정리가 다른 요청의 쓰기·지우기를 깨뜨리면 안 된다
    errors: list[Exception] = []
    gate = threading.Barrier(8)

    def work(n: int) -> None:
        try:
            gate.wait()
            for i in range(150):
                key = f"inst/dog{n % 2}/s{n}/{i}/analysis.json"
                storage.write_bytes(key, b"{}")
                src = storage.root / f"src-{n}-{i}.bin"
                src.write_bytes(b"v")
                storage.put_file(src, f"inst/dog{n % 2}/s{n}/{i}/original.mp4")
                if i % 2:
                    storage.delete_prefix(f"inst/dog{n % 2}/s{n}/{i}/")
                else:
                    storage.delete(key)
                    storage.delete(f"inst/dog{n % 2}/s{n}/{i}/original.mp4")
        except Exception as error:  # 스레드의 오류를 모아서 본다
            errors.append(error)

    threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert not (storage.root / "inst").exists()


# ---- 274 리뷰: Windows 처리는 지워지는 중인 경로에만, 권한 오류 다시 하기는 Windows에만 ----


def test_path_that_resolves_outside_the_root_is_rejected(storage: LocalStorage, monkeypatch) -> None:
    # 저장소 안의 링크가 밖을 가리키면 resolve()가 밖의 경로를 돌려준다. 어느 OS에서든 거부해야 한다
    outside = storage.root.parent / "elsewhere" / "a.txt"
    original = Path.resolve

    def resolve(self: Path, *args, **kwargs) -> Path:
        return outside if self.name == "a.txt" else original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(StorageError):
        storage.path("link/a.txt")


def test_windows_path_only_rewrites_paths_being_deleted(storage: LocalStorage) -> None:
    from app.storage import local

    inside = storage.root / "i" / "a.txt"
    outside = storage.root.parent / "elsewhere" / "a.txt"
    assert storage._windows_path(inside, "i/a.txt") == inside
    assert storage._windows_path(outside, "i/a.txt") == outside  # 밖을 가리키는 경로는 그대로 두어 검사에 걸리게 한다
    deleted = Path(storage.root.anchor) / local._WINDOWS_DELETED / "$Deleted" / "0001" / "a.txt"
    assert storage._windows_path(deleted, "i/a.txt") == inside


def test_permission_error_is_retried_only_where_it_means_a_folder_being_deleted(
    storage: LocalStorage, monkeypatch
) -> None:
    from app.storage import local

    monkeypatch.setattr(local, "WRITE_RETRY_SEC", 0)
    calls: list[int] = []

    def denied() -> None:
        calls.append(1)
        raise PermissionError("denied")

    monkeypatch.setattr(local, "_RETRY_ERRORS", (FileNotFoundError,))  # Linux: 실제 권한 오류라 바로 올린다
    with pytest.raises(PermissionError):
        storage._write_in_place(storage.root / "p" / "a.txt", denied)
    assert len(calls) == 1

    calls.clear()
    monkeypatch.setattr(local, "_RETRY_ERRORS", (FileNotFoundError, PermissionError))  # Windows
    with pytest.raises(PermissionError):
        storage._write_in_place(storage.root / "p" / "a.txt", denied)
    assert len(calls) == local.WRITE_ATTEMPTS
