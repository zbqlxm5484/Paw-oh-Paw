"""결과 영상 만들기(7절 "결과 영상 만들기", 11.3 순수 함수, 17.3 BE-12): 관절점 파일 읽기, 골격 그리기, ffmpeg 인코딩.

인코딩 테스트는 ffmpeg(FFMPEG_PATH)로 1초짜리 검은 영상을 만들어 쓴다. ffmpeg가 없으면 그 테스트만 건너뛴다.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from app.clients.analysis import load_fixture
from app.core.config import get_settings
from app.video.render import (
    BODY_POINTS,
    KEYPOINT_COUNT,
    LEFT_POINTS,
    RIGHT_POINTS,
    SKELETON,
    VideoRenderError,
    draw_skeleton,
    limb_of,
    load_keypoints,
    parse_keypoints,
    render_video,
    visible_points,
)

# ---- 관절점 파일 ----


def test_fixture_keypoints_are_parsed() -> None:
    keypoints = parse_keypoints(load_fixture("keypoints"))
    assert (keypoints.width, keypoints.height, keypoints.fps) == (1920, 1080, 59.94)
    assert sorted(keypoints.frames) == [40, 41]  # 42번은 points가 null(개 없음)이라 들어 있지 않다
    assert len(keypoints.frames[40].points) == KEYPOINT_COUNT
    assert keypoints.frames[40].points[0] == (612.0, 402.0) and keypoints.frames[41].points[0] == (620.5, 402.0)
    assert keypoints.frames[40].camera_side == keypoints.frames[41].camera_side == "right"


def test_points_without_confidence_or_below_threshold() -> None:
    points: list[Any] = [[3, 4]] * KEYPOINT_COUNT  # 신뢰도가 없으면 1.0으로 본다
    points[0] = [1, 2, 0.1]  # MIN_CONFIDENCE 미만 → 못 찾은 점
    points[1] = [1, "2", 0.9]  # 숫자가 아니면 못 찾은 점
    points[2] = [True, 2, 0.9]  # bool도 숫자로 보지 않는다
    keypoints = parse_keypoints({"frames": [{"frame": 7, "points": points}]})
    frame = keypoints.frames[7].points
    assert frame[0] is None and frame[1] is None and frame[2] is None and frame[3] == (3.0, 4.0)
    assert keypoints.width is None and keypoints.fps is None
    assert keypoints.frames[7].camera_side is None  # camera_side가 없으면 판정 못 한 것으로 본다


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("right", "right"), ("LEFT", "left"), ("Right", "right"), (None, None), ("up", None), (5, None)],
)
def test_camera_side_is_normalised(raw: Any, expected: str | None) -> None:
    keypoints = parse_keypoints({"frames": [{"frame": 0, "camera_side": raw, "points": [[1, 2]] * KEYPOINT_COUNT}]})
    assert keypoints.frames[0].camera_side == expected


def test_visible_points_follow_the_camera_side() -> None:
    # 세부명세서 PR-F01-04: 카메라 반대쪽 다리는 쓰지 않는다. 몸통은 귀 둘·등 가운데·엉덩이 위
    assert BODY_POINTS == {0, 1, 2, 13}
    assert LEFT_POINTS == set(range(3, 8)) | set(range(14, 18)) and RIGHT_POINTS == set(range(8, 13)) | set(
        range(18, 22)
    )
    assert visible_points("right") == BODY_POINTS | RIGHT_POINTS
    assert visible_points("left") == BODY_POINTS | LEFT_POINTS
    assert visible_points(None) == BODY_POINTS


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"frames": None},
        {"frames": [1]},
        {"frames": [{"frame": -1, "points": None}]},
        {"frames": [{"frame": 1.5, "points": None}]},
        {"frames": [{"frame": "0", "points": None}]},
        {"frames": [{"frame": 0, "points": [[1, 2]] * (KEYPOINT_COUNT - 1)}]},
        {"frames": [{"frame": 0, "points": "x"}]},
    ],
)
def test_malformed_keypoints_are_rejected(data: Any) -> None:
    with pytest.raises(VideoRenderError):
        parse_keypoints(data)


def test_unreadable_keypoints_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(VideoRenderError):
        load_keypoints(tmp_path / "missing.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(VideoRenderError):
        load_keypoints(broken)


def test_skeleton_covers_all_points_and_limbs_match_label_guide() -> None:
    # 연결은 22점(0~21)을 모두 쓴다. 다리 번호는 라벨 기준서 1장: 왼앞 3~7, 오른앞 8~12, 왼뒤 14~17, 오른뒤 18~21
    assert {index for edge in SKELETON for index in edge} == set(range(KEYPOINT_COUNT))
    assert [limb_of(i) for i in (0, 2, 13)] == ["BODY"] * 3
    assert limb_of(3) == limb_of(7) == "LF" and limb_of(8) == limb_of(12) == "RF"
    assert limb_of(14) == limb_of(17) == "LH" and limb_of(18) == limb_of(21) == "RH"


# ---- 그리기 ----


# 시험 프레임 크기. 점 22개를 두 줄로 두면 점 사이가 12px라 점(반지름 4)과 테두리가 서로 덮지 않는다
WIDTH, HEIGHT = 160, 120


def _grid_points(width: int = WIDTH, height: int = HEIGHT) -> list[tuple[float, float]]:
    """22점을 프레임 안에 두 줄로 퍼뜨린다."""
    return [(width * (0.1 + 0.075 * (i % 11)), height * (0.3 if i < 11 else 0.7)) for i in range(KEYPOINT_COUNT)]


def test_draw_skeleton_marks_points_and_skips_missing_ones() -> None:
    frame = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    points: list[tuple[float, float] | None] = list(_grid_points())
    points[5] = None
    assert draw_skeleton(frame, points) == KEYPOINT_COUNT - 1
    x, y = points[0]
    assert tuple(frame[round(y), round(x)]) == (255, 255, 255)  # 0번(귀)은 몸통 색(흰색)
    x, y = points[7]
    assert tuple(frame[round(y), round(x)]) == (80, 220, 80)  # 7번(왼쪽 앞발끝)은 왼쪽 앞다리 색
    blank = np.zeros_like(frame)
    assert draw_skeleton(blank, [None] * KEYPOINT_COUNT) == 0 and not blank.any()


def test_draw_skeleton_draws_only_the_visible_points() -> None:
    # 0번(귀, 몸통)·7번(왼쪽 앞발끝)·12번(오른쪽 앞발끝)만 있는 프레임. 오른쪽이 카메라 쪽이면 7번은 그리지 않는다
    frame = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    points: list[tuple[float, float] | None] = [None] * KEYPOINT_COUNT
    points[0], points[7], points[12] = (80.0, 20.0), (40.0, 60.0), (120.0, 60.0)
    assert draw_skeleton(frame, points, visible=visible_points("right")) == 2
    assert frame[20, 80].any() and frame[60, 120].any() and not frame[60, 40].any()
    body_only = np.zeros_like(frame)
    assert draw_skeleton(body_only, points, visible=visible_points(None)) == 1
    assert body_only[20, 80].any() and not body_only[60, 120].any() and not body_only[60, 40].any()


def test_draw_skeleton_scales_from_keypoint_coordinates_to_the_frame() -> None:
    # 관절점 파일은 1280x960 좌표계, 프레임은 160x120 → 비율 0.125
    frame = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    points: list[tuple[float, float] | None] = [(400.0, 400.0)] + [None] * (KEYPOINT_COUNT - 1)
    assert draw_skeleton(frame, points, scale=(0.125, 0.125)) == 1
    assert frame[50, 50].any() and not frame[100, 100].any() and not frame[2, 2].any()


# ---- 인코딩 (ffmpeg 필요) ----


@pytest.fixture(scope="module")
def ffmpeg() -> str:
    path = get_settings().FFMPEG_PATH
    try:
        subprocess.run([path, "-version"], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("ffmpeg가 없어 인코딩 테스트를 건너뛴다(FFMPEG_PATH)")
    return path


@pytest.fixture(scope="module")
def black_video(ffmpeg: str, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """160x120, 10fps, 1초(10프레임) 검은 영상."""
    path = tmp_path_factory.mktemp("src") / "black.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={WIDTH}x{HEIGHT}:r=10:d=1"]
        + ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        check=True,
        capture_output=True,
    )
    return path


def write_keypoints(
    path: Path,
    frames: dict[int, list[Any] | None],
    *,
    width: int = WIDTH,
    height: int = HEIGHT,
    camera_side: str | None = "left",
) -> Path:
    data = {
        "width": width,
        "height": height,
        "fps": 10,
        "frames": [{"frame": n, "camera_side": camera_side, "points": pts} for n, pts in frames.items()],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _probe(ffmpeg: str, path: Path) -> list[dict[str, Any]]:
    ffprobe = get_settings().FFPROBE_PATH
    completed = subprocess.run(
        [ffprobe, "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(path)],
        check=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)["streams"]


def _decode(path: Path) -> list[np.ndarray]:
    capture = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(frame)
    capture.release()
    return frames


def test_render_video_draws_the_frames_that_have_keypoints(black_video: Path, ffmpeg: str, tmp_path: Path) -> None:
    grid = [list(p) + [0.9] for p in _grid_points()]
    keypoints = write_keypoints(tmp_path / "keypoints.json", {0: grid, 3: grid, 7: None})
    output = tmp_path / "result.mp4"

    result = render_video(black_video, keypoints, output, ffmpeg_path=ffmpeg)

    assert (result.frames, result.drawn_frames, result.width, result.height) == (10, 2, WIDTH, HEIGHT)
    assert result.fps == 10.0
    assert result.bytes == output.stat().st_size > 0
    streams = _probe(ffmpeg, output)
    assert [s["codec_type"] for s in streams] == ["video"]  # 소리 없음
    assert streams[0]["codec_name"] == "h264" and streams[0]["pix_fmt"] == "yuv420p"
    assert streams[0]["nb_read_frames"] == "10"
    decoded = _decode(output)
    assert len(decoded) == 10
    assert int(decoded[0].max()) > 100 and int(decoded[3].max()) > 100  # 골격을 그린 프레임
    assert int(decoded[5].max()) < 40  # 안 그린 프레임은 검은 그대로(인코딩 잡음만)
    assert (tmp_path / "ffmpeg.log").is_file()


def test_render_video_scales_keypoints_of_a_different_size(black_video: Path, ffmpeg: str, tmp_path: Path) -> None:
    # 관절점 파일이 1280x960 좌표계면 160x120 프레임에 맞춰 1/8로 줄여 그린다. 점 하나만 두어 테두리끼리 덮지 않게 한다
    x, y = _grid_points()[0]
    big: list[Any] = [[x * 8, y * 8, 0.9]] + [None] * (KEYPOINT_COUNT - 1)
    keypoints = write_keypoints(tmp_path / "keypoints.json", {0: big}, width=1280, height=960)
    result = render_video(black_video, keypoints, tmp_path / "result.mp4", ffmpeg_path=ffmpeg)
    assert result.drawn_frames == 1
    first = _decode(tmp_path / "result.mp4")[0]
    assert int(first[round(y), round(x)].min()) > 180  # 흰 점의 가운데(인코딩 손실만큼만 어둡다)
    assert int(first[round(y) + 20, round(x) + 20].max()) < 40


def test_render_video_skips_the_far_side_limbs(black_video: Path, ffmpeg: str, tmp_path: Path) -> None:
    # 7번(왼쪽 앞발끝)과 12번(오른쪽 앞발끝)만 있는 프레임. camera_side가 right면 결과 영상에 12번만 보인다
    points: list[Any] = [None] * KEYPOINT_COUNT
    points[7], points[12] = [40, 60, 0.9], [120, 60, 0.9]
    keypoints = write_keypoints(tmp_path / "keypoints.json", {0: points}, camera_side="right")
    result = render_video(black_video, keypoints, tmp_path / "result.mp4", ffmpeg_path=ffmpeg)
    assert result.drawn_frames == 1
    first = _decode(tmp_path / "result.mp4")[0]
    assert int(first[60, 120].max()) > 100 and int(first[60, 40].max()) < 40


def test_render_video_rejects_an_unreadable_input(ffmpeg: str, tmp_path: Path) -> None:
    not_video = tmp_path / "text.mp4"
    not_video.write_text("hello", encoding="utf-8")
    keypoints = write_keypoints(tmp_path / "keypoints.json", {})
    with pytest.raises(VideoRenderError):
        render_video(not_video, keypoints, tmp_path / "result.mp4", ffmpeg_path=ffmpeg)


def test_render_video_reports_a_missing_ffmpeg(black_video: Path, tmp_path: Path) -> None:
    keypoints = write_keypoints(tmp_path / "keypoints.json", {})
    with pytest.raises(VideoRenderError, match="FFMPEG_PATH"):
        render_video(black_video, keypoints, tmp_path / "result.mp4", ffmpeg_path=str(tmp_path / "no-ffmpeg"))


def test_render_video_reports_ffmpeg_failure_without_paths(black_video: Path, tmp_path: Path) -> None:
    # 종료 코드가 0이 아닌 가짜 ffmpeg. 표준 오류에 출력 경로(마지막 인자)를 찍어도 메시지에는 남지 않는다(11.8)
    if os.name == "nt":
        fake = tmp_path / "ffmpeg.cmd"
        lines = ["@echo off", "set last=", ":loop", 'if "%~1"=="" goto done', "set last=%~1", "shift", "goto loop"]
        lines += [":done", "echo Error opening output %last% 1>&2", "exit /b 3"]
        fake.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    else:
        fake = tmp_path / "ffmpeg.sh"
        fake.write_text('#!/bin/sh\nfor last; do :; done\necho "Error opening output $last" 1>&2\nexit 3\n')
        fake.chmod(0o755)
    keypoints = write_keypoints(tmp_path / "keypoints.json", {})
    output = tmp_path / "result.mp4"
    with pytest.raises(VideoRenderError, match="종료 코드 3") as info:
        render_video(black_video, keypoints, output, ffmpeg_path=str(fake))
    assert str(tmp_path) not in str(info.value) and "<path>" in str(info.value)
