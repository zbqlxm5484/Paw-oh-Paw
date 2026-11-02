"""scripts/measure_render.py(S15P31A404-193): 합성 관절점과 세 방식 측정이 돈다. ffmpeg가 없으면 건너뛴다."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.video import render
from scripts.measure_render import MODES, bench_detector, measure, synthetic_keypoints, table

WIDTH, HEIGHT, FRAMES = 64, 48, 10


@pytest.fixture(scope="module")
def ffmpeg() -> str:
    path = get_settings().FFMPEG_PATH
    if not (shutil.which(path) or Path(path).is_file()):
        pytest.skip("ffmpeg가 없어 측정 테스트를 건너뛴다(FFMPEG_PATH)")
    return path


@pytest.fixture(scope="module")
def tiny_video(ffmpeg: str, tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("measure") / "tiny.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={WIDTH}x{HEIGHT}:r=10:d=1"]
        + ["-pix_fmt", "yuv420p", str(path)],
        check=True,
    )
    return path


class _NoFace:
    calls = 0

    def detect(self, frame):
        self.calls += 1
        return []


def test_synthetic_keypoints_cover_every_frame_with_22_points(tiny_video: Path, tmp_path: Path) -> None:
    path = synthetic_keypoints(tiny_video, tmp_path / "k.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert (data["width"], data["height"], data["fps"]) == (WIDTH, HEIGHT, 10.0)
    assert [f["frame"] for f in data["frames"]] == list(range(FRAMES))
    assert all(len(f["points"]) == render.KEYPOINT_COUNT for f in data["frames"])
    parsed = render.parse_keypoints(data)
    assert len(parsed.frames) == FRAMES


def test_measure_runs_the_three_modes_and_every_mode_calls_the_detector_per_frame(
    tiny_video: Path, ffmpeg: str, tmp_path: Path
) -> None:
    keypoints = synthetic_keypoints(tiny_video, tmp_path / "k.json")
    detector = _NoFace()
    timings = measure(tiny_video, keypoints, tmp_path, ffmpeg=ffmpeg, modes=MODES, make_detector=lambda: detector)

    assert [t.mode for t in timings] == list(MODES)
    assert all(t.result.frames == FRAMES and t.seconds > 0 for t in timings)
    # interval: 10fps·0.05초 → 매 프레임이라 10번, every: 10번. skeleton은 검출기를 부르지 않는다
    assert detector.calls == 2 * FRAMES
    assert render.detect_interval_frames(10.0) == 1  # every 모드가 원래 함수를 되돌려 놓았다
    assert {p.name for p in tmp_path.glob("*.mp4")} == {"skeleton.mp4", "interval.mp4", "every.mp4"}

    text = table(tiny_video, timings)
    assert "| skeleton |" in text and "| every |" in text and "tiny.mp4" in text


def test_unknown_mode_is_rejected(tiny_video: Path, ffmpeg: str, tmp_path: Path) -> None:
    keypoints = synthetic_keypoints(tiny_video, tmp_path / "k.json")
    with pytest.raises(SystemExit):
        measure(tiny_video, keypoints, tmp_path, ffmpeg=ffmpeg, modes=["blur"], make_detector=_NoFace)


def test_bench_detector_counts_calls_after_a_warmup(tiny_video: Path) -> None:
    detector = _NoFace()
    low, mid, high = bench_detector(tiny_video, 5, make_detector=lambda: detector)
    assert detector.calls == 6 and 0 <= low <= mid <= high
