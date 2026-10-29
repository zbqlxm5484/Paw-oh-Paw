"""결과 영상 만들기(7절 "결과 영상 만들기" 1~3번, 작업 단위 7, Jira 128·150). DB·저장소·설정을 모르는 순수 함수다(11.3).

원본 영상의 프레임마다 사람 얼굴을 찾아 모자이크로 가리고(7절 2번, BE-12), 분석 API의 관절점 파일(6절 get_keypoints:
프레임별 22점·신뢰도)로 골격을 그린 뒤, 브라우저에서 바로 재생되는 H.264(yuv420p, faststart) MP4로 저장한다.
프레임 읽기·얼굴 검출·그리기는 OpenCV, 인코딩은 ffmpeg 실행 파일이다. OpenCV가 바로 쓰는 mp4v 코덱은 Chrome에서
열리지 않기 때문이다(7절 3번). 소리는 넣지 않는다. 사람이 보는 용도라 보호자·직원의 목소리가 남을 이유가 없다.

얼굴 검출은 Google MediaPipe BlazeFace(full range)를 ONNX로 바꿔 OpenCV DNN(cv2.dnn)으로 돌린다. 모델 파일
(models/face_detection_full_range.onnx, Apache-2.0)은 코드와 같이 둔다. 라이선스뿐 아니라 학습 데이터 조건까지 보는
세부명세서 7.1 때문에 YOLO 계열(AGPL)과 YuNet(모델은 MIT지만 학습 데이터 WIDER FACE가 비상업 표기)은 쓰지 않는다
(7절, Jira 137). 모델 입력이 192x192라 프레임을 겹치는 타일로 나눠 타일마다 찾고, 상자를 넓혀 가리고, 검출이 끊겨도
잠깐은 마지막 자리를 계속 가린다. 얼굴 가리기는 분석과 무관하고 결과 영상에만 적용한다(7절).

워커의 자식 프로세스(app/worker/render.py)가 render_video 하나를 부른다. 자식은 이 모듈만 import한다.
관절점 번호의 뜻은 docs/labeling/labelGuide.md 1장(0부터), 연결은 ai/data_prep/aihub_to_coco.py의 SKELETON과 같다.
프레임마다 관절점 파일의 camera_side(right·left·null)에 따라 등 가운데·엉덩이 위와 카메라 쪽 귀·다리만 그리고
반대쪽 귀·다리는 그리지 않는다(세부명세서 PR-F01-04: 반대쪽 다리 관절점은 고객 결과에 쓰지 않는다. 몸에 가려 틀리게
찍히는 일이 많다. 반대쪽 귀도 같은 이유로 뺀다). 판정은 분석 API가 한다(engine/camera_side.py와 같은 규칙).
"""

from __future__ import annotations

import json
import math
import subprocess
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

KEYPOINT_COUNT = 22
# 신뢰도가 이보다 낮은 점은 못 찾은 점으로 보고 그리지 않는다. 기업 평가 도구 video_kpi.py의 CONF = 0.3("서비스와
# 같다"), engine/camera_side.py의 CONF와 같은 값이다(128 리뷰). 바꿀 때는 셋을 같이 본다
MIN_CONFIDENCE = 0.3
# 12.4: 자식 프로세스의 ffmpeg는 -threads 2
FFMPEG_THREADS = 2
# 마지막 프레임을 넘긴 뒤 ffmpeg가 파일을 닫을 때까지 기다리는 한도. 넘으면 죽이고 실패로 본다
ENCODE_TIMEOUT_SEC = 120
# 인코딩 품질. CRF 23은 x264 기본값이고, veryfast는 화질보다 CPU를 아끼는 쪽이다(3절 서버 부담)
X264_PRESET = "veryfast"
X264_CRF = "23"

# ---- 얼굴 가리기 설정(7절 2번). 16절에 환경 변수가 없으므로 코드 상수다 ----
# Google MediaPipe BlazeFace(full range)를 ONNX로 바꾼 모델(Apache-2.0, 구글이 동의를 받아 모은 자체 데이터로 학습).
# 출처·SHA-256·변환 명령은 models/README.md. OpenCV DNN으로 돌리므로 패키지를 더 넣지 않는다
FACE_MODEL_PATH = Path(__file__).resolve().parent / "models" / "face_detection_full_range.onnx"
# 모델 입력은 192x192, 앵커는 stride 4의 48x48 격자(MediaPipe face_detection_full_range.pbtxt)
FACE_INPUT_SIZE = 192
FACE_ANCHOR_STRIDE = 4
# 검출은 이 폭 이하로 줄인 프레임에서 한다(4K도 1080p 비용). 1080p는 그대로다
FACE_DETECT_WIDTH = 1920
# 프레임을 이 크기쯤의 겹치는 타일로 나눠 타일마다 찾는다. 192px 입력에 프레임을 통째로 넣으면 멀리 있는 보호자 얼굴
# (1080p에서 60px 안팎)이 몇 px로 줄어 놓친다. 1080p면 4x3 타일이고 회사 프레임 20장에서 사람 얼굴 24/24, 오탐 0,
# 1스레드 약 100ms/프레임이다. 3x2는 팔로 가린 얼굴 하나를, 2x2는 가장자리 얼굴을 놓쳤다
FACE_TILE_SIZE = (480, 360)
FACE_TILE_OVERLAP = 0.2
# MediaPipe full range 기본값(min_score_thresh 0.6). 0.5면 20장에서 오탐 1. 엉뚱한 곳을 가리는 쪽이 놓치는 쪽보다 낫다
FACE_SCORE_THRESHOLD = 0.6
FACE_NMS_THRESHOLD = 0.3
# 찾은 상자를 사방으로 이만큼 넓혀 가린다(머리카락·턱·옆얼굴)
FACE_MARGIN = 0.3
# 검출이 끊겨도 이 시간 동안은 마지막 자리를 계속 가린다. 한 프레임만 놓쳐도 얼굴이 드러나기 때문이다
FACE_HOLD_SEC = 0.5
# 모자이크 블록은 넓힌 상자 너비의 1/3(얼굴 하나가 두 칸쯤), 최소 16px. 6칸으로 가리면 그 결과에서 검출기(당시
# YuNet)가 회사 프레임 20장 중 12장을 다시 얼굴로 찾았고(모양이 남는다), 3칸이면 0장이다. 그 위에 상자 너비의
# 1/8 가우시안 흐림을 더해 칸 경계를 지운다
FACE_BLOCK_DIVISOR = 3
FACE_MIN_BLOCK = 16
FACE_BLUR_SIGMA_RATIO = 1 / 8

Point = tuple[float, float] | None
Box = tuple[int, int, int, int]  # 프레임 픽셀의 x0, y0, x1, y1(끝은 포함하지 않음)
FaceFinder = Callable[[np.ndarray], Sequence[Box]]  # 프레임(BGR) → 얼굴 상자 목록

# 22점 연결(0부터). ai/data_prep/aihub_to_coco.py의 SKELETON(1부터)을 0부터로 옮긴 것이다.
SKELETON: tuple[tuple[int, int], ...] = (
    (0, 2),  # 왼쪽 귀 → 등 가운데(T13)
    (1, 2),  # 오른쪽 귀 → 등 가운데
    (2, 3),  # 등 가운데 → 왼쪽 어깨뼈 위끝
    (2, 8),  # 등 가운데 → 오른쪽 어깨뼈 위끝
    (2, 13),  # 등 가운데 → 엉덩이 위(iliac crest)
    (3, 4),  # 왼쪽 앞다리: 어깨뼈 → 어깨 → 팔꿈치 → 앞발목 → 앞발끝
    (4, 5),
    (5, 6),
    (6, 7),
    (8, 9),  # 오른쪽 앞다리
    (9, 10),
    (10, 11),
    (11, 12),
    (13, 14),  # 왼쪽 뒷다리: 엉덩이 위 → 고관절 → 무릎 → 뒷발목 → 뒷발끝
    (14, 15),
    (15, 16),
    (16, 17),
    (13, 18),  # 오른쪽 뒷다리
    (18, 19),
    (19, 20),
    (20, 21),
)

# 점이 속한 다리. 몸통(귀·등 가운데·엉덩이 위)은 BODY다. 색은 BGR이다(OpenCV).
BODY, LF, RF, LH, RH = "BODY", "LF", "RF", "LH", "RH"
COLORS = {
    BODY: (255, 255, 255),  # 흰색
    LF: (80, 220, 80),  # 초록
    RF: (255, 170, 60),  # 하늘색
    LH: (60, 160, 255),  # 주황
    RH: (230, 90, 230),  # 자홍
}


def limb_of(index: int) -> str:
    if 3 <= index <= 7:
        return LF
    if 8 <= index <= 12:
        return RF
    if 14 <= index <= 17:
        return LH
    if 18 <= index <= 21:
        return RH
    return BODY


# 카메라 쪽 귀·다리만 그린다(세부명세서 PR-F01-04). 값은 관절점 파일의 camera_side. 반대쪽 귀도 몸에 가려 틀리게
# 찍히므로 뺀다(10-29 결정). 집합은 engine/camera_side.py의 LEFT·RIGHT와 같다. 몸통은 등 가운데(T13)·엉덩이 위 둘
CAMERA_RIGHT, CAMERA_LEFT = "right", "left"
BODY_POINTS = frozenset({2, 13})
LEFT_POINTS = frozenset({0}) | frozenset(range(3, 8)) | frozenset(range(14, 18))
RIGHT_POINTS = frozenset({1}) | frozenset(range(8, 13)) | frozenset(range(18, 22))
ALL_POINTS = frozenset(range(KEYPOINT_COUNT))


def visible_points(camera_side: str | None) -> frozenset[int]:
    """그릴 점 번호. right면 몸통 + 오른쪽 귀·다리, left면 몸통 + 왼쪽 귀·다리, null(판정 못 함)이면 몸통 둘만."""
    if camera_side == CAMERA_RIGHT:
        return BODY_POINTS | RIGHT_POINTS
    if camera_side == CAMERA_LEFT:
        return BODY_POINTS | LEFT_POINTS
    return BODY_POINTS


class VideoRenderError(Exception):
    """원본 영상을 읽지 못했거나, 관절점 파일이 형식에 맞지 않거나, 인코딩이 실패했다.

    메시지에는 파일 경로를 넣지 않는다(11.8). 워커는 촬영의 결과 영상을 FAILED(VIDEO_RENDER_FAILED)로 둔다(14.2).
    """


@dataclass(frozen=True)
class FramePoints:
    """관절점 파일의 프레임 하나: 22점과 카메라 쪽(right·left, 판정 못 했으면 None)."""

    points: list[Point]
    camera_side: str | None


@dataclass(frozen=True)
class Keypoints:
    """관절점 파일(6절). frames는 프레임 번호 → FramePoints이고, 개를 못 찾은 프레임(points가 null)은 들어 있지 않다."""

    width: int | None
    height: int | None
    fps: float | None
    frames: dict[int, FramePoints]


@dataclass(frozen=True)
class RenderResult:
    frames: int  # 읽은(= 쓴) 프레임 수
    drawn_frames: int  # 골격을 하나라도 그린 프레임 수
    width: int
    height: int
    fps: float
    bytes: int  # 결과 파일 크기
    face_frames: int = 0  # 얼굴을 하나라도 가린 프레임 수


# ---- 관절점 파일 읽기 ----


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or math.isnan(value) or math.isinf(value):
        return None
    return float(value)


def _positive_int(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None and number > 0 else None


def _point(raw: Any) -> Point:
    """[x, y] 또는 [x, y, 신뢰도]. 숫자가 아니거나 신뢰도가 MIN_CONFIDENCE 미만이면 못 찾은 점(None)이다."""
    if not isinstance(raw, list | tuple) or len(raw) < 2:
        return None
    x, y = _number(raw[0]), _number(raw[1])
    confidence = _number(raw[2]) if len(raw) > 2 else 1.0
    if x is None or y is None or confidence is None or confidence < MIN_CONFIDENCE:
        return None
    return x, y


def _camera_side(raw: Any) -> str | None:
    """right·left(대소문자 무관)만 받고 그 밖(null, 다른 값)은 판정 못 함(None)으로 본다. 그러면 몸통만 그린다."""
    if isinstance(raw, str) and raw.lower() in (CAMERA_RIGHT, CAMERA_LEFT):
        return raw.lower()
    return None


def parse_keypoints(data: Any) -> Keypoints:
    """관절점 JSON(dict) → Keypoints. 형식이 다르면 VideoRenderError(어느 자리인지 메시지에).

    프레임 번호는 0부터이고, 원본 영상을 OpenCV VideoCapture.read()로 처음부터 차례로 읽은 순서다. 분석 API도 같은
    방식으로 번호를 매긴다(128 리뷰에서 확인, 분석 API 명세에 적기로 함). 개를 못 찾은 프레임은 points가 null이다.
    """
    if not isinstance(data, dict) or not isinstance(data.get("frames"), list):
        raise VideoRenderError("관절점 파일에 frames 목록이 없습니다")
    frames: dict[int, FramePoints] = {}
    for position, item in enumerate(data["frames"]):
        if not isinstance(item, dict):
            raise VideoRenderError(f"frames[{position}]이 객체가 아닙니다")
        frame = _number(item.get("frame"))
        if frame is None or frame < 0 or not frame.is_integer():
            raise VideoRenderError(f"frames[{position}].frame={item.get('frame')!r}")
        points = item.get("points")
        if points is None:
            continue  # 개를 못 찾은 프레임
        if not isinstance(points, list) or len(points) != KEYPOINT_COUNT:
            raise VideoRenderError(f"frames[{position}].points가 {KEYPOINT_COUNT}점이 아닙니다")
        frames[int(frame)] = FramePoints([_point(raw) for raw in points], _camera_side(item.get("camera_side")))
    return Keypoints(
        width=_positive_int(data.get("width")),
        height=_positive_int(data.get("height")),
        fps=_number(data.get("fps")),
        frames=frames,
    )


def load_keypoints(path: Path) -> Keypoints:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise VideoRenderError("관절점 파일을 읽지 못했습니다") from error
    return parse_keypoints(data)


# ---- 그리기 ----


def draw_skeleton(
    frame: np.ndarray,
    points: Sequence[Point],
    *,
    scale: tuple[float, float] = (1.0, 1.0),
    visible: Collection[int] = ALL_POINTS,
) -> int:
    """frame(BGR, 제자리에서 고친다)에 연결선과 점을 그리고 그린 점의 수를 돌려준다.

    scale은 관절점 좌표계(관절점 파일의 width·height) → 이 프레임 크기의 비율이다. visible에 든 번호만 그리고
    (visible_points: 카메라 반대쪽 귀·다리는 뺀다), 못 찾은 점(None)이나 visible 밖의 점에 닿는 선은 건너뛴다.
    선 굵기는 프레임 크기에 맞춘다(720p에서 2, 1080p에서 3).
    """
    height, width = frame.shape[:2]
    thickness = max(2, round(min(width, height) / 360))
    radius = thickness + 2
    scale_x, scale_y = scale
    pixels = [
        None if p is None or index not in visible else (round(p[0] * scale_x), round(p[1] * scale_y))
        for index, p in enumerate(points)
    ]
    for a, b in SKELETON:
        if a >= len(pixels) or b >= len(pixels) or pixels[a] is None or pixels[b] is None:
            continue
        limb = limb_of(b) if limb_of(a) == limb_of(b) else BODY
        cv2.line(frame, pixels[a], pixels[b], COLORS[limb], thickness, cv2.LINE_AA)
    drawn = 0
    for index, pixel in enumerate(pixels):
        if pixel is None:
            continue
        cv2.circle(frame, pixel, radius + 1, (0, 0, 0), -1, cv2.LINE_AA)  # 밝은 배경에서도 보이게 검은 테두리
        cv2.circle(frame, pixel, radius, COLORS[limb_of(index)], -1, cv2.LINE_AA)
        drawn += 1
    return drawn


# ---- 얼굴 가리기 (7절 2번, BE-12) ----


def _anchor_centers(input_size: int = FACE_INPUT_SIZE, stride: int = FACE_ANCHOR_STRIDE) -> np.ndarray:
    """MediaPipe SSD 앵커의 중심((n, 2) = cx, cy, 0~1 비율). full range는 층 하나(stride 4)에 칸마다 앵커 하나이고
    크기는 고정 1(fixed_anchor_size)이라 중심만 있으면 된다. 순서는 행(y)이 바깥, 열(x)이 안쪽이다.
    """
    cells = math.ceil(input_size / stride)
    centers = (np.arange(cells, dtype=np.float32) + 0.5) / cells
    grid_y, grid_x = np.meshgrid(centers, centers, indexing="ij")
    return np.stack([grid_x.ravel(), grid_y.ravel()], axis=1)


def _tiles(
    width: int, height: int, tile: tuple[int, int] = FACE_TILE_SIZE, overlap: float = FACE_TILE_OVERLAP
) -> list[Box]:
    """프레임을 겹치는 타일로 나눈다. 타일 수는 ceil(폭/타일 폭) x ceil(높이/타일 높이)이고, 타일마다 사방을 overlap
    비율만큼 넓혀 경계에 걸친 얼굴이 어느 한 타일에는 온전히 들어가게 한다. 작은 프레임은 타일 하나(프레임 전체)다.
    """
    cols = max(1, math.ceil(width / tile[0]))
    rows = max(1, math.ceil(height / tile[1]))
    tile_width, tile_height = width / cols, height / rows
    boxes: list[Box] = []
    for row in range(rows):
        for col in range(cols):
            x0 = max(0, math.floor(col * tile_width - tile_width * overlap))
            y0 = max(0, math.floor(row * tile_height - tile_height * overlap))
            x1 = min(width, math.ceil((col + 1) * tile_width + tile_width * overlap))
            y1 = min(height, math.ceil((row + 1) * tile_height + tile_height * overlap))
            boxes.append((x0, y0, x1, y1))
    return boxes


def _iou(a: Sequence[float], b: Sequence[float]) -> float:
    inter_width = min(a[2], b[2]) - max(a[0], b[0])
    inter_height = min(a[3], b[3]) - max(a[1], b[1])
    if inter_width <= 0 or inter_height <= 0:
        return 0.0
    inter = inter_width * inter_height
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _nms(boxes: Sequence[Sequence[float]], scores: Sequence[float], threshold: float) -> list[int]:
    """점수 높은 순으로 보며 이미 고른 상자와 IoU가 threshold 이상이면 버린다.

    타일이 겹쳐 같은 얼굴이 두 번 나올 때 하나로 합친다.
    """
    keep: list[int] = []
    for index in sorted(range(len(boxes)), key=lambda i: -scores[i]):
        if all(_iou(boxes[index], boxes[kept]) < threshold for kept in keep):
            keep.append(index)
    return keep


class FaceDetector:
    """BlazeFace(full range) ONNX를 OpenCV DNN으로 돌려 프레임의 사람 얼굴 상자를 찾는다. 자식 프로세스마다 하나 만든다.

    프레임을 폭 detect_width 이하로 줄이고 겹치는 타일(_tiles)로 나눠, 타일마다 정사각형으로 채워(letterbox) 192x192로
    넣는다. 출력은 앵커(48x48 격자)마다 상자 16값(중심 x·y, 너비·높이, 눈·코·입·귀 6점)과 점수 1값이다. MediaPipe
    TensorsToDetections와 같이 중심 = 값/192 + 앵커 중심, 크기 = 값/192, 점수 = sigmoid로 푼다. 타일 결과를 프레임
    좌표로 되돌린 뒤 NMS로 합친다.
    """

    def __init__(
        self,
        model_path: Path = FACE_MODEL_PATH,
        *,
        detect_width: int = FACE_DETECT_WIDTH,
        score_threshold: float = FACE_SCORE_THRESHOLD,
    ) -> None:
        self.detect_width = detect_width
        self.score_threshold = score_threshold
        if not model_path.is_file():
            raise VideoRenderError("얼굴 검출 모델 파일이 없습니다")
        # OpenCV 5.0은 모델을 열 때 엔진 안내를 표준 오류에 찍을 수 있다. 동작과 무관하고 자식 프로세스 로그를
        # 어지럽히므로 여는 동안만 오류 수준으로 낮춘다
        log_level = cv2.utils.logging.getLogLevel()
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
        try:
            self._net = cv2.dnn.readNetFromONNX(str(model_path))
            self._outputs = self._net.getUnconnectedOutLayersNames()
        except cv2.error as error:
            raise VideoRenderError("얼굴 검출 모델을 열지 못했습니다") from error
        finally:
            cv2.utils.logging.setLogLevel(log_level)
        self._anchors = _anchor_centers()

    def _infer(self, square: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """정사각형 조각(BGR) → (상자 (n, 4): 조각 기준 0~1 비율 x0, y0, x1, y1, 점수 (n,))."""
        blob = cv2.dnn.blobFromImage(
            square, 1 / 127.5, (FACE_INPUT_SIZE, FACE_INPUT_SIZE), (127.5, 127.5, 127.5), swapRB=True
        )
        self._net.setInput(blob)
        outputs = self._net.forward(self._outputs)
        regressors = next((o for o in outputs if o.ndim == 3 and o.shape[-1] == 16), None)
        logits = next((o for o in outputs if o.ndim == 3 and o.shape[-1] == 1), None)
        if regressors is None or logits is None or regressors.shape[1] != len(self._anchors):
            raise VideoRenderError("얼굴 검출 모델의 출력 모양이 다릅니다")
        scores = 1.0 / (1.0 + np.exp(-np.clip(logits[0, :, 0], -50.0, 50.0)))
        centers = regressors[0, :, :2] / FACE_INPUT_SIZE + self._anchors
        half = regressors[0, :, 2:4] / FACE_INPUT_SIZE / 2
        return np.concatenate([centers - half, centers + half], axis=1), scores

    def detect(self, frame: np.ndarray) -> list[Box]:
        """frame(BGR)의 얼굴 상자(원래 프레임 좌표). 폭이 detect_width보다 크면 줄여서 찾고 상자를 되돌린다."""
        height, width = frame.shape[:2]
        if width > self.detect_width:
            ratio = self.detect_width / width
            size = (self.detect_width, max(1, round(height * ratio)))
            small = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
        else:
            ratio, small = 1.0, frame
        small_height, small_width = small.shape[:2]
        found: list[list[float]] = []  # 줄인 프레임 좌표의 x0, y0, x1, y1
        found_scores: list[float] = []
        try:
            for x0, y0, x1, y1 in _tiles(small_width, small_height):
                crop = small[y0:y1, x0:x1]
                crop_height, crop_width = crop.shape[:2]
                side = max(crop_height, crop_width)
                square = np.zeros((side, side, 3), dtype=np.uint8)
                pad_x, pad_y = (side - crop_width) // 2, (side - crop_height) // 2
                square[pad_y : pad_y + crop_height, pad_x : pad_x + crop_width] = crop
                boxes, scores = self._infer(square)
                for index in np.flatnonzero(scores >= self.score_threshold):
                    bx0, by0, bx1, by1 = (boxes[index] * side).tolist()
                    found.append([bx0 - pad_x + x0, by0 - pad_y + y0, bx1 - pad_x + x0, by1 - pad_y + y0])
                    found_scores.append(float(scores[index]))
        except cv2.error as error:
            raise VideoRenderError("얼굴 검출에 실패했습니다") from error
        result: list[Box] = []
        for index in _nms(found, found_scores, FACE_NMS_THRESHOLD):
            bx0, by0, bx1, by1 = found[index]
            box = (
                max(0, math.floor(bx0 / ratio)),
                max(0, math.floor(by0 / ratio)),
                min(width, math.ceil(bx1 / ratio)),
                min(height, math.ceil(by1 / ratio)),
            )
            if box[2] > box[0] and box[3] > box[1]:
                result.append(box)
        return result


def _overlaps(a: Box, b: Box) -> bool:
    """겹치는 넓이가 작은 쪽 상자의 절반 이상이면 같은 얼굴로 본다."""
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    if width <= 0 or height <= 0:
        return False
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return smaller <= 0 or width * height * 2 >= smaller


class FaceTracker:
    """검출이 끊긴 상자를 hold_frames 프레임 더 가린다(FACE_HOLD_SEC). 같은 자리의 새 검출은 묵은 상자를 대신한다."""

    def __init__(self, hold_frames: int) -> None:
        self.hold_frames = max(0, hold_frames)
        self._held: list[tuple[Box, int]] = []  # (상자, 앞으로 더 가릴 프레임 수)

    def update(self, detected: Sequence[Box]) -> list[Box]:
        """이번 프레임의 검출 결과를 넣고 이번 프레임에서 가릴 상자 전부(검출 + 유지 중)를 돌려준다."""
        aged = [
            (box, left - 1) for box, left in self._held if left > 0 and not any(_overlaps(box, new) for new in detected)
        ]
        self._held = [(box, self.hold_frames) for box in detected] + aged
        return [box for box, _ in self._held]


def blur_faces(frame: np.ndarray, boxes: Sequence[Box], *, margin: float = FACE_MARGIN) -> int:
    """boxes를 margin만큼 넓혀 모자이크 + 흐림으로 가린다(제자리). 프레임 밖은 잘라낸다. 가린 상자 수를 돌려준다."""
    height, width = frame.shape[:2]
    blurred = 0
    for x0, y0, x1, y1 in boxes:
        box_width, box_height = x1 - x0, y1 - y0
        if box_width <= 0 or box_height <= 0:
            continue
        pad_x, pad_y = round(box_width * margin), round(box_height * margin)
        x0, y0 = max(0, x0 - pad_x), max(0, y0 - pad_y)
        x1, y1 = min(width, x1 + pad_x), min(height, y1 + pad_y)
        if x1 <= x0 or y1 <= y0:
            continue
        block = max(FACE_MIN_BLOCK, (x1 - x0) // FACE_BLOCK_DIVISOR)
        cells = (max(1, (x1 - x0) // block), max(1, (y1 - y0) // block))
        small = cv2.resize(frame[y0:y1, x0:x1], cells, interpolation=cv2.INTER_AREA)
        mosaic = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
        sigma = max(2.0, (x1 - x0) * FACE_BLUR_SIGMA_RATIO)
        frame[y0:y1, x0:x1] = cv2.GaussianBlur(mosaic, (0, 0), sigma)
        blurred += 1
    return blurred


def process_frame(
    frame: np.ndarray, frame_points: FramePoints | None, *, scale: tuple[float, float], faces: Sequence[Box] = ()
) -> bool:
    """프레임 하나를 결과 영상용으로 고친다. 얼굴을 먼저 가리고(7절 2번) 그 위에 골격을 그린다(1번).

    순서를 이렇게 두어야 골격이 모자이크에 묻히지 않는다. 카메라 쪽 귀·다리만 그린다(visible_points).
    골격을 하나라도 그렸으면 True.
    """
    blur_faces(frame, faces)
    if frame_points is None:
        return False
    visible = visible_points(frame_points.camera_side)
    return draw_skeleton(frame, frame_points.points, scale=scale, visible=visible) > 0


# ---- 인코딩 ----


def _ffmpeg_command(
    ffmpeg_path: str, width: int, height: int, fps: float, output_path: Path, threads: int
) -> list[str]:
    return [
        ffmpeg_path,
        "-y",
        "-v",
        "error",
        "-nostats",
        # 입력: 자식이 표준 입력으로 넘기는 BGR 프레임
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{width}x{height}",
        "-framerate",
        f"{fps:.6f}",
        "-i",
        "-",
        # 출력: 브라우저가 재생하는 H.264 + yuv420p + faststart(머리 정보를 앞에 두어 바로 재생). 소리 없음
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        X264_PRESET,
        "-crf",
        X264_CRF,
        "-pix_fmt",
        "yuv420p",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # yuv420p는 너비·높이가 짝수여야 한다
        "-movflags",
        "+faststart",
        "-threads",
        str(threads),
        "-f",
        "mp4",
        str(output_path),
    ]


def _hide_paths(text: str, paths: Sequence[Path]) -> str:
    """ffmpeg 메시지의 파일 경로를 지운다(11.8 로그에 경로를 남기지 않는다)."""
    for path in paths:
        text = text.replace(str(path), "<path>").replace(path.as_posix(), "<path>")
    return text


def _last_line(log_path: Path, hidden: Sequence[Path]) -> str:
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    except OSError:
        return ""
    return _hide_paths(lines[-1], hidden)[:200] if lines else ""


def _finish_ffmpeg(encoder: subprocess.Popen[bytes], log_path: Path, hidden: Sequence[Path]) -> None:
    """표준 입력을 닫아 남은 프레임을 쓰게 하고 종료를 기다린다. 0이 아니면 VideoRenderError."""
    try:
        if encoder.stdin is not None:
            encoder.stdin.close()
    except OSError:
        pass  # ffmpeg가 먼저 죽었다. 아래 종료 코드가 사유를 낸다
    try:
        encoder.wait(timeout=ENCODE_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        encoder.kill()
        encoder.wait()
        raise VideoRenderError(f"ffmpeg가 {ENCODE_TIMEOUT_SEC}초 안에 끝나지 않아 중단했습니다") from None
    if encoder.returncode != 0:
        raise VideoRenderError(f"ffmpeg 종료 코드 {encoder.returncode}: {_last_line(log_path, hidden)}")


def render_video(
    input_path: Path,
    keypoints_path: Path,
    output_path: Path,
    *,
    ffmpeg_path: str = "ffmpeg",
    ffmpeg_threads: int = FFMPEG_THREADS,
    detect_faces: FaceFinder | None = None,
) -> RenderResult:
    """원본 영상 + 관절점 파일 → output_path에 결과 영상(MP4). 실패하면 VideoRenderError.

    ffmpeg의 오류 출력은 output_path 옆의 ffmpeg.log에 쓴다(표준 오류를 파이프로 받으면 프레임을 넘기는 중에 막힐 수
    있다). 워커가 작업 폴더째 지운다. 프레임 번호는 0부터, 읽는 순서다(parse_keypoints).
    detect_faces는 프레임 → 얼굴 상자 목록이다. None이면 BlazeFace(FaceDetector)이고, 테스트가 가짜를 끼우는 자리다.
    """
    cv2.setNumThreads(1)  # 12.4: 자식 프로세스의 OpenCV 스레드는 1개
    keypoints = load_keypoints(keypoints_path)
    capture = cv2.VideoCapture(str(input_path))
    if not capture.isOpened():
        raise VideoRenderError("원본 영상을 열지 못했습니다")
    try:
        ok, frame = capture.read()
        if not ok or frame is None:
            raise VideoRenderError("원본 영상에서 프레임을 읽지 못했습니다")
        height, width = frame.shape[:2]
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        if fps <= 0:
            fps = keypoints.fps or 30.0  # 읽히지 않으면 관절점 파일의 fps, 그것도 없으면 30
        scale = (
            width / keypoints.width if keypoints.width else 1.0,
            height / keypoints.height if keypoints.height else 1.0,
        )
        finder = detect_faces or FaceDetector().detect  # 모델을 못 열면 ffmpeg를 띄우기 전에 실패한다
        tracker = FaceTracker(round(fps * FACE_HOLD_SEC))
        log_path = output_path.parent / "ffmpeg.log"
        hidden = (input_path, output_path, keypoints_path)
        try:
            log = log_path.open("wb")
        except OSError as error:
            raise VideoRenderError("작업 폴더에 쓸 수 없습니다") from error
        with log:
            try:
                encoder = subprocess.Popen(
                    _ffmpeg_command(ffmpeg_path, width, height, fps, output_path, ffmpeg_threads),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=log,
                )
            except OSError as error:
                raise VideoRenderError("ffmpeg를 실행하지 못했습니다(FFMPEG_PATH)") from error
            frames = drawn_frames = face_frames = 0
            try:
                assert encoder.stdin is not None
                while ok and frame is not None:
                    if frame.shape[0] != height or frame.shape[1] != width:
                        raise VideoRenderError(f"{frames}번 프레임의 크기가 첫 프레임과 다릅니다")
                    faces = tracker.update(finder(frame))
                    if faces:
                        face_frames += 1
                    if process_frame(frame, keypoints.frames.get(frames), scale=scale, faces=faces):
                        drawn_frames += 1
                    try:
                        encoder.stdin.write(frame.tobytes())
                    except (BrokenPipeError, OSError):
                        break  # ffmpeg가 먼저 죽었다. _finish_ffmpeg가 종료 코드로 사유를 낸다
                    frames += 1
                    ok, frame = capture.read()
            except BaseException:
                encoder.kill()
                encoder.wait()
                raise
        _finish_ffmpeg(encoder, log_path, hidden)
    finally:
        capture.release()
    size = output_path.stat().st_size if output_path.is_file() else 0
    if size == 0:
        raise VideoRenderError("결과 영상 파일이 비어 있습니다")
    return RenderResult(
        frames=frames,
        drawn_frames=drawn_frames,
        width=width,
        height=height,
        fps=fps,
        bytes=size,
        face_frames=face_frames,
    )
