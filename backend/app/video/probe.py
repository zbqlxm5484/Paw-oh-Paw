"""ffprobe로 영상 정보 읽기(13.1). DB·저장소를 모르는 순수 함수다(11.3).

`ffprobe -v error -show_streams -show_format -of json`의 출력을 읽는다.
휴대폰 영상은 세로로 찍어도 너비·높이를 가로로 저장하고 회전 값만 남기므로, 회전이 ±90°면 너비·높이를 바꿔 준다.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any

PROBE_TIMEOUT_SEC = 30


class VideoProbeError(Exception):
    """ffprobe가 영상 스트림을 읽지 못했다. 업로드에서는 400 VIDEO_UNREADABLE이 된다."""


@dataclass(frozen=True)
class VideoInfo:
    width: int  # 회전을 반영한, 화면에 보이는 방향의 너비
    height: int
    rotation: int  # 0·90·180·270
    fps: Decimal  # 소수 둘째 자리
    duration_sec: Decimal  # 소수 둘째 자리
    bitrate_kbps: int  # 반올림한 정수
    codec: str  # h264, hevc, ...


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _two_places(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _rotation(stream: dict[str, Any]) -> int:
    """side_data_list의 rotation 또는 tags.rotate. 없으면 0."""
    for side_data in stream.get("side_data_list") or []:
        if "rotation" in side_data:
            value = _decimal(side_data["rotation"])
            if value is not None:
                return int(value.to_integral_value(ROUND_HALF_UP)) % 360
    value = _decimal((stream.get("tags") or {}).get("rotate"))
    return int(value.to_integral_value(ROUND_HALF_UP)) % 360 if value is not None else 0


def _fps(stream: dict[str, Any]) -> Decimal:
    """avg_frame_rate(예: 60000/1001)를 나눈다. 비어 있으면 r_frame_rate, 그것도 없으면 0."""
    for key in ("avg_frame_rate", "r_frame_rate"):
        raw = stream.get(key)
        if not raw or raw in ("0/0", "0"):
            continue
        try:
            fraction = Fraction(raw)
        except (ValueError, ZeroDivisionError):
            continue
        if fraction > 0:
            return Decimal(fraction.numerator) / Decimal(fraction.denominator)
    return Decimal(0)


def probe(path: Path, ffprobe_path: str = "ffprobe") -> VideoInfo:
    """영상 정보를 읽는다. 영상이 아니거나 깨졌으면 VideoProbeError."""
    command = [ffprobe_path, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]
    try:
        completed = subprocess.run(command, capture_output=True, timeout=PROBE_TIMEOUT_SEC, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise VideoProbeError(f"ffprobe를 실행하지 못했습니다: {error}") from error
    if completed.returncode != 0:
        raise VideoProbeError(completed.stderr.decode("utf-8", "replace").strip() or "ffprobe failed")
    try:
        data = json.loads(completed.stdout.decode("utf-8", "replace"))
    except ValueError as error:
        raise VideoProbeError("ffprobe 출력을 읽지 못했습니다") from error

    streams = [s for s in data.get("streams") or [] if s.get("codec_type") == "video"]
    if not streams:
        raise VideoProbeError("영상 스트림이 없습니다")
    stream = streams[0]
    fmt = data.get("format") or {}

    width, height = int(stream.get("width") or 0), int(stream.get("height") or 0)
    if width <= 0 or height <= 0:
        raise VideoProbeError("너비·높이를 읽지 못했습니다")
    rotation = _rotation(stream)
    if rotation in (90, 270):
        width, height = height, width

    duration = _decimal(stream.get("duration")) or _decimal(fmt.get("duration"))
    if duration is None or duration <= 0:
        raise VideoProbeError("길이를 읽지 못했습니다")

    bit_rate = _decimal(stream.get("bit_rate"))
    if bit_rate is None or bit_rate <= 0:
        # 영상 스트림에 비트레이트가 없으면 파일 크기 × 8 ÷ 길이(13.1)
        size = _decimal(fmt.get("size")) or Decimal(path.stat().st_size)
        bit_rate = size * 8 / duration

    return VideoInfo(
        width=width,
        height=height,
        rotation=rotation,
        fps=_two_places(_fps(stream)),
        duration_sec=_two_places(duration),
        bitrate_kbps=int((bit_rate / 1000).to_integral_value(ROUND_HALF_UP)),
        codec=str(stream.get("codec_name") or "").lower(),
    )
