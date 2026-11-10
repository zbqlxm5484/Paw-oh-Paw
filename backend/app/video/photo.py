"""반려견 사진을 저장할 모양으로 바꾼다(명세 12.5 사진, 13.9, BE-34). DB와 저장소를 모른다(11.3).

받은 바이트 → 형식·크기 확인 → 픽셀로 풀기 → 사람 얼굴 가리기(XRAY는 건너뜀) → 같은 형식으로 다시 쓰기.
다시 쓰면서 사진 속 부가 정보(EXIF의 위치·기기)가 빠지고, 사진에 적힌 방향대로 세워진다.
얼굴 검출기와 가리는 방식은 결과 영상과 같다(video/render.py의 FaceDetector, blur_faces).
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from app.video.render import Box, FaceDetector, blur_faces

JPEG, PNG = "jpg", "png"
CONTENT_TYPES = {JPEG: "image/jpeg", PNG: "image/png"}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
# 크기 정보가 든 JPEG 조각(SOF0~SOF15 중 DHT·JPG·DAC를 뺀 것)
JPEG_SIZE_MARKERS = frozenset(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
# 길이 없이 표시만 있는 JPEG 조각(TEM, RST0~7, SOI)
JPEG_BARE_MARKERS = frozenset({0x01, 0xD8, *range(0xD0, 0xD8)})
JPEG_QUALITY = 92

FaceFinder = Callable[[np.ndarray], Sequence[Box]]


class PhotoFormatError(Exception):
    """JPEG도 PNG도 아니다."""


class PhotoUnreadableError(Exception):
    """형식은 맞는데 크기를 읽을 수 없거나 픽셀로 풀 수 없다."""


class PhotoTooLargeError(Exception):
    """화소 수가 상한을 넘는다."""


@dataclass(frozen=True)
class PreparedPhoto:
    data: bytes  # 저장할 바이트
    ext: str  # jpg 또는 png
    width: int
    height: int
    masked_faces: int


def sniff_format(data: bytes) -> str:
    """내용의 첫 바이트로 형식을 가린다. 파일 이름은 보지 않는다."""
    if data.startswith(PNG_SIGNATURE):
        return PNG
    if data.startswith(JPEG_SIGNATURE):
        return JPEG
    raise PhotoFormatError


def _png_size(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise PhotoUnreadableError
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def _jpeg_size(data: bytes) -> tuple[int, int]:
    position = 2
    while position + 4 <= len(data):
        if data[position] != 0xFF:
            raise PhotoUnreadableError
        marker = data[position + 1]
        if marker == 0xFF:  # 채움 바이트
            position += 1
        elif marker in JPEG_BARE_MARKERS:
            position += 2
        elif marker in JPEG_SIZE_MARKERS:
            if position + 9 > len(data):
                raise PhotoUnreadableError
            height = int.from_bytes(data[position + 5 : position + 7], "big")
            width = int.from_bytes(data[position + 7 : position + 9], "big")
            return width, height
        elif marker == 0xDA:  # 픽셀 자료가 시작됐는데 크기 조각이 없었다
            raise PhotoUnreadableError
        else:
            position += 2 + int.from_bytes(data[position + 2 : position + 4], "big")
    raise PhotoUnreadableError


def declared_size(data: bytes, ext: str) -> tuple[int, int]:
    """머리 부분에 적힌 (너비, 높이). 픽셀로 풀기 전에 화소 수를 본다(작은 파일이 큰 그림으로 풀리는 것을 막는다)."""
    width, height = _png_size(data) if ext == PNG else _jpeg_size(data)
    if width <= 0 or height <= 0:
        raise PhotoUnreadableError
    return width, height


_detector: FaceDetector | None = None
_detector_lock = threading.Lock()


def find_faces(image: np.ndarray) -> Sequence[Box]:
    """프로세스마다 검출기 하나를 처음 쓸 때 만들고, 한 번에 한 요청만 쓴다(cv2.dnn은 같이 쓰면 안 된다)."""
    global _detector  # noqa: PLW0603 - 프로세스 안에서 하나만 두는 검출기
    with _detector_lock:
        if _detector is None:
            _detector = FaceDetector()
        return _detector.detect(image)


def prepare_photo(
    data: bytes, *, mask_faces: bool, max_pixels: int, detect_faces: FaceFinder | None = None
) -> PreparedPhoto:
    """받은 사진 바이트 → 저장할 사진. mask_faces면 사람 얼굴을 가린다.

    PhotoFormatError: JPEG·PNG가 아니다. PhotoTooLargeError: 화소 수가 max_pixels를 넘는다.
    PhotoUnreadableError: 풀 수 없다. 얼굴 검출이 실패하면 VideoRenderError가 그대로 올라간다(가리지 않은 사진을
    돌려주지 않는다). detect_faces는 테스트가 가짜를 끼우는 자리다.
    """
    ext = sniff_format(data)
    width, height = declared_size(data, ext)
    if width * height > max_pixels:
        raise PhotoTooLargeError
    try:
        # IMREAD_COLOR는 EXIF 방향대로 세우고 3채널 8비트 BGR로 준다
        image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    except cv2.error:
        image = None
    if image is None or image.size == 0:
        raise PhotoUnreadableError
    masked = blur_faces(image, (detect_faces or find_faces)(image)) if mask_faces else 0
    options = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY] if ext == JPEG else []
    ok, encoded = cv2.imencode(f".{ext}", image, options)
    if not ok:
        raise PhotoUnreadableError
    return PreparedPhoto(
        data=encoded.tobytes(), ext=ext, width=image.shape[1], height=image.shape[0], masked_faces=masked
    )
