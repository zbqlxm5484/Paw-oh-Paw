"""작업 지우기(DELETE /analyses/{id})와 전체 파기(purge.py) 테스트. 팀 서비스 자료 파기와 짝이다."""
import json

import main
import purge
import pytest
import store
from fastapi.testclient import TestClient

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    root = tmp_path / "storage"
    monkeypatch.setattr(main, "STORAGE_DIR", root)
    monkeypatch.setattr(main, "API_KEY", "")
    monkeypatch.delenv("ANALYSIS_POSE_SOURCE", raising=False)
    main.JOBS.clear()
    return root


def upload(name="260820-141844-제니-9.8kg-main.mp4"):
    return client.post("/analyses", files={"video": (name, b"fake video", "video/mp4")}).json()["id"]


def test_delete_removes_files_and_log_line(storage):
    keep, gone = upload(), upload()
    assert client.delete(f"/analyses/{gone}").status_code == 204
    assert not (storage / gone).exists() and (storage / keep).exists()
    assert [row["id"] for row in store.read_log(storage)] == [keep]
    assert client.get(f"/analyses/{gone}").status_code == 404
    main.JOBS.clear()                                          # 다시 켠 뒤에도 없다
    assert client.get(f"/analyses/{gone}").status_code == 404


def test_delete_unknown_is_404_and_in_progress_is_409(monkeypatch):
    assert client.delete("/analyses/nope").status_code == 404
    monkeypatch.setattr(main, "analyze", lambda job_id: None)  # queued로 남김
    job_id = upload()
    r = client.delete(f"/analyses/{job_id}")
    assert r.status_code == 409 and r.json()["error"]["code"] == "JOB_IN_PROGRESS"


def test_delete_needs_key(monkeypatch):
    job_id = upload()
    monkeypatch.setattr(main, "API_KEY", "secret")
    assert client.delete(f"/analyses/{job_id}").status_code == 401


def test_log_has_no_filename(storage):
    upload()
    line = (storage / store.LOG_FILE).read_text(encoding="utf-8")
    assert "제니" not in line and "filename" not in json.loads(line)


def test_purge_dry_run_then_execute(storage):
    upload(), upload()
    assert purge.run(["--all"], root=storage) == 0
    assert len(list(storage.glob("*/job.json"))) == 2            # dry run은 지우지 않는다
    assert purge.run(["--all", "--execute"], ask=lambda _: "no", root=storage) == 1
    assert len(list(storage.glob("*/job.json"))) == 2            # 확인 문구가 틀리면 지우지 않는다
    assert purge.run(["--all", "--execute"], ask=lambda _: "PURGE", root=storage) == 0
    assert list(storage.glob("*/job.json")) == [] and not (storage / store.LOG_FILE).exists()


def test_purge_refuses_while_analysis_running(storage, monkeypatch):
    monkeypatch.setattr(main, "analyze", lambda job_id: None)
    upload()
    assert purge.run(["--all", "--execute", "--yes"], root=storage) == 1
    assert len(list(storage.glob("*/job.json"))) == 1


def test_purge_counts_and_removes_folders_without_job_json(storage):
    upload()
    half = storage / "half-upload"                 # 업로드 도중 끊겨 영상만 남은 폴더
    half.mkdir()
    (half / "video.mp4").write_bytes(b"12345")
    stats = store.purge_stats(storage)
    assert stats["jobs"] == 2 and stats["bytes"] >= 5
    assert purge.run(["--all", "--execute", "--yes"], root=storage) == 0
    assert [p for p in storage.iterdir()] == []


def test_broken_log_line_does_not_break_delete(storage):
    keep, gone = upload(), upload()
    with (storage / store.LOG_FILE).open("a", encoding="utf-8") as f:
        f.write('{"id": "half-writ\n')            # 쓰다 만 줄
    assert client.delete(f"/analyses/{gone}").status_code == 204
    assert [row["id"] for row in store.read_log(storage)] == [keep]


def test_delete_reports_failure_when_folder_remains(storage, monkeypatch):
    job_id = upload()
    monkeypatch.setattr(store.shutil, "rmtree", lambda *a, **k: None)   # 지우기가 안 되는 상황
    r = client.delete(f"/analyses/{job_id}")
    assert r.status_code == 500 and r.json()["error"]["code"] == "DELETE_FAILED"
    assert [row["id"] for row in store.read_log(storage)] == [job_id]       # 기록 줄은 그대로


def test_interrupted_upload_leaves_no_folder(storage, monkeypatch):
    async def broken_read(self, size=-1):
        raise ConnectionResetError("client went away")
    from starlette.datastructures import UploadFile
    monkeypatch.setattr(UploadFile, "read", broken_read)
    with pytest.raises(ConnectionResetError):
        client.post("/analyses", files={"video": ("a.mp4", b"x", "video/mp4")})
    assert not storage.exists() or list(storage.iterdir()) == []
