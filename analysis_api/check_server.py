"""떠 있는 분석 API 점검: python check_server.py --url http://127.0.0.1:18010 --video a.mp4 [--video b.mp4 ...]

GPU 서버에 배포한 분석 API가 팀 서비스와 같은 방식으로 불렸을 때 제대로 답하는지 영상 몇 개로 확인한다(S15P31A404-258).
팀 서비스 워커처럼 등록 → 상태 조회(2초마다) → 결과·관절점 파일 받기 → 지우기를 하고, 결과가 결과 JSON v1
(docs/analysisApi/resultFormat.md) 모양인지와 걸린 시간을 본다. 표준 라이브러리만 써서 서버·개발 PC 어디서든 돈다.

    ANALYSIS_API_KEY=... python check_server.py --url http://127.0.0.1:18010 --video data/videos/a.mp4
    python check_server.py --url ... --video a.mp4 --track data/tracks/fs-v4.track.json   # 미리 뽑은 관절점과 비교

- 키는 환경변수 ANALYSIS_API_KEY로만 받는다(명령 줄·로그에 남지 않게)
- 끝나면 만든 작업을 지운다(--keep이면 남긴다). 점검용 영상의 사본이 GPU 서버에 남지 않게 하려는 것이다
- --track을 주면 같은 영상(SHA-256, 없으면 파일 이름)의 미리 뽑은 관절점과 판정·통과 수·관절점 위치를 비교한다.
  모델 모드가 오프라인 추론과 같은 결과를 내는지 보는 것이다
- 하나라도 확인에 걸리면 끝 코드 1
"""
import argparse
import hashlib
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+/v\d+/([0-9a-f]{8}|unknown|sample)$")
VERSION_KEYS = {"angle_def", "gait_events", "validity", "gait_metrics", "joint_rom"}
RESULT_KEYS = {"id", "shot_id", "status", "model", "versions", "input", "validity", "validity_reason",
               "summary", "passes", "files", "created_at"}
PASS_KEYS = {"index", "start_frame", "end_frame", "heading", "camera_side", "gait", "valid", "reason_code",
             "reason", "measure_start", "measure_end", "metrics", "checks"}
METRIC_REASONS = {"NOT_ENOUGH_CYCLES", "LOW_CONFIDENCE"}
CONF = 0.3


# ---- 결과 모양 확인 (테스트가 직접 부른다) ----


def check_result(result: dict, keypoints: dict) -> list:
    """결과 JSON v1과 관절점 파일의 모양 확인. 걸린 것의 설명 목록(빈 목록이면 통과)"""
    problems = []
    missing = RESULT_KEYS - set(result)
    if missing:
        problems.append(f"결과에 없는 키: {sorted(missing)}")
    if not VERSION_RE.match(str((result.get("model") or {}).get("version", ""))):
        problems.append(f"model.version 형식이 다름: {(result.get('model') or {}).get('version')!r}")
    if not VERSION_KEYS <= set(result.get("versions") or {}):
        problems.append(f"versions에 없는 키: {sorted(VERSION_KEYS - set(result.get('versions') or {}))}")
    if result.get("validity") not in ("valid", "partial", "invalid"):
        problems.append(f"validity 값이 다름: {result.get('validity')!r}")

    passes = result.get("passes") or []
    used = sum(1 for p in passes if p.get("valid"))
    if result.get("summary") != {"passes": len(passes), "used": used, "excluded": len(passes) - used}:
        problems.append(f"summary가 통과와 맞지 않음: {result.get('summary')}")
    n = (result.get("input") or {}).get("frames")
    for p in passes:
        tag = f"통과 {p.get('index')}"
        if PASS_KEYS - set(p):
            problems.append(f"{tag}: 없는 키 {sorted(PASS_KEYS - set(p))}")
            continue
        if p["valid"] != (p["reason_code"] is None):
            problems.append(f"{tag}: valid와 reason_code가 맞지 않음")
        if not (0 <= p["start_frame"] <= p["end_frame"] < (n or 10 ** 9)):
            problems.append(f"{tag}: 프레임 범위가 영상 밖")
        if not p["valid"] and p["metrics"]:
            problems.append(f"{tag}: 제외된 통과에 수치가 있음")
        for key, item in (p["metrics"] or {}).items():
            if key == "stifle_cycle_rom" and isinstance(item.get("values"), list):
                continue
            if item.get("value") is None:
                if item.get("reason") not in METRIC_REASONS:
                    problems.append(f"{tag}: {key} 측정 불가 사유가 다름 {item.get('reason')!r}")
            elif not isinstance(item.get("value"), (int, float)) or not item.get("unit"):
                problems.append(f"{tag}: {key} 값 모양이 다름 {item}")

    frames = keypoints.get("frames") or []
    if n is not None and len(frames) != n:
        problems.append(f"관절점 파일 프레임 수({len(frames)})가 input.frames({n})와 다름")
    if [f.get("frame") for f in frames] != list(range(len(frames))):
        problems.append("관절점 파일 frame 번호가 0부터 빠짐 없이 이어지지 않음")
    for f in frames:
        if f.get("points") is not None and len(f["points"]) != 22:
            problems.append(f"프레임 {f.get('frame')}: 관절점이 22개가 아님")
            break
        side = f.get("camera_side")
        suffix = {"right": "_r", "left": "_l"}.get(side)
        if f.get("angles") and (suffix is None or not all(k.endswith(suffix) for k in f["angles"])):
            problems.append(f"프레임 {f.get('frame')}: 각도 키가 카메라 쪽({side})과 맞지 않음")
            break
    return problems


def compare_with_track(result: dict, keypoints: dict, track_video: dict) -> dict:
    """서버 결과와 미리 뽑은 관절점(같은 영상)을 비교한다. 판정은 같은 엔진이 돌므로, 관절점이 같으면 같아야 한다"""
    diffs = []
    for got, ref in zip(keypoints.get("frames") or [], track_video.get("frames") or []):
        if not got.get("points") or not ref:
            continue
        for a, b in zip(got["points"], ref["kp"]):
            if a[2] >= CONF and b[2] >= CONF:
                diffs.append(math.hypot(a[0] - b[0], a[1] - b[1]))
    found_got = sum(1 for f in keypoints.get("frames") or [] if f.get("points"))
    found_ref = sum(1 for f in track_video.get("frames") or [] if f)
    return {
        "frames": (len(keypoints.get("frames") or []), len(track_video.get("frames") or [])),
        "dog_found": (found_got, found_ref),
        "point_diff_px_median": round(statistics.median(diffs), 2) if diffs else None,
        "point_diff_px_p95": round(statistics.quantiles(diffs, n=20)[-1], 2) if len(diffs) > 1 else None,
    }


# ---- HTTP (표준 라이브러리만) ----


class Server:
    def __init__(self, url: str, key: str):
        self.url, self.key = url.rstrip("/"), key

    def call(self, method: str, path: str, body: Optional[bytes] = None, ctype: Optional[str] = None):
        req = urllib.request.Request(self.url + path, data=body, method=method)
        if self.key:
            req.add_header("X-API-Key", self.key)
        if ctype:
            req.add_header("Content-Type", ctype)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, None

    def submit(self, video: Path, shot_id: str):
        boundary = uuid.uuid4().hex
        meta = json.dumps({"shot_id": shot_id}).encode()
        parts = [
            f'--{boundary}\r\nContent-Disposition: form-data; name="meta"\r\n\r\n'.encode() + meta + b"\r\n",
            (f'--{boundary}\r\nContent-Disposition: form-data; name="video"; filename="{video.name}"\r\n'
             f"Content-Type: video/mp4\r\n\r\n").encode() + video.read_bytes() + b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
        return self.call("POST", "/analyses", b"".join(parts), f"multipart/form-data; boundary={boundary}")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_video(server: Server, video: Path, args, track: Optional[dict]) -> dict:
    row = {"video": video.name, "ok": False, "problems": []}
    started = time.monotonic()
    status, body = server.submit(video, f"check-{uuid.uuid4().hex[:8]}")
    if status != 202:
        row["problems"].append(f"등록 {status}: {body}")
        return row
    job_id = body["id"]
    row["submit_s"] = round(time.monotonic() - started, 1)
    state = None
    while time.monotonic() - started < args.timeout:
        _, state = server.call("GET", f"/analyses/{job_id}")
        if state and state.get("status") in ("done", "failed"):
            break
        time.sleep(2)
    row["total_s"] = round(time.monotonic() - started, 1)
    row["status"] = state and state.get("status")
    if row["status"] != "done":
        row["problems"].append(f"done이 아님: {state and (state.get('status'), state.get('error'))}")
    else:
        _, result = server.call("GET", f"/analyses/{job_id}/result")
        _, keypoints = server.call("GET", f"/analyses/{job_id}/files/keypoints")
        row["problems"] += check_result(result, keypoints)
        row.update(model=result["model"].get("version"), validity=result["validity"],
                   passes=result["summary"], frames=result["input"].get("frames"),
                   fps=result["input"].get("fps"))
        if row["total_s"] and row.get("frames"):
            row["fps_processed"] = round(row["frames"] / row["total_s"], 1)
        if track is not None:
            ref = track.get(_sha256(video)) or track.get(video.name)
            row["track"] = compare_with_track(result, keypoints, ref) if ref else "관절점 파일에 이 영상이 없음"
    if not args.keep:
        code, _ = server.call("DELETE", f"/analyses/{job_id}")
        if code not in (204, 404):
            row["problems"].append(f"지우기 {code}")
    row["ok"] = not row["problems"]
    return row


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="떠 있는 분석 API 점검 (S15P31A404-258)")
    parser.add_argument("--url", required=True, help="분석 API 주소 (예: http://127.0.0.1:18010)")
    parser.add_argument("--video", action="append", required=True, help="점검할 영상 (여러 번 줄 수 있음)")
    parser.add_argument("--track", help="같은 영상의 미리 뽑은 관절점 파일 (비교용)")
    parser.add_argument("--timeout", type=float, default=900, help="영상 하나를 기다리는 최대 초")
    parser.add_argument("--keep", action="store_true", help="점검한 작업을 지우지 않는다")
    args = parser.parse_args(argv)

    server = Server(args.url, os.environ.get("ANALYSIS_API_KEY", ""))
    code, health = server.call("GET", "/health")
    print(f"health {code}: {json.dumps(health, ensure_ascii=False)}")
    if code != 200 or not health or not health.get("model_known"):
        print("health가 정상이 아니거나 model_known이 false입니다. 모델 파일·models.yaml을 확인하세요", file=sys.stderr)
        return 1

    track = None
    if args.track:
        data = json.loads(Path(args.track).read_text(encoding="utf-8"))
        track = {}
        for v in data["videos"]:
            if v.get("sha256"):
                track[v["sha256"]] = v
            track.setdefault(Path(v["video"]).name, v)

    rows = [check_video(server, Path(v), args, track) for v in args.video]
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    bad = [r for r in rows if not r["ok"]]
    print(f"영상 {len(rows)}개 중 통과 {len(rows) - len(bad)}개")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
