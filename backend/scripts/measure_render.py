"""결과 영상 처리 시간 측정(S15P31A404-193, 명세 7절·12.4).

원본 영상 하나를 `render_video`로 세 방식으로 만들어 시간을 잰다.
- skeleton: 골격만 그리고 얼굴 검출은 안 한다(디코드 + 그리기 + 인코딩의 바닥값)
- interval: 서비스 기본값. FACE_DETECT_INTERVAL_SEC(0.05초)마다 검출하고 사이 프레임은 추적으로 가린다
- every: 매 프레임 검출(검출 비용의 상한)

    python -m scripts.measure_render <video.mp4> [--keypoints k.json] [--out DIR] [--repeat N] [--modes a,b,c]

관절점 파일이 없으면 영상의 프레임 수·크기에 맞춘 합성 관절점(22점, 카메라 오른쪽, 모든 프레임)을 만들어 쓴다.
그리는 비용은 점의 위치와 무관하므로 시간 측정에는 충분하다. ffmpeg는 `.env`의 FFMPEG_PATH다.
결과는 마크다운 표로 찍어 docs/report/renderTiming.md에 그대로 붙인다. 경로는 파일 이름만 찍는다(11.8).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2

from app.core.config import get_settings
from app.video import render
from app.video.render import KEYPOINT_COUNT, FaceDetector, RenderResult, render_video

MODES = ("skeleton", "interval", "every")
FaceFinder = Callable[[Any], list]


@dataclass(frozen=True)
class Timing:
    mode: str
    seconds: float
    result: RenderResult

    @property
    def ms_per_frame(self) -> float:
        return self.seconds * 1000 / max(self.result.frames, 1)


def video_info(video: Path) -> tuple[float, int, int, int]:
    """(fps, 너비, 높이, 프레임 수). 프레임 수는 컨테이너 값이라 실제와 한두 장 다를 수 있다."""
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise SystemExit(f"영상을 열지 못했습니다: {video.name}")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    return fps, width, height, frames


def synthetic_keypoints(video: Path, out: Path) -> Path:
    """프레임마다 22점을 가진 관절점 파일(6절 형식)을 만든다. 점은 화면 가운데를 천천히 가로지른다."""
    fps, width, height, frames = video_info(video)
    rows = []
    for n in range(frames):
        shift = (n / max(frames, 1)) * width * 0.5
        points = [
            [
                round(width * 0.25 + shift + (i % 6) * width * 0.04, 1),
                round(height * 0.35 + (i // 6) * height * 0.12, 1),
                0.9,
            ]
            for i in range(KEYPOINT_COUNT)
        ]
        rows.append({"frame": n, "camera_side": "right", "points": points, "angles": {}})
    data = {
        "angle_def": "v1",
        "fps": fps,
        "width": width,
        "height": height,
        "keypoint_order": "PRD 6.5.3 (0-21)",
        "frames": rows,
    }
    out.write_text(json.dumps(data), encoding="utf-8")
    return out


@contextmanager
def _detect_every_frame():
    """every 모드: render_video가 쓰는 간격 함수를 잠깐 1프레임으로 바꾼다(측정용. 서비스 코드는 그대로)."""
    original = render.detect_interval_frames
    render.detect_interval_frames = lambda fps, interval_sec=None: 1  # type: ignore[assignment]
    try:
        yield
    finally:
        render.detect_interval_frames = original


def measure(
    video: Path,
    keypoints: Path,
    out_dir: Path,
    *,
    ffmpeg: str,
    modes: Iterable[str] = MODES,
    repeat: int = 1,
    make_detector: Callable[[], Any] = FaceDetector,
) -> list[Timing]:
    """방식마다 repeat번 돌려 가장 짧은 시간을 돌려준다(다른 일이 끼어든 영향을 뺀다)."""
    timings: list[Timing] = []
    detector: Any = None
    for mode in modes:
        if mode not in MODES:
            raise SystemExit(f"모르는 방식: {mode} (가능: {', '.join(MODES)})")
        best: Timing | None = None
        for _ in range(max(repeat, 1)):
            finder: FaceFinder | None
            if mode == "skeleton":
                finder = lambda frame: []  # noqa: E731
            else:
                detector = detector or make_detector()
                finder = detector.detect
            output = out_dir / f"{mode}.mp4"
            started = time.perf_counter()
            if mode == "every":
                with _detect_every_frame():
                    result = render_video(video, keypoints, output, ffmpeg_path=ffmpeg, detect_faces=finder)
            else:
                result = render_video(video, keypoints, output, ffmpeg_path=ffmpeg, detect_faces=finder)
            elapsed = time.perf_counter() - started
            if best is None or elapsed < best.seconds:
                best = Timing(mode, elapsed, result)
        assert best is not None
        timings.append(best)
    return timings


def bench_detector(
    video: Path, calls: int = 20, *, make_detector: Callable[[], Any] = FaceDetector
) -> tuple[float, float, float]:
    """영상 첫 프레임에 얼굴 검출기만 calls번 불러 (최소, 중앙값, 최대) ms를 돌려준다.

    인코딩·그리기와 분리한 검출 비용이다.
    """
    capture = cv2.VideoCapture(str(video))
    ok, frame = capture.read()
    capture.release()
    if not ok or frame is None:
        raise SystemExit(f"영상에서 프레임을 읽지 못했습니다: {video.name}")
    cv2.setNumThreads(1)  # render_video와 같은 조건(12.4)
    detector = make_detector()
    detector.detect(frame)  # 첫 호출은 모델 준비가 섞이므로 뺀다
    samples = []
    for _ in range(max(calls, 1)):
        started = time.perf_counter()
        detector.detect(frame)
        samples.append((time.perf_counter() - started) * 1000)
    return min(samples), statistics.median(samples), max(samples)


def table(video: Path, timings: list[Timing]) -> str:
    fps, width, height, _ = video_info(video)
    base = next((t for t in timings if t.mode == "skeleton"), None)
    lines = [
        f"영상 `{video.name}`: {width}x{height} {fps:g}fps, 검출 간격 {render.detect_interval_frames(fps)}프레임",
        "",
        "| 방식 | 프레임 | 얼굴 가린 프레임 | 전체(초) | 프레임당(ms) | 골격 대비 추가(초) | 결과 크기(MB) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for t in timings:
        extra = f"{t.seconds - base.seconds:.1f}" if base and t is not base else "-"
        lines.append(
            f"| {t.mode} | {t.result.frames} | {t.result.face_frames} | {t.seconds:.1f} "
            f"| {t.ms_per_frame:.0f} | {extra} | {t.result.bytes / 1_048_576:.1f} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="결과 영상 처리 시간 측정")
    parser.add_argument("video", type=Path)
    parser.add_argument("--keypoints", type=Path, default=None, help="관절점 파일. 없으면 합성한다")
    parser.add_argument("--out", type=Path, default=Path("data/tmp/measure_render"), help="결과 영상을 둘 폴더")
    parser.add_argument("--repeat", type=int, default=1, help="방식마다 반복 횟수(가장 짧은 값을 쓴다)")
    parser.add_argument("--modes", default=",".join(MODES), help="쉼표로 구분: skeleton,interval,every")
    parser.add_argument("--bench-detector", type=int, default=0, metavar="N", help="검출기만 N번 불러 ms를 잰다")
    args = parser.parse_args(argv)

    if args.bench_detector:
        fps, width, height, _ = video_info(args.video)
        low, mid, high = bench_detector(args.video, args.bench_detector)
        print(
            f"검출기 `{args.video.name}` {width}x{height}: {args.bench_detector}회, "
            f"ms 최소 {low:.0f} 중앙값 {mid:.0f} 최대 {high:.0f}"
        )
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    keypoints = args.keypoints or synthetic_keypoints(args.video, args.out / "keypoints.json")
    ffmpeg = get_settings().FFMPEG_PATH
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    timings = measure(args.video, keypoints, args.out, ffmpeg=ffmpeg, modes=modes, repeat=args.repeat)
    print(table(args.video, timings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
