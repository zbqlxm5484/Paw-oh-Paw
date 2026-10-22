"""분석 API 뼈대 v0.2 — 등록, 상태, 결과, 관절점 파일.

분석은 아직 하지 않는다. 엔진 연결과 작업 큐는 다음 단계.
형식 근거: 「분석 API 초안 검토 답변」 10-22
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

KST = timezone(timedelta(hours=9))
MAX_BYTES = 500 * 1024 * 1024                                # 영상 한 건 상한 (임시)
MODEL = {"name": "fs-v4", "version": "0.1.0/v1/a4261a10"}    # 엔진/각도정의/가중치 해시 8자. 설정 파일로 옮길 예정

# 상태값: queued(대기) → running(분석 중) → done(완료) / failed(실패)
app = FastAPI(title="크림오프 분석 API", version="0.2.0")
JOBS: dict = {}   # 임시 저장소. 서버를 끄면 사라짐 → 결과 DB로 교체 예정


class ApiError(Exception):
    """모든 오류를 {"error": {"code", "message"}} 한 가지 모양으로 내기 위한 예외"""

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


def _now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def _get(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if job is None:
        raise ApiError(404, "NOT_FOUND", "없는 분석입니다")
    return job


def _ready(job: dict) -> None:
    if job["status"] != "done":
        raise ApiError(409, "NOT_READY", "아직 분석이 끝나지 않았습니다")


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}


@app.post("/analyses", status_code=202)
async def create_analysis(video: UploadFile = File(...), meta: Optional[str] = Form(None)):
    if not (video.content_type or "").startswith("video/"):
        raise ApiError(415, "UNSUPPORTED_MEDIA", "영상 파일만 받습니다")
    if video.size is not None and video.size > MAX_BYTES:
        raise ApiError(413, "TOO_LARGE", "영상이 너무 큽니다")
    info = {}
    if meta:
        try:
            info = json.loads(meta)
        except json.JSONDecodeError:
            info = None
        if not isinstance(info, dict):
            raise ApiError(400, "INVALID_META", "meta는 JSON 객체여야 합니다")
    job_id = str(uuid.uuid4())
    now = _now()
    JOBS[job_id] = {
        "id": job_id, "shot_id": info.get("shot_id"), "status": "queued", "error": None,
        "model": MODEL, "meta": info, "filename": video.filename,
        "created_at": now, "updated_at": now, "result": None, "keypoints": None,
    }
    return {"id": job_id, "status": "queued"}


@app.get("/analyses/{job_id}")
def get_status(job_id: str):
    job = _get(job_id)
    return {k: job[k] for k in ("id", "shot_id", "status", "error", "model", "created_at", "updated_at")}


@app.get("/analyses/{job_id}/result")
def get_result(job_id: str):
    job = _get(job_id)
    _ready(job)
    return job["result"]


@app.get("/analyses/{job_id}/files/keypoints")
def get_keypoints(job_id: str):
    job = _get(job_id)
    _ready(job)
    return job["keypoints"]