"""얼굴 가리기(7절 2번, BE-12, Jira 150): 모자이크·검출 유지·골격과의 순서·BlazeFace 모델·render_video 연결."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from app.core.config import get_settings
from app.video.render import (
    BODY,
    COLORS,
    FACE_INPUT_SIZE,
    FACE_MODEL_PATH,
    KEYPOINT_COUNT,
    Box,
    FaceDetector,
    FaceTracker,
    FramePoints,
    VideoRenderError,
    _anchor_centers,
    _nms,
    _tiles,
    blur_faces,
    detect_interval_frames,
    process_frame,
    render_video,
)

WIDTH, HEIGHT = 160, 120
FACE: Box = (60, 40, 100, 70)  # 40x30 상자. margin 0.3이면 (48, 31, 112, 79)로 넓어진다
WIDENED = (48, 31, 112, 79)


def _noise(seed: int = 1) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, 256, (HEIGHT, WIDTH, 3), dtype=np.uint8)


def _variance(region: np.ndarray) -> float:
    """픽셀 값의 분산. 잡음은 크고(0~255면 5461쯤), 모자이크·흐림은 거의 0이다."""
    return float(region.astype(np.float64).var())


def _region(frame: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = box
    return frame[y0:y1, x0:x1]


# ---- 모자이크 ----


def test_blur_faces_mosaics_the_widened_box_and_leaves_the_rest(tmp_path: Path) -> None:
    original = _noise()
    frame = original.copy()

    assert blur_faces(frame, [FACE]) == 1

    inside, before = _region(frame, WIDENED), _region(original, WIDENED)
    assert _variance(before) > 4000
    assert _variance(inside) < _variance(before) / 50  # 몇 칸짜리 모자이크는 거의 평평하다
    mask = np.ones((HEIGHT, WIDTH), dtype=bool)
    mask[WIDENED[1] : WIDENED[3], WIDENED[0] : WIDENED[2]] = False
    assert np.array_equal(frame[mask], original[mask])  # 넓힌 상자 밖은 그대로


def test_blur_faces_clips_at_the_frame_edge_and_skips_empty_boxes() -> None:
    original = _noise()
    frame = original.copy()
    boxes: list[Box] = [(-20, -20, 30, 30), (200, 200, 300, 300), (10, 10, 10, 30), (WIDTH - 5, HEIGHT - 5, 400, 400)]

    assert blur_faces(frame, boxes) == 2  # 모서리에 걸친 둘만. 밖에 있거나 너비가 0인 상자는 건너뛴다

    assert _variance(frame[0:30, 0:30]) < _variance(original[0:30, 0:30]) / 50
    assert not np.array_equal(frame[HEIGHT - 5 :, WIDTH - 5 :], original[HEIGHT - 5 :, WIDTH - 5 :])
    # 첫 상자는 (0,0,45,45), 넷째 상자는 넓혀서 (81,29,160,120)까지다. 그 둘에 닿지 않는 곳은 그대로
    assert np.array_equal(frame[50:110, 0:70], original[50:110, 0:70])


def test_blur_faces_with_no_boxes_changes_nothing() -> None:
    original = _noise()
    frame = original.copy()
    assert blur_faces(frame, []) == 0 and np.array_equal(frame, original)


# ---- 검출 유지 ----


def test_face_tracker_keeps_a_lost_face_for_hold_frames() -> None:
    tracker = FaceTracker(2)
    assert tracker.update([FACE]) == [FACE]
    assert tracker.update([]) == [FACE]  # 1프레임 놓쳐도 가린다
    assert tracker.update([]) == [FACE]
    assert tracker.update([]) == []  # hold_frames가 지나면 사라진다

    instant = FaceTracker(0)
    assert instant.update([FACE]) == [FACE] and instant.update([]) == []


def test_face_tracker_drops_a_held_box_only_when_a_new_detection_covers_it() -> None:
    tracker = FaceTracker(3)
    again: Box = (59, 39, 101, 71)  # 같은 얼굴을 다시 찾았다. 묵은 상자를 다 덮는다
    moved: Box = (66, 44, 106, 74)  # 같은 얼굴이 조금 움직였다. 묵은 상자의 왼쪽·위쪽은 덮지 못한다
    far: Box = (0, 0, 20, 20)
    tracker.update([FACE])
    assert tracker.update([again]) == [again]  # 덮인 묵은 상자는 버린다(같은 자리를 두 번 가리지 않는다)
    assert tracker.update([moved]) == [moved, again]  # 덮지 못하면 둘 다 가린다
    assert tracker.update([far]) == [far, moved, again]  # 다른 자리도 둘 다


def test_face_tracker_keeps_a_held_face_when_a_neighbouring_box_only_overlaps_it() -> None:
    """시연 영상 제니 01번에서 본 일(277). 진짜 얼굴(16번 프레임)이 점수가 내려가 안 잡히는 동안, 옆의 작은 상자(22번
    프레임)가 조금 겹친다고 얼굴 상자를 밀어내면 그 얼굴이 드러난다. 고치기 전 규칙(작은 쪽 넓이의 절반이 겹치면
    대신한다)은 밀어냈고 얼굴이 8프레임 동안 드러났다.
    """
    face: Box = (790, 230, 843, 283)
    neighbour: Box = (773, 226, 812, 265)  # 겹침 22x35 = 770. 작은 쪽(39x39 = 1521)의 절반을 넘지만 얼굴의 27%뿐이다
    tracker = FaceTracker(15)
    tracker.update([face])
    for _ in range(6):
        assert face in tracker.update([])
    assert tracker.update([neighbour]) == [neighbour, face]  # 둘 다 가린다
    for _ in range(8):
        assert face in tracker.update([])  # 얼굴 상자는 제 유지 시간(15프레임)을 채운다
    assert face not in tracker.update([])


def test_face_tracker_remembers_where_a_sure_face_was() -> None:
    tracker = FaceTracker(1, 3)
    weak: Box = (62, 42, 98, 68)
    assert tracker.anchors() == []
    tracker.update([FACE])
    assert tracker.anchors() == [FACE]
    assert tracker.update([], [weak]) == [weak, FACE]  # 낮은 점수 검출도 가린다
    assert tracker.anchors() == [FACE]  # 자리는 확실한 검출의 것만 기억한다. 낮은 점수 검출은 넘겨받지 못한다
    tracker.update([])
    assert tracker.anchors() == [FACE]  # 검출 뒤 세 번째 프레임까지 쓸 수 있다
    tracker.update([])
    assert tracker.anchors() == []

    forgetful = FaceTracker(1)  # 기억할 시간을 주지 않으면 자리를 넘기지 않는다
    forgetful.update([FACE])
    assert forgetful.anchors() == []


# ---- 골격과 합치기 ----


@pytest.mark.parametrize(("fps", "every"), [(60, 3), (59.94, 3), (30, 2), (29.97, 2), (24, 2), (20, 1), (10, 1)])
def test_detect_interval_frames_is_the_smallest_count_covering_the_interval(fps: float, every: int) -> None:
    assert detect_interval_frames(fps) == every  # 0.05초 이상이 되는 가장 작은 프레임 수. 60 x 0.05의 부동소수 오차도 3


def test_process_frame_blurs_first_and_draws_the_skeleton_on_top() -> None:
    frame = _noise()
    points: list[Any] = [None] * KEYPOINT_COUNT
    points[2] = (80.0, 60.0)  # 2번(등 가운데, 몸통)이 얼굴 상자 안에 있다

    assert process_frame(frame, FramePoints(points, None), scale=(1.0, 1.0), faces=[FACE]) is True

    assert tuple(int(v) for v in frame[60, 80]) == COLORS[BODY]  # 점은 모자이크 위에 그려진다
    assert _variance(frame[31:40, 48:60]) < 100  # 점이 닿지 않는 상자 구석은 가려져 평평하다


def test_process_frame_blurs_even_when_there_are_no_keypoints() -> None:
    original = _noise()
    frame = original.copy()
    assert process_frame(frame, None, scale=(1.0, 1.0), faces=[FACE]) is False
    assert not np.array_equal(_region(frame, WIDENED), _region(original, WIDENED))


# ---- BlazeFace 모델·타일·앵커 ----


def test_bundled_model_is_present_with_its_license() -> None:
    assert FACE_MODEL_PATH.name == "face_detection_full_range.onnx"
    assert FACE_MODEL_PATH.is_file() and FACE_MODEL_PATH.stat().st_size > 1_000_000
    license_text = (FACE_MODEL_PATH.parent / "LICENSE").read_text(encoding="utf-8")
    assert "Apache License" in license_text and "Version 2.0" in license_text
    readme = (FACE_MODEL_PATH.parent / "README.md").read_text(encoding="utf-8")
    assert FACE_MODEL_PATH.name in readme and "SHA-256" in readme  # 출처와 검증값을 적어 둔다


def test_tiles_cover_the_frame_with_overlap() -> None:
    tiles = _tiles(1920, 1080)
    assert len(tiles) == 12  # 1080p는 4x3
    assert tiles[0] == (0, 0, 576, 432)  # 480x360에 사방 20%를 더하고 프레임 밖은 자른다
    assert tiles[-1] == (1344, 648, 1920, 1080)
    assert all(0 <= x0 < x1 <= 1920 and 0 <= y0 < y1 <= 1080 for x0, y0, x1, y1 in tiles)
    assert _tiles(160, 120) == [(0, 0, 160, 120)]  # 작은 프레임은 타일 하나


def test_anchor_centers_follow_the_48x48_grid() -> None:
    anchors = _anchor_centers()
    assert anchors.shape == (2304, 2)
    assert anchors[0].tolist() == pytest.approx([0.5 / 48, 0.5 / 48])
    assert anchors[1].tolist() == pytest.approx([1.5 / 48, 0.5 / 48])  # 열(x)이 안쪽에서 돈다
    assert anchors[48].tolist() == pytest.approx([0.5 / 48, 1.5 / 48])


def test_nms_merges_overlapping_boxes_and_keeps_the_rest() -> None:
    boxes = [[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]]
    assert _nms(boxes, [0.8, 0.9, 0.7], 0.3) == [1, 2]  # 겹치는 둘 중 점수 높은 것만, 떨어진 것은 그대로


class _FakeNet:
    """앵커 하나(24행 24열)에만 상자를 내는 가짜 모델. 상자 값은 (중심 x, 중심 y, 너비, 높이) = (0, 0, 48, 48)px."""

    def __init__(self, logit: float = 50.0) -> None:
        regressors = np.zeros((1, 2304, 16), dtype=np.float32)
        logits = np.full((1, 2304, 1), -50.0, dtype=np.float32)
        index = 24 * 48 + 24
        regressors[0, index, 2:4] = 48.0
        logits[0, index, 0] = logit  # 점수는 sigmoid(logit)
        self.outputs = [regressors, logits]

    def setInput(self, blob: np.ndarray) -> None:  # OpenCV의 메서드 이름 그대로
        assert blob.shape == (1, 3, FACE_INPUT_SIZE, FACE_INPUT_SIZE)

    def forward(self, names: Any) -> list[np.ndarray]:
        return self.outputs


def test_face_detector_maps_tile_boxes_back_to_the_frame() -> None:
    detector = FaceDetector(detect_width=200)
    detector._net = _FakeNet()
    (box,) = detector.detect(np.zeros((300, 400, 3), dtype=np.uint8))
    # 400x300 프레임 → 폭 200으로 줄임 → 타일 하나 → 200x200 정사각형(위아래 25px 채움). 앵커 중심 24.5/48 → 102.1px,
    # 너비 48/192 → 50px. 정사각형 (77.1, 77.1)~(127.1, 127.1) → 채움을 빼고 2배 → (154.2, 104.2)~(254.2, 204.2)
    assert box == (154, 104, 255, 205)


def test_face_detector_takes_a_low_score_only_where_a_face_was() -> None:
    """고개를 숙이거나 돌리면 같은 얼굴의 점수가 0.3~0.5로 내려간다(277). 얼굴이 있던 자리에서만 그 점수를 받아 준다."""
    detector = FaceDetector(detect_width=200)
    frame = np.zeros((300, 400, 3), dtype=np.uint8)
    box: Box = (154, 104, 255, 205)  # 위 시험과 같은 상자
    here: Box = (160, 110, 250, 200)
    elsewhere: Box = (0, 0, 60, 60)

    detector._net = _FakeNet(logit=-0.2)  # 점수 0.45
    assert detector.detect(frame) == []  # 새 얼굴로는 모자란다(0.5)
    assert detector.detect_tracked(frame, [here]) == ([], [box])  # 얼굴이 있던 자리와 겹치면 받는다(0.3)
    assert detector.detect(frame, [here]) == [box]
    assert detector.detect_tracked(frame, [elsewhere]) == ([], [])  # 다른 자리의 기억은 소용없다

    detector._net = _FakeNet(logit=-1.0)  # 점수 0.27
    assert detector.detect_tracked(frame, [here]) == ([], [])  # 얼굴이 있던 자리라도 버린다

    detector._net = _FakeNet()
    assert detector.detect_tracked(frame, [here]) == ([box], [])  # 확실한 검출은 확실한 쪽에 온다


def test_face_detector_finds_nothing_on_blank_frames() -> None:
    detector = FaceDetector()
    assert detector.detect(np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)) == []
    assert detector.detect(np.full((1080, 1920, 3), 90, dtype=np.uint8)) == []  # 4x3 타일 길


def test_face_detector_reports_a_missing_model(tmp_path: Path) -> None:
    with pytest.raises(VideoRenderError, match="모델"):
        FaceDetector(tmp_path / "missing.onnx")


# ---- render_video 연결 (ffmpeg 필요) ----


@pytest.fixture(scope="module")
def ffmpeg() -> str:
    path = get_settings().FFMPEG_PATH
    try:
        subprocess.run([path, "-version"], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("ffmpeg가 없어 인코딩 테스트를 건너뛴다(FFMPEG_PATH)")
    return path


def _texture_video(ffmpeg: str, path: Path, *, fps: int = 10, count: int = 10) -> Path:
    """160x120, fps·count 프레임(기본 10fps 10프레임). 4px 네모마다 색이 다른 무늬를 거의 무손실(qp 0)로 넣는다.

    검은 영상이나 ffmpeg 시험 무늬는 색이 몇 가지뿐이라 가린 자리가 드러나지 않는다. 이 무늬는 분산이 커서 드러난다.
    """
    frames = [
        cv2.resize(_noise(seed)[: HEIGHT // 4, : WIDTH // 4], (WIDTH, HEIGHT), interpolation=cv2.INTER_NEAREST)
        for seed in range(count)
    ]
    size = f"{WIDTH}x{HEIGHT}"
    command = [ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", size, "-framerate", str(fps)]
    command += ["-i", "-", "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(command, input=b"".join(frame.tobytes() for frame in frames), check=True, capture_output=True)
    return path


@pytest.fixture(scope="module")
def texture_video(ffmpeg: str, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _texture_video(ffmpeg, tmp_path_factory.mktemp("src") / "texture.mp4")


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


def _empty_keypoints(path: Path) -> Path:
    path.write_text(json.dumps({"width": WIDTH, "height": HEIGHT, "fps": 10, "frames": []}), encoding="utf-8")
    return path


def test_render_video_blurs_with_the_given_detector_and_holds_half_a_second(
    texture_video: Path, ffmpeg: str, tmp_path: Path
) -> None:
    seen = 0

    def detect(frame: np.ndarray) -> list[Box]:
        nonlocal seen
        seen += 1
        return [FACE] if seen <= 3 else []  # 처음 3프레임만 얼굴

    output = tmp_path / "result.mp4"
    result = render_video(
        texture_video, _empty_keypoints(tmp_path / "k.json"), output, ffmpeg_path=ffmpeg, detect_faces=detect
    )

    assert (result.frames, result.drawn_frames, result.face_frames) == (10, 0, 8)  # 3 + 10fps x 0.5초 유지
    source, rendered = _decode(texture_video), _decode(output)
    for index in (0, 7):  # 검출된 프레임과 유지 중인 프레임
        assert _variance(_region(rendered[index], WIDENED)) < _variance(_region(source[index], WIDENED)) / 10
    assert (
        _variance(_region(rendered[9], WIDENED)) > _variance(_region(source[9], WIDENED)) / 2
    )  # 유지가 끝나면 원본대로
    outside = (0, 0, 40, 30)
    assert _variance(_region(rendered[0], outside)) > _variance(_region(source[0], outside)) / 2  # 상자 밖은 그대로


def test_render_video_detects_every_third_frame_at_60fps_and_covers_the_frames_between(
    ffmpeg: str, tmp_path: Path
) -> None:
    video = _texture_video(ffmpeg, tmp_path / "texture60.mp4", fps=60, count=12)
    calls = 0

    def detect(frame: np.ndarray) -> list[Box]:
        nonlocal calls
        calls += 1
        return [FACE]

    output = tmp_path / "result.mp4"
    result = render_video(video, _empty_keypoints(tmp_path / "k.json"), output, ffmpeg_path=ffmpeg, detect_faces=detect)

    assert calls == 4  # 60fps x 0.05초 = 3프레임마다: 0·3·6·9번 프레임만 검출기를 부른다
    assert (result.frames, result.face_frames) == (12, 12)  # 사이 프레임은 유지된 상자로 가린다
    source, rendered = _decode(video), _decode(output)
    for index in (1, 11):  # 검출기를 부르지 않은 프레임도 가려져 있다
        assert _variance(_region(rendered[index], WIDENED)) < _variance(_region(source[index], WIDENED)) / 10


def test_render_video_hands_the_remembered_places_to_blazeface(
    texture_video: Path, ffmpeg: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """기본 검출기 길: 확실히 찾은 자리를 다음 검출에 넘기고, 그 자리의 낮은 점수 검출도 가린다."""
    seen: list[list[Box]] = []

    class Detector:
        def detect_tracked(self, frame: np.ndarray, near: Sequence[Box] = ()) -> tuple[list[Box], list[Box]]:
            seen.append(list(near))
            if len(seen) == 1:
                return [FACE], []  # 0번 프레임에서만 확실히 찾는다
            return [], ([FACE] if near else [])  # 그 뒤로는 자리를 받았을 때만 낮은 점수로 찾는다

    monkeypatch.setattr("app.video.render.FaceDetector", Detector)
    output = tmp_path / "result.mp4"
    result = render_video(texture_video, _empty_keypoints(tmp_path / "k.json"), output, ffmpeg_path=ffmpeg)

    # 10fps라 프레임마다 검출하고, 자리는 1.0초(10프레임) 기억한다. 1~9번 프레임의 검출이 0번의 자리를 받는다
    assert seen == [[]] + [[FACE]] * 9
    assert (result.frames, result.face_frames) == (10, 10)
    source, rendered = _decode(texture_video), _decode(output)
    assert _variance(_region(rendered[9], WIDENED)) < _variance(_region(source[9], WIDENED)) / 10


def test_render_video_uses_blazeface_by_default(texture_video: Path, ffmpeg: str, tmp_path: Path) -> None:
    result = render_video(
        texture_video, _empty_keypoints(tmp_path / "k.json"), tmp_path / "result.mp4", ffmpeg_path=ffmpeg
    )
    assert result.frames == 10 and result.face_frames == 0  # 무늬에는 얼굴이 없다


def test_render_video_also_covers_the_places_given_by_hand(texture_video: Path, ffmpeg: str, tmp_path: Path) -> None:
    """검출기가 아무것도 못 찾아도 extra_faces가 준 프레임의 상자는 가린다(시연 데이터의 face_masks.json, 277)."""
    output = tmp_path / "result.mp4"
    result = render_video(
        texture_video,
        _empty_keypoints(tmp_path / "k.json"),
        output,
        ffmpeg_path=ffmpeg,
        detect_faces=lambda frame: [],
        extra_faces=lambda frame_no: [FACE] if 2 <= frame_no <= 4 else [],
    )

    assert (result.frames, result.face_frames) == (10, 3)
    source, rendered = _decode(texture_video), _decode(output)
    for index in (2, 4):
        assert _variance(_region(rendered[index], WIDENED)) < _variance(_region(source[index], WIDENED)) / 10
    for index in (1, 5):  # 적어 준 프레임만 가린다. 검출한 얼굴처럼 이어서 유지하지 않는다
        assert _variance(_region(rendered[index], WIDENED)) > _variance(_region(source[index], WIDENED)) / 2
