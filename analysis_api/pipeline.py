"""분석 파이프라인: 영상 → (결과 JSON v1, 관절점 파일). S15P31A404-180 (3/4), S15P31A404-182 (4/4)

관절점을 어디서 얻을지는 ANALYSIS_POSE_SOURCE로 고른다.
- sample(기본): samples/의 견본 결과를 돌려준다. 모델·엔진 없이 팀 서비스 연동을 시험할 때
- track: 미리 뽑아 둔 관절점 파일(기업 video_kpi.py track 형식, ANALYSIS_TRACK_FILE)에서 올린 영상과
  SHA-256이 같은 영상을 찾아 엔진을 돌린다. GPU·모델 없이 실제 엔진 결과를 낼 수 있다
- 모델로 영상에서 바로 관절점을 뽑는 경로는 MMPose 실행 환경(허정원)이 정해지면 이 자리에 더한다

모델은 models.yaml에서 고른다(ANALYSIS_MODEL, 없으면 default). 관절점 파일·가중치 해시도 모델마다 그 파일에 둔다.

엔진(저장소 루트의 engine/)
- engine.validity.judge_shot: 통과 자르기, 유효·무효 판별, 측정 구간
- engine.joint_rom.frame_angles: 프레임별 카메라 쪽 다리 굽힘 각도(관절점 파일의 angles)
- engine.gait_metrics.pass_metrics: 유효 통과의 걸음 길이·입각기 비율·보행 속도·주기 수(passes[].metrics)
- engine.joint_rom.joint_metrics: 유효 통과의 관절 가동 범위·각도 중앙값·무릎 주기별 가동 범위(passes[].metrics)
형식: docs/analysisApi/resultFormat.md
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:   # analysis_api 폴더에서 실행해도 저장소 루트의 engine 패키지를 쓰게 한다
    sys.path.insert(0, str(ROOT))

from engine.angles import ANGLE_DEF  # noqa: E402
from engine.gait_events import EVENTS_VERSION, detect_pass  # noqa: E402
from engine.gait_metrics import METRICS_VERSION, pass_metrics  # noqa: E402
from engine.joint_rom import ROM_VERSION, joint_metrics  # noqa: E402
from engine.joint_rom import frame_angles as joint_rom_angles  # noqa: E402
from engine.validity import VALIDITY_VERSION, inside_frames, judge_shot, load_config  # noqa: E402

# 결과가 바뀌는 변경(엔진·결과 형식)일 때만 올린다. model.version에 들어가서, 올리면 팀 서비스가 그 전 회차와 비교하지 않는다
API_VERSION = "0.6.0"   # 0.5.0: 보행 수치(S15P31A404-183), 0.6.0: 가동 범위·각도 중앙값(S15P31A404-184)
MODELS_FILE = HERE / "models.yaml"
SAMPLES_DIR = HERE / "samples"
KST = timezone(timedelta(hours=9))
VERSIONS = {"angle_def": ANGLE_DEF, "gait_events": EVENTS_VERSION, "validity": VALIDITY_VERSION,
            "gait_metrics": METRICS_VERSION, "joint_rom": ROM_VERSION}
SAMPLE_MODEL = {"name": "sample-pipeline", "version": f"{API_VERSION}/{ANGLE_DEF}/sample"}


class AnalysisFailed(Exception):
    """분석 중 실패. code가 상태 조회의 error.code로 나간다"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def pose_source() -> str:
    return os.environ.get("ANALYSIS_POSE_SOURCE", "sample")


def load_models(path: Optional[Path] = None) -> dict:
    """models.yaml → {"default": 이름, "models": {이름: 항목}}"""
    import yaml  # 설정을 읽을 때만 필요하다

    data = yaml.safe_load(Path(path or MODELS_FILE).read_text(encoding="utf-8")) or {}
    return {"default": data.get("default"), "models": data.get("models") or {}}


def model_config() -> dict:
    """지금 고른 모델. 환경변수 ANALYSIS_TRACK_FILE·ANALYSIS_WEIGHTS_SHA256이 있으면 models.yaml 값보다 먼저 쓴다.
    models.yaml에 없는 이름이면 항목이 비어 track에서 POSE_UNAVAILABLE이 난다(조용히 다른 모델을 쓰지 않는다)"""
    models = load_models()
    name = os.environ.get("ANALYSIS_MODEL") or models["default"] or "unknown"
    entry = models["models"].get(name) or {}
    track = os.environ.get("ANALYSIS_TRACK_FILE") or entry.get("track_file") or ""
    if track and not Path(track).is_absolute():
        track = str(ROOT / track)
    return {"name": name, "known": name in models["models"],
            "weights_sha256": os.environ.get("ANALYSIS_WEIGHTS_SHA256") or entry.get("weights_sha256") or "",
            "track_file": track}


def current_model() -> dict:
    """상태 조회·health에 내는 모델 정보 {name, version}"""
    if pose_source() == "track":
        cfg = model_config()
        return {"name": cfg["name"], "version": f"{API_VERSION}/{ANGLE_DEF}/{cfg['weights_sha256'][:8] or 'unknown'}"}
    return dict(SAMPLE_MODEL)


def _now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@lru_cache(maxsize=4)
def load_tracks(path: str) -> dict:
    """관절점 파일 → {sha256 또는 파일 이름: 영상 하나}. 같은 파일을 여러 번 읽지 않게 기억해 둔다"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    index = {"__meta__": data.get("meta") or {}}
    for v in data["videos"]:
        if v.get("sha256"):
            index[v["sha256"]] = v
        index.setdefault(Path(v["video"]).name, v)
    return index


def find_track(video_path: Path, filename: Optional[str], track_file: str, sha256: Optional[str] = None) -> tuple:
    """(영상 하나의 관절점, 관절점 파일 meta). SHA-256으로 먼저 찾고, 없으면 파일 이름으로"""
    if not track_file or not Path(track_file).is_file():
        raise AnalysisFailed("POSE_UNAVAILABLE", "관절점 파일이 없습니다 (models.yaml의 track_file 또는 ANALYSIS_TRACK_FILE)")
    index = load_tracks(track_file)
    video = index.get(sha256 or sha256_of(video_path)) or (index.get(Path(filename).name) if filename else None)
    if video is None:
        raise AnalysisFailed("POSE_UNAVAILABLE", "이 영상의 관절점을 찾지 못했습니다")
    return video, index["__meta__"]


# ---- 결과 만들기 ----


def frame_angles(kp, side: str) -> Optional[dict]:
    """카메라 쪽 다리 6관절의 굽힘 각도. 키는 {관절}_l·{관절}_r (결과 형식 5절). 계산은 engine.joint_rom과 같다"""
    if kp is None:
        return None
    suffix = "r" if side == "right" else "l"
    return {f"{joint}_{suffix}": round(angle, 1) for joint, angle in joint_rom_angles(kp, side).items()}


def build_keypoints(video: dict, passes: list) -> dict:
    """관절점 파일. 통과 안의 프레임만 camera_side와 각도를 낸다 (통과 밖은 방향을 정하지 않음)"""
    side_of = {}
    for p in passes:
        for i in range(p["start_frame"], p["end_frame"] + 1):
            side_of[i] = p["camera_side"]
    frames = []
    for i, f in enumerate(video["frames"]):
        kp = f["kp"] if f else None
        side = side_of.get(i)
        frames.append({
            "frame": i,
            "camera_side": side if kp else None,
            "points": [[round(p[0], 1), round(p[1], 1), round(p[2], 3)] for p in kp] if kp else None,
            "angles": frame_angles(kp, side) if kp and side else None,
        })
    return {"angle_def": ANGLE_DEF, "fps": video["fps"], "width": video["width"], "height": video["height"],
            "keypoint_order": "PRD 6.5.3 (0-21)", "frames": frames}


def build_result(job: dict, video: dict, judged: dict, model: dict) -> dict:
    """결과 JSON v1. 수치(metrics)는 유효 통과만 채운다"""
    passes = []
    for p in judged["passes"]:
        passes.append({
            "index": p["index"], "start_frame": p["start_frame"], "end_frame": p["end_frame"],
            "heading": p["heading"], "camera_side": p["camera_side"], "gait": p["gait"],
            "valid": p["valid"], "reason_code": p["reason_code"], "reason": p["reason"],
            "reason_detail": p.get("reason_detail"),
            "measure_start": p["measure_start"], "measure_end": p["measure_end"],
            "metrics": p.get("metrics") or {}, "checks": p["checks"],
        })
    return {
        "id": job["id"], "shot_id": job["shot_id"], "status": "done",
        "model": model, "versions": VERSIONS,
        "input": {"filename": job["filename"], "codec": None, "fps": video["fps"],
                  "width": video["width"], "height": video["height"], "frames": len(video["frames"])},
        "validity": judged["validity"], "validity_reason": judged["validity_reason"],
        "validity_reason_text": judged.get("validity_reason_text"),
        "summary": judged["summary"], "passes": passes,
        "files": {"keypoints": f"/analyses/{job['id']}/files/keypoints"},
        "created_at": _now(),
    }


def run_sample(job: dict) -> tuple:
    result = json.loads((SAMPLES_DIR / "result_partial.json").read_text(encoding="utf-8"))
    keypoints = json.loads((SAMPLES_DIR / "keypoints.json").read_text(encoding="utf-8"))
    result.update(id=job["id"], shot_id=job["shot_id"], model=dict(SAMPLE_MODEL), versions=VERSIONS,
                  created_at=_now())
    result["input"]["filename"] = job["filename"]
    result["files"]["keypoints"] = f"/analyses/{job['id']}/files/keypoints"
    return result, keypoints


def run_track(video_path: Path, job: dict) -> tuple:
    cfg = model_config()
    video, meta = find_track(video_path, job.get("filename"), cfg["track_file"], job.get("video_sha256"))
    made_by = (meta.get("model") or {}).get("name")
    if made_by and made_by != cfg["name"]:   # 다른 모델로 뽑은 관절점에 이 모델 이름을 붙이지 않는다
        raise AnalysisFailed("POSE_UNAVAILABLE", f"관절점 파일의 모델({made_by})이 고른 모델({cfg['name']})과 다릅니다")
    if not video.get("frames") or not video.get("fps"):
        raise AnalysisFailed("DECODE_FAILED", "영상의 프레임 정보를 읽을 수 없습니다")
    cfg_validity = load_config()
    judged = judge_shot(video, cfg_validity)
    for p in judged["passes"]:
        if p["valid"]:   # 제외된 통과는 수치를 내지 않는다 (결과 형식 3절)
            _, kps = inside_frames(video, p["start_frame"], p["end_frame"], cfg_validity)
            events = detect_pass(kps, video["fps"], p["camera_side"])   # 두 계산이 같은 착지·이지를 쓴다
            p["metrics"] = {**pass_metrics(kps, video["fps"], p["camera_side"], events),
                            **joint_metrics(kps, video["fps"], p["camera_side"], events)}
    model = current_model()
    model.update(angle_def=ANGLE_DEF, weights_sha256=cfg["weights_sha256"] or None)
    return build_result(job, video, judged, model), build_keypoints(video, judged["passes"])


def run(video_path: Path, job: dict) -> tuple:
    """영상 → (결과 JSON, 관절점 파일). 실패는 AnalysisFailed"""
    if Path(video_path).stat().st_size == 0:
        raise AnalysisFailed("DECODE_FAILED", "영상을 읽을 수 없습니다")
    if pose_source() == "track":
        return run_track(Path(video_path), job)
    return run_sample(job)
