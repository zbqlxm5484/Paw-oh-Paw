"""작업 시간 제한(ANALYSIS_JOB_TIMEOUT_SEC)과 촬영 단위 지우기(DELETE /analyses?shot_id=...) 테스트.
GPU 추론이 멈추거나, 다시 분석으로 같은 촬영에 작업이 여러 개 생겨도 사본이 남지 않는지 본다."""
import time

import main
import pytest
import store
from conftest import client


@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    root = tmp_path / "storage"
    monkeypatch.setattr(main, "STORAGE_DIR", root)
    monkeypatch.setattr(main, "API_KEY", "")
    monkeypatch.delenv("ANALYSIS_POSE_SOURCE", raising=False)
    main.JOBS.clear()
    return root


def upload(shot_id="s-1"):
    r = client.post("/analyses", files={"video": ("a.mp4", b"fake video", "video/mp4")},
                    data={"meta": f'{{"shot_id": "{shot_id}"}}'})
    return r.json()["id"]


def stuck(monkeypatch, seconds_ago):
    """분석이 seconds_ago초 전에 시작해 아직 running인 작업 (GPU 추론이 멈춘 것처럼)"""
    monkeypatch.setattr(main, "analyze", lambda job_id: None)
    job_id = upload()
    main._update(job_id, status="running", started_ts=time.time() - seconds_ago)
    return job_id


def test_running_too_long_becomes_timeout_and_can_be_deleted(monkeypatch):
    job_id = stuck(monkeypatch, main.JOB_TIMEOUT_SEC + 10)
    body = client.get(f"/analyses/{job_id}").json()
    assert body["status"] == "failed" and body["error"]["code"] == "TIMEOUT"
    assert client.delete(f"/analyses/{job_id}").status_code == 204     # 더는 409로 막히지 않는다


def test_running_within_limit_stays_running(monkeypatch):
    job_id = stuck(monkeypatch, 5)
    assert client.get(f"/analyses/{job_id}").json()["status"] == "running"
    assert client.delete(f"/analyses/{job_id}").status_code == 409


def test_timeout_survives_restart(monkeypatch):
    job_id = stuck(monkeypatch, main.JOB_TIMEOUT_SEC + 10)
    main.JOBS.clear()                                     # 디스크에서 읽어도 같은 판단
    assert client.get(f"/analyses/{job_id}").json()["error"]["code"] == "TIMEOUT"


def test_late_result_does_not_overwrite_timeout(monkeypatch):
    job_id = stuck(monkeypatch, main.JOB_TIMEOUT_SEC + 10)
    client.get(f"/analyses/{job_id}")                     # TIMEOUT으로 끝냄
    assert main._finish(job_id, status="done", result={"x": 1}, keypoints={}) is None
    assert client.get(f"/analyses/{job_id}").json()["status"] == "failed"


def test_result_after_delete_does_not_recreate_folder(storage, monkeypatch):
    """분석이 끝나기 전에 작업이 지워져도(파기), 늦게 끝난 분석이 폴더를 다시 만들지 않는다"""
    real = main.run_pipeline

    def delete_midway(video_path, job):
        out = real(video_path, job)
        with main._LOCK:                                  # 분석 중에 파기가 지운 것처럼
            main.JOBS.pop(job["id"], None)
            store.delete_job(storage, job["id"])
        return out

    monkeypatch.setattr(main, "run_pipeline", delete_midway)
    job_id = upload()
    assert not (storage / job_id).exists()
    assert client.get(f"/analyses/{job_id}").status_code == 404
    assert store.read_log(storage) == []                  # 기록 줄도 남기지 않는다


def test_delete_all_jobs_of_a_shot(storage):
    first, second, other = upload("s-1"), upload("s-1"), upload("s-2")   # s-1은 다시 분석해 작업이 둘
    r = client.delete("/analyses", params={"shot_id": "s-1"})
    assert r.status_code == 200 and sorted(r.json()["deleted"]) == sorted([first, second])
    assert not (storage / first).exists() and not (storage / second).exists() and (storage / other).exists()
    assert [row["id"] for row in store.read_log(storage)] == [other]


def test_shot_delete_reads_disk_after_restart(storage):
    job_id = upload("s-1")
    main.JOBS.clear()
    assert client.delete("/analyses", params={"shot_id": "s-1"}).json()["deleted"] == [job_id]


def test_shot_delete_refuses_while_any_job_runs(monkeypatch, storage):
    done = upload("s-1")
    monkeypatch.setattr(main, "analyze", lambda job_id: None)
    upload("s-1")                                         # queued
    r = client.delete("/analyses", params={"shot_id": "s-1"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "JOB_IN_PROGRESS"
    assert (storage / done).exists()                      # 하나도 지우지 않는다


def test_shot_delete_with_nothing_is_ok_and_needs_key(monkeypatch):
    assert client.delete("/analyses", params={"shot_id": "none"}).json() == {"shot_id": "none", "deleted": []}
    assert client.delete("/analyses").status_code == 400
    monkeypatch.setattr(main, "API_KEY", "secret")
    assert client.delete("/analyses", params={"shot_id": "none"}).status_code == 401
