"""분석 API v0.3 — 영상 등록·상태·결과·관절점 파일 (S15P31A404-156, (2/4)).

등록하면 영상을 저장소에 쓰고 바로 202를 돌려준 뒤, 분석은 응답이 나간 뒤 뒤에서 한다.
팀 서비스는 30초(ANALYSIS_HTTP_TIMEOUT_SEC) 안에 답을 받아야 해서, 분석을 요청 안에서 돌리지 않는다.

지금 분석 자리에는 견본 파이프라인(samples/의 견본 결과를 돌려줌)이 들어 있다. 모델 연결은 다음 단계에서
run_pipeline만 바꾼다. 견본 결과의 model은 "sample-pipeline"이라 실제 분석 결과와 섞이지 않는다.

설정(환경변수)
- ANALYSIS_API_KEY: 비어 있으면 인증을 끈다(로컬 개발). 있으면 X-API-Key 헤더가 같아야 한다
- ANALYSIS_UPLOAD_MAX_MB: 영상 한 건 상한. 팀 서비스 UPLOAD_MAX_MB(100)와 맞춘다
- ANALYSIS_STORAGE_DIR: 올린 영상을 두는 곳. 기본은 저장소의 data/analysis_api (git에 안 올라감)

형식 근거: 「분석 API 초안 검토 답변」 10-22, 팀 서비스 분석 클라이언트(backend/app/clients/analysis.py)
"""
import hmac
import json
import os
import shutil
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

KST = timezone(timedelta(hours=9))
HERE = Path(__file__).resolve().parent
SAMPLES_DIR = HERE / "samples"
CHUNK_BYTES = 1024 * 1024

API_KEY = os.environ.get("ANALYSIS_API_KEY", "")
MAX_BYTES = int(os.environ.get("ANALYSIS_UPLOAD_MAX_MB", "100")) * 1024 * 1024
STORAGE_DIR = Path(os.environ.get("ANALYSIS_STORAGE_DIR", HERE.parent / "data" / "analysis_api"))
VIDEO_SUFFIXES = {".mp4", ".mov"}

# 견본 파이프라인. 모델을 연결하면 {"name": "fs-v4", "version": "엔진/각도정의/가중치 해시 8자"}로 바뀐다
MODEL = {"name": "sample-pipeline", "version": "0.3.0/v1/sample"}

# 상태값: queued(대기) → running(분석 중) → done(완료) / failed(실패)
app = FastAPI(title="크림오프 분석 API", version="0.3.0")
JOBS: dict = {}   # 임시 저장소. 서버를 끄면 사라짐 → 결과 DB로 교체 예정 (3/4)
_LOCK = threading.Lock()


class ApiError(Exception):
    """모든 오류를 {"error": {"code", "message", "detail"}} 한 가지 모양으로 내기 위한 예외"""

    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


class AnalysisFailed(Exception):
    """분석 중 실패. code가 상태 조회의 error.code로 나간다 (DECODE_FAILED, INTERNAL)"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


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


def _get(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if job is None:
        raise ApiError(404, "NOT_FOUND", "없는 분석입니다")
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
    """영상 → (결과 JSON, 관절점 파일 JSON). 지금은 견본을 돌려주는 자리이고, 모델 연결 때 이 함수만 바꾼다"""
    if video_path.stat().st_size == 0:
        raise AnalysisFailed("DECODE_FAILED", "영상을 읽을 수 없습니다")
    result = json.loads((SAMPLES_DIR / "result_partial.json").read_text(encoding="utf-8"))
    keypoints = json.loads((SAMPLES_DIR / "keypoints.json").read_text(encoding="utf-8"))
    result.update(id=job["id"], shot_id=job["shot_id"], model=MODEL, created_at=_now())
    result["input"]["filename"] = job["filename"]
    result["files"]["keypoints"] = f"/analyses/{job['id']}/files/keypoints"
    return result, keypoints


def analyze(job_id: str) -> None:
    """응답이 나간 뒤 뒤에서 도는 분석. 어떤 예외도 서버 밖으로 내지 않고 failed로 남긴다(PR-F07-06)"""
    job = JOBS[job_id]
    _update(job_id, status="running")
    try:
        result, keypoints = run_pipeline(Path(job["video_path"]), job)
    except AnalysisFailed as e:
        _update(job_id, status="failed", error={"code": e.code, "message": e.message, "detail": None})
        return
    except Exception:
        _update(job_id, status="failed",
                error={"code": "INTERNAL", "message": "분석 중 알 수 없는 오류가 났습니다", "detail": None})
        return
    _update(job_id, status="done", result=result, keypoints=keypoints)


@app.get("/health")
def health():
    """Docker 상태 확인용이라 인증 없이 연다"""
    return {"status": "ok", "model": MODEL}


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
            "model": MODEL, "meta": info, "filename": video.filename, "video_path": str(path),
            "created_at": now, "updated_at": now, "result": None, "keypoints": None,
        }
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
