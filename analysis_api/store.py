"""분석 작업 기록: 작업 상태·결과·관절점 파일을 디스크에 남긴다. S15P31A404-182, (4/4)

분석 API를 다시 켜도 끝난 작업은 그대로 조회되게 하려고 둔다. 작업마다 저장소({작업 ID}/) 안에
- job.json: 작업 상태 (결과·관절점은 빼고)
- result.json: 결과 JSON v1
- keypoints.json: 관절점 파일
- video.*: 올린 영상 (main._save_video)
을 두고, 저장소 맨 위 analyses.jsonl에 끝난 작업을 한 줄씩 쌓는다 (모델·버전·판정·걸린 시간).

파일은 임시 이름으로 다 쓴 뒤 이름을 바꿔 넣는다. 쓰는 도중에 꺼져도 반쯤 쓴 파일이 남지 않는다.
"""
import json
import os
import threading
from pathlib import Path
from typing import Optional

JOB_FILE, RESULT_FILE, KEYPOINTS_FILE, LOG_FILE = "job.json", "result.json", "keypoints.json", "analyses.jsonl"
UNFINISHED = ("queued", "running")
_LOG_LOCK = threading.Lock()


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)   # 같은 폴더 안 이름 바꾸기는 한 번에 일어난다


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_job(root: Path, job: dict) -> None:
    """작업 상태를 job.json에. 결과와 관절점이 처음 생기면 각자 파일로"""
    folder = Path(root) / job["id"]
    state = {k: v for k, v in job.items() if k not in ("result", "keypoints")}
    if job.get("result") is not None and not (folder / RESULT_FILE).exists():
        _write_json(folder / RESULT_FILE, job["result"])
        _write_json(folder / KEYPOINTS_FILE, job["keypoints"])
    _write_json(folder / JOB_FILE, state)


def load_job(root: Path, job_id: str) -> Optional[dict]:
    """디스크의 작업 하나. 없으면 None. 작업 ID를 경로로 쓰므로 폴더 이름으로 쓸 수 없는 값은 바로 None"""
    if not job_id or Path(job_id).name != job_id or job_id.startswith("."):
        return None
    folder = Path(root) / job_id
    job = _read_json(folder / JOB_FILE)
    if not isinstance(job, dict) or job.get("id") != job_id:
        return None
    job["result"] = _read_json(folder / RESULT_FILE) if job.get("status") == "done" else None
    job["keypoints"] = _read_json(folder / KEYPOINTS_FILE) if job.get("status") == "done" else None
    return job


def unfinished_jobs(root: Path) -> list:
    """queued·running으로 남아 있는 작업. 분석 중에 서버가 꺼졌던 것들이다"""
    out = []
    for path in sorted(Path(root).glob(f"*/{JOB_FILE}")):
        job = load_job(root, path.parent.name)
        if job and job.get("status") in UNFINISHED:
            out.append(job)
    return out


def append_log(root: Path, entry: dict) -> None:
    """끝난 작업 한 줄. 모델을 바꿔 가며 돌린 결과를 나중에 비교하는 기록이다 (REQ-OP-006)"""
    Path(root).mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False)
    with _LOG_LOCK, (Path(root) / LOG_FILE).open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_log(root: Path) -> list:
    path = Path(root) / LOG_FILE
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
