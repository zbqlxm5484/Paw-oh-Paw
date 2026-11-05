"""분석 API — 영상 등록·상태·결과·관절점 파일 (S15P31A404-156 (2/4), S15P31A404-180 (3/4), S15P31A404-182 (4/4)).

등록하면 영상을 저장소에 쓰고 바로 202를 돌려준 뒤, 분석은 응답이 나간 뒤 뒤에서 한다.
팀 서비스는 30초(ANALYSIS_HTTP_TIMEOUT_SEC) 안에 답을 받아야 해서, 분석을 요청 안에서 돌리지 않는다.

분석 자체(관절점 → 유효 판별 → 결과 JSON)는 pipeline.py가 한다. 이 파일은 HTTP와 작업 상태만 맡는다.
작업 상태·결과는 store.py로 디스크에 남겨, 분석 API를 다시 켜도 끝난 작업은 그대로 조회된다.

설정(환경변수)
- ANALYSIS_API_KEY: 비어 있으면 인증을 끈다(로컬 개발). 있으면 X-API-Key 헤더가 같아야 한다
- ANALYSIS_UPLOAD_MAX_MB: 영상 한 건 상한. 팀 서비스 UPLOAD_MAX_MB(100)와 맞춘다
- ANALYSIS_STORAGE_DIR: 올린 영상을 두는 곳. 기본은 저장소의 data/analysis_api (git에 안 올라감)
- ANALYSIS_POSE_SOURCE 등 분석 설정은 pipeline.py 참고

형식 근거: docs/analysisApi/resultFormat.md (결과 JSON v1), 팀 서비스 분석 클라이언트(backend/app/clients/analysis.py)
"""
import hmac
import json
import logging
import os
import shutil
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import store
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pipeline import (
    API_VERSION,
    VERSIONS,
    AnalysisFailed,
    current_model,
    model_config,
    pose_source,
    sha256_of,
)
from pipeline import run as pipeline_run

KST = timezone(timedelta(hours=9))
HERE = Path(__file__).resolve().parent
CHUNK_BYTES = 1024 * 1024

API_KEY = os.environ.get("ANALYSIS_API_KEY", "")
MAX_BYTES = int(os.environ.get("ANALYSIS_UPLOAD_MAX_MB", "100")) * 1024 * 1024
STORAGE_DIR = Path(os.environ.get("ANALYSIS_STORAGE_DIR", HERE.parent / "data" / "analysis_api"))
VIDEO_SUFFIXES = {".mp4", ".mov"}

logger = logging.getLogger("analysis_api")


def recover_unfinished() -> int:
    """분석 중에 서버가 꺼져 queued·running으로 남은 작업을 failed(INTERRUPTED)로. 팀 서비스는 다시 분석으로 안내한다"""
    jobs = store.unfinished_jobs(STORAGE_DIR)
    for job in jobs:
        job.update(status="failed", updated_at=_now(), error={
            "code": "INTERRUPTED", "message": "분석 중에 분석 API가 다시 시작되었습니다", "detail": None})
        store.save_job(STORAGE_DIR, job)
    return len(jobs)


@asynccontextmanager
async def lifespan(app: FastAPI):
    count = recover_unfinished()
    if count:
        logger.warning("interrupted jobs marked failed: %d", count)
    yield


# 상태값: queued(대기) → running(분석 중) → done(완료) / failed(실패)
app = FastAPI(title="크림오프 분석 API", version=API_VERSION, lifespan=lifespan)
JOBS: dict = {}   # 디스크(store)의 작업을 읽어 둔 것. 서버를 다시 켜면 비고, 조회할 때 디스크에서 다시 읽는다
_LOCK = threading.Lock()


class ApiError(Exception):
    """모든 오류를 {"error": {"code", "message", "detail"}} 한 가지 모양으로 내기 위한 예외"""

    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "detail": None}})


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return _error(exc.status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return _error(400, "INVALID_REQUEST", "필수 항목이 빠졌거나 형식이 틀렸습니다")


def require_key(x_api_key: Optional[str] = Header(None)) -> None:
    """ANALYSIS_API_KEY가 있으면 X-API-Key가 같아야 한다. 비교는 시간 차이로 키가 새지 않게 compare_digest로"""
    if API_KEY and not (x_api_key and hmac.compare_digest(x_api_key, API_KEY)):
        raise ApiError(401, "AUTH_REQUIRED", "분석 API 키가 없거나 맞지 않습니다")


def _now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def _update(job_id: str, **fields) -> None:
    with _LOCK:
        JOBS[job_id].update(fields, updated_at=_now())
        store.save_job(STORAGE_DIR, JOBS[job_id])


def _get(job_id: str) -> dict:
    """메모리에 없으면 디스크에서 읽는다 (분석 API를 다시 켠 뒤의 조회)"""
    job = JOBS.get(job_id)
    if job is None:
        job = store.load_job(STORAGE_DIR, job_id)
        if job is None:
            raise ApiError(404, "NOT_FOUND", "없는 분석입니다")
        with _LOCK:
            job = JOBS.setdefault(job_id, job)
    return job


def _ready(job: dict) -> None:
    if job["status"] != "done":
        raise ApiError(409, "NOT_READY", "아직 분석이 끝나지 않았습니다")


def _parse_meta(meta: Optional[str]) -> dict:
    if not meta:
        return {}
    try:
        info = json.loads(meta)
    except json.JSONDecodeError:
        info = None
    if not isinstance(info, dict):
        raise ApiError(400, "INVALID_META", "meta는 JSON 객체여야 합니다")
    return info


async def _save_video(video: UploadFile, job_id: str) -> Path:
    """조금씩 읽어 저장하면서 크기를 센다. 상한을 넘으면 지금까지 쓴 것을 지우고 413"""
    suffix = Path(video.filename or "").suffix.lower()
    folder = STORAGE_DIR / job_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"video{suffix if suffix in VIDEO_SUFFIXES else '.mp4'}"
    written = 0
    try:
        with path.open("wb") as out:
            while chunk := await video.read(CHUNK_BYTES):
                written += len(chunk)
                if written > MAX_BYTES:
                    raise ApiError(413, "TOO_LARGE", "영상이 너무 큽니다")
                out.write(chunk)
    except ApiError:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return path


def run_pipeline(video_path: Path, job: dict) -> tuple:
    """영상 → (결과 JSON, 관절점 파일 JSON). 실제 일은 pipeline.run이 한다 (테스트에서 이 자리를 바꿔 끼운다)"""
    return pipeline_run(video_path, job)


def _record(job: dict, started: float) -> None:
    """끝난 작업을 analyses.jsonl에 한 줄. 기록을 못 남겨도 분석 결과는 그대로 둔다"""
    result = job.get("result") or {}
    entry = {
        "id": job["id"], "shot_id": job["shot_id"],   # 파일 이름은 남기지 않는다(반려견 이름이 들어 있을 수 있음)
        "video_sha256": job.get("video_sha256"), "pose_source": job.get("pose_source"),
        "model": job["model"], "versions": result.get("versions") or VERSIONS,
        "status": job["status"], "error_code": (job.get("error") or {}).get("code"),
        "validity": result.get("validity"), "validity_reason": result.get("validity_reason"),
        "summary": result.get("summary"), "elapsed_ms": round((time.monotonic() - started) * 1000),
        "created_at": job["created_at"], "finished_at": job["updated_at"],
    }
    try:
        store.append_log(STORAGE_DIR, entry)
    except OSError:
        logger.exception("could not write analyses.jsonl for job %s", job["id"])


def analyze(job_id: str) -> None:
    """응답이 나간 뒤 뒤에서 도는 분석. 어떤 예외도 서버 밖으로 내지 않고 failed로 남긴다(PR-F07-06)"""
    job = JOBS[job_id]
    started = time.monotonic()
    try:
        _update(job_id, status="running", video_sha256=sha256_of(Path(job["video_path"])))
        result, keypoints = run_pipeline(Path(job["video_path"]), job)
    except AnalysisFailed as e:
        _update(job_id, status="failed", error={"code": e.code, "message": e.message, "detail": None})
    except Exception:
        logger.exception("analysis failed job=%s", job_id)
        _update(job_id, status="failed",
                error={"code": "INTERNAL", "message": "분석 중 알 수 없는 오류가 났습니다", "detail": None})
    else:
        _update(job_id, status="done", result=result, keypoints=keypoints,
                model={k: result["model"][k] for k in ("name", "version")})
    _record(JOBS[job_id], started)


@app.get("/health")
def health():
    """Docker 상태 확인용이라 인증 없이 연다"""
    cfg = model_config()
    return {"status": "ok", "model": current_model(), "pose_source": pose_source(),
            "model_known": cfg["known"] or pose_source() == "sample"}


@app.post("/analyses", status_code=202, dependencies=[Depends(require_key)])
async def create_analysis(background: BackgroundTasks, video: UploadFile = File(...),
                          meta: Optional[str] = Form(None)):
    if not (video.content_type or "").startswith("video/"):
        raise ApiError(415, "UNSUPPORTED_MEDIA", "영상 파일만 받습니다")
    info = _parse_meta(meta)
    job_id = str(uuid.uuid4())
    path = await _save_video(video, job_id)
    now = _now()
    with _LOCK:
        JOBS[job_id] = {
            "id": job_id, "shot_id": info.get("shot_id"), "status": "queued", "error": None,
            "model": current_model(), "pose_source": pose_source(), "meta": info, "filename": video.filename,
            "video_path": str(path), "created_at": now, "updated_at": now, "result": None, "keypoints": None,
        }
        store.save_job(STORAGE_DIR, JOBS[job_id])
    background.add_task(analyze, job_id)
    return {"id": job_id, "status": "queued"}


@app.get("/analyses/{job_id}", dependencies=[Depends(require_key)])
def get_status(job_id: str):
    job = _get(job_id)
    return {k: job[k] for k in ("id", "shot_id", "status", "error", "model", "created_at", "updated_at")}


@app.get("/analyses/{job_id}/result", dependencies=[Depends(require_key)])
def get_result(job_id: str):
    job = _get(job_id)
    _ready(job)
    return job["result"]


@app.get("/analyses/{job_id}/files/keypoints", dependencies=[Depends(require_key)])
def get_keypoints(job_id: str):
    job = _get(job_id)
    _ready(job)
    return job["keypoints"]


@app.delete("/analyses/{job_id}", status_code=204, dependencies=[Depends(require_key)])
def delete_analysis(job_id: str):
    """작업 하나를 지운다: 올린 영상·상태·결과·관절점 파일과 analyses.jsonl의 그 줄(자료 파기, 백엔드 명세 15.9).
    분석 중(queued·running)이면 409 JOB_IN_PROGRESS. 없는 작업은 404라, 부르는 쪽은 404도 "이미 없음"으로 보면 된다"""
    job = _get(job_id)
    if job["status"] in store.UNFINISHED:
        raise ApiError(409, "JOB_IN_PROGRESS", "분석 중인 작업은 지울 수 없습니다")
    with _LOCK:
        JOBS.pop(job_id, None)
        files, size = store.delete_job(STORAGE_DIR, job_id)
    logger.info("analysis deleted job=%s files=%d bytes=%d", job_id, files, size)
    return Response(status_code=204)
