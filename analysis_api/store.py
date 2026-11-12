"""분석 작업 기록: 작업 상태·결과·관절점 파일을 디스크에 남긴다. S15P31A404-182, (4/4)

분석 API를 다시 켜도 끝난 작업은 그대로 조회되게 하려고 둔다. 작업마다 저장소({작업 ID}/) 안에
- job.json: 작업 상태 (결과·관절점은 빼고)
- result.json: 결과 JSON v1
- keypoints.json: 관절점 파일
- video.*: 올린 영상 (main._save_video)
을 두고, 저장소 맨 위 analyses.jsonl에 끝난 작업을 한 줄씩 쌓는다 (모델·버전·판정·걸린 시간).

파일은 임시 이름으로 다 쓴 뒤 이름을 바꿔 넣는다. 쓰는 도중에 꺼져도 반쯤 쓴 파일이 남지 않는다.

파기(팀 서비스 자료 파기와 짝, 백엔드 명세 7절·15.9): delete_job은 작업 하나(폴더째, analyses.jsonl의 그 줄까지),
purge_all은 저장소 전체를 지운다. analyses.jsonl에는 파일 이름을 남기지 않는다(기업 영상 이름에 반려견 이름이 있다).
"""
import json
import os
import shutil
import threading
import uuid
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


def load_state(root: Path, job_id: str) -> Optional[dict]:
    """작업 상태(job.json)만. 없으면 None. 여러 작업을 훑을 때 쓴다: 결과·관절점 파일(작업마다 수백 KB)은 읽지 않는다.
    작업 ID를 경로로 쓰므로 폴더 이름으로 쓸 수 없는 값은 바로 None"""
    if not job_id or Path(job_id).name != job_id or job_id.startswith("."):
        return None
    job = _read_json(Path(root) / job_id / JOB_FILE)
    if not isinstance(job, dict) or job.get("id") != job_id:
        return None
    return job


def load_job(root: Path, job_id: str) -> Optional[dict]:
    """디스크의 작업 하나(끝났으면 결과·관절점까지). 없으면 None"""
    job = load_state(root, job_id)
    if job is None:
        return None
    folder = Path(root) / job_id
    job["result"] = _read_json(folder / RESULT_FILE) if job.get("status") == "done" else None
    job["keypoints"] = _read_json(folder / KEYPOINTS_FILE) if job.get("status") == "done" else None
    return job


def unfinished_jobs(root: Path) -> list:
    """queued·running으로 남아 있는 작업. 분석 중에 서버가 꺼졌던 것들이다"""
    out = []
    for path in sorted(Path(root).glob(f"*/{JOB_FILE}")):
        job = load_state(root, path.parent.name)
        if job and job.get("status") in UNFINISHED:
            out.append(job)
    return out


def append_log(root: Path, entry: dict) -> None:
    """끝난 작업 한 줄. 모델을 바꿔 가며 돌린 결과를 나중에 비교하는 기록이다 (REQ-OP-006)"""
    Path(root).mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False)
    with _LOG_LOCK, (Path(root) / LOG_FILE).open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _valid_id(job_id: str) -> bool:
    return bool(job_id) and Path(job_id).name == job_id and not job_id.startswith(".")


def is_job_dir_name(name: str) -> bool:
    """작업 폴더 이름인가. 작업 ID는 uuid4 문자열(main.create_analysis)이라 그 모양인 이름만 작업 폴더로 본다"""
    try:
        return str(uuid.UUID(name)) == name
    except ValueError:
        return False


def _job_dirs(root: Path) -> list:
    """저장소 아래 작업 폴더(이름이 UUID인 폴더). job.json이 없는 폴더(업로드 도중 끊겨 영상만 남은 것)도 포함한다.
    이름이 UUID가 아닌 폴더는 건드리지 않는다: ANALYSIS_STORAGE_DIR를 data/처럼 넓게 잘못 줘도 data/tracks/ 등이 남는다"""
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and is_job_dir_name(p.name))


def _other_entries(root: Path) -> list:
    """작업 폴더도 기록 파일도 아닌 것. 파기 명령이 지우지 않고 개수만 알린다"""
    root = Path(root)
    if not root.is_dir():
        return []
    ours = {LOG_FILE, LOG_FILE + ".tmp"}
    return [p for p in root.iterdir() if not (p.is_dir() and is_job_dir_name(p.name)) and p.name not in ours]


def _parse(line: str):
    """기록 한 줄. 깨진 줄(쓰는 도중 꺼진 것 등)은 None"""
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        return None
    return row if isinstance(row, dict) else None


def _dir_size(folder: Path) -> tuple:
    files = [p for p in folder.rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files)


def scrub_log(root: Path, job_ids: set) -> int:
    """analyses.jsonl에서 그 작업들의 줄을 지운다. 지운 줄 수"""
    path = Path(root) / LOG_FILE
    if not path.exists() or not job_ids:
        return 0
    with _LOG_LOCK:
        lines = path.read_text(encoding="utf-8").splitlines()
        # 깨진 줄은 어느 작업 것인지 알 수 없고 읽을 수도 없으므로 버린다(지운 작업의 조각일 수 있다)
        keep = [line for line in lines if (row := _parse(line)) is not None and row.get("id") not in job_ids]
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text("".join(line + "\n" for line in keep), encoding="utf-8")
        os.replace(tmp, path)
    return len(lines) - len(keep)


def delete_job(root: Path, job_id: str) -> tuple:
    """작업 하나를 지운다(영상·상태·결과·관절점 파일, 기록 줄). (지운 파일 수, 바이트). 없으면 (0, 0).
    폴더를 다 지우지 못하면 OSError(기록 줄은 그대로 둔다)"""
    if not (_valid_id(job_id) and is_job_dir_name(job_id)):
        return 0, 0
    folder = Path(root) / job_id
    files, size = _dir_size(folder) if folder.is_dir() else (0, 0)
    shutil.rmtree(folder, ignore_errors=True)
    if folder.exists():
        raise OSError(f"작업 폴더를 다 지우지 못했습니다: {job_id}")
    scrub_log(root, {job_id})
    return files, size


def purge_stats(root: Path) -> dict:
    """전체 파기 대상: 작업 수, 파일 수(기록 파일 포함), 바이트, 분석 중인 작업 수"""
    jobs = _job_dirs(root)
    files = size = 0
    for folder in jobs:
        f, b = _dir_size(folder)
        files, size = files + f, size + b
    log = Path(root) / LOG_FILE
    if log.exists():
        files, size = files + 1, size + log.stat().st_size
    return {"jobs": len(jobs), "files": files, "bytes": size, "unfinished": len(unfinished_jobs(root)),
            "others": len(_other_entries(root))}


def purge_all(root: Path) -> dict:
    """저장소의 모든 작업과 analyses.jsonl을 지운다. 지우기 전에 센 값을 돌려준다"""
    stats = purge_stats(root)
    for folder in _job_dirs(root):
        shutil.rmtree(folder, ignore_errors=True)
    for name in (LOG_FILE, LOG_FILE + ".tmp"):
        (Path(root) / name).unlink(missing_ok=True)
    left = _job_dirs(root)
    if left:
        raise OSError(f"작업 폴더 {len(left)}개를 다 지우지 못했습니다")
    return stats


def jobs_of_shot(root: Path, shot_id: str) -> list:
    """그 촬영(shot_id)으로 만든 작업들의 상태(job.json). 다시 분석하면 같은 촬영에 작업이 여러 개 생긴다.
    결과·관절점 파일은 읽지 않는다: 작업 300개에서 1.8초 걸리던 훑기가 0.07초가 된다(조영운 측정, 팀 서비스 호출 한도 30초)"""
    out = []
    for folder in _job_dirs(root):
        job = load_state(root, folder.name)
        if job and job.get("shot_id") == shot_id:
            out.append(job)
    return out


def read_log(root: Path) -> list:
    path = Path(root) / LOG_FILE
    if not path.exists():
        return []
    return [row for line in path.read_text(encoding="utf-8").splitlines() if (row := _parse(line)) is not None]
