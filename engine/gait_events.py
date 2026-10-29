"""착지·이지 시점 검출 초안 (F-02, PR-F02-02).

발끝이 땅에 닿아 있는 동안은 화면에서 거의 움직이지 않는다(카메라가 고정이라서). 그래서 발끝 속도가 낮은
구간을 "디딤(입각기)"으로 보고, 그 구간이 시작되는 프레임을 착지, 끝나고 발이 다시 움직이는 프레임을 이지로 낸다.

- 착지(touchdown): 발이 땅에 닿는 순간. 디딤 구간의 첫 프레임
- 이지(liftoff): 발이 땅에서 떨어지는 순간. 디딤 구간이 끝난 뒤 첫 프레임
- 보행 주기(stride): 같은 발의 착지에서 다음 착지까지

속도는 몸통 길이 L(T13과 장골능 사이 거리)로 나눈 "몸통 길이/초"로 잰다. 개 크기와 카메라 거리에 상관없이
같은 기준을 쓰기 위해서다. 디딤 기준은 고정값과 몸통 속도 비율 중 큰 쪽이라, 평보처럼 느린 보행과 속보처럼
빠른 보행 모두에 맞춰진다.

입력은 통과 하나의 프레임들이다(유효 판별에서 자른 구간). 카메라 쪽 다리만 넣는다(PR-F02-04).
관절점 번호는 세부명세서 6.5.3절, `engine/camera_side.py`와 같다.

기준값은 데이터로 맞추기 전의 처음 값이다. 정답 대조(S15P31A404-160)에서 바꾼다.
"""
import math
import statistics
from dataclasses import dataclass, field
from typing import Optional, Sequence

EVENTS_VERSION = "v0"

T13, ILIAC = 2, 13
CONF = 0.3                  # 관절점 확신도 바닥 (paw_eval과 같음)
PAWS = {                    # 카메라 쪽 다리의 발끝 번호
    "right": {"front": 12, "hind": 21},
    "left": {"front": 7, "hind": 17},
}

SMOOTH_FRAMES = 5           # 발끝 속도 이동 중앙값 창 (PR-F02-03 흔들림 처리)
STANCE_MIN_SPEED = 0.15     # 몸통 길이/초. 디딤으로 보는 속도 바닥 (몸통이 거의 안 움직일 때)
STANCE_RATIO = 0.25         # 몸통 속도의 이 비율보다 느리면 디딤
MIN_STANCE_S = 0.06         # 이보다 짧은 디딤은 흔들림으로 보고 버림
MAX_GAP_FRAMES = 2          # 디딤 구간 안에서 관절점이 빠져도 이어 붙이는 최대 프레임 수

Point = Optional[Sequence[float]]   # (x, y, 확신도) 또는 None
Frame = Optional[Sequence[Point]]   # 22점 또는 None(개 없음)


@dataclass(frozen=True)
class Stance:
    """디딤 한 번. touchdown·liftoff가 None이면 통과 처음이나 끝에 걸려 그 순간을 못 봤다는 뜻"""

    touchdown: Optional[int]
    liftoff: Optional[int]
    first_frame: int        # 디딤으로 판정한 첫 프레임
    last_frame: int         # 디딤으로 판정한 마지막 프레임


@dataclass(frozen=True)
class Stride:
    """보행 주기 한 번. 착지에서 다음 착지 바로 전까지"""

    start: int              # 착지 프레임
    end: int                # 다음 착지 프레임 (포함하지 않음)
    stance_frames: int

    @property
    def stance_ratio(self) -> float:
        """입각기 비율: 한 주기 중 발이 땅에 닿아 있는 시간의 비율"""
        return self.stance_frames / (self.end - self.start)


@dataclass
class PawEvents:
    paw: str                # "front" 또는 "hind"
    slot: int               # 발끝 관절점 번호
    stances: list = field(default_factory=list)
    strides: list = field(default_factory=list)

    def touchdowns(self) -> list:
        return [s.touchdown for s in self.stances if s.touchdown is not None]

    def liftoffs(self) -> list:
        return [s.liftoff for s in self.stances if s.liftoff is not None]


def _point(frame: Frame, slot: int, conf: float = CONF) -> Optional[tuple]:
    if frame is None:
        return None
    p = frame[slot]
    if p is None or (len(p) > 2 and p[2] < conf):
        return None
    return float(p[0]), float(p[1])


def body_length(frames: Sequence[Frame]) -> Optional[float]:
    """통과 전체의 몸통 길이 중앙값. 프레임마다 쓰지 않고 하나로 둬서 길이 흔들림이 속도에 섞이지 않게 한다"""
    lengths = []
    for f in frames:
        a, b = _point(f, T13), _point(f, ILIAC)
        if a and b:
            d = math.hypot(a[0] - b[0], a[1] - b[1])
            if d > 1e-6:
                lengths.append(d)
    return statistics.median(lengths) if lengths else None


def _speeds(points: list, fps: float, length: float) -> list:
    """프레임별 속도(몸통 길이/초). 앞뒤 프레임 차이로 재고, 어느 한쪽이 없으면 한쪽 차이로 잰다"""
    n = len(points)
    out = [None] * n
    for i in range(n):
        prev = points[i - 1] if i > 0 else None
        nxt = points[i + 1] if i + 1 < n else None
        cur = points[i]
        if prev and nxt:
            dx, dy, dt = nxt[0] - prev[0], nxt[1] - prev[1], 2
        elif cur and nxt:
            dx, dy, dt = nxt[0] - cur[0], nxt[1] - cur[1], 1
        elif prev and cur:
            dx, dy, dt = cur[0] - prev[0], cur[1] - prev[1], 1
        else:
            continue
        out[i] = math.hypot(dx, dy) * fps / dt / length
    return out


def _moving_median(values: list, window: int) -> list:
    half = window // 2
    out = []
    for i in range(len(values)):
        near = [v for v in values[max(0, i - half): i + half + 1] if v is not None]
        out.append(statistics.median(near) if values[i] is not None and near else None)
    return out


def _runs(mask: list, max_gap: int) -> list:
    """True가 이어진 구간 [(첫, 마지막)]. None(관절점 없음)은 max_gap 프레임까지 구간 안으로 이어 붙인다"""
    runs, start, last, gap = [], None, None, 0
    for i, m in enumerate(mask):
        if m is True:
            if start is None:
                start = i
            last, gap = i, 0
        elif m is None and start is not None and gap < max_gap:
            gap += 1
        else:
            if start is not None:
                runs.append((start, last))
            start, last, gap = None, None, 0
    if start is not None:
        runs.append((start, last))
    return runs


def detect_paw(frames: Sequence[Frame], fps: float, slot: int, paw: str = "",
               length: Optional[float] = None, body_speed: Optional[float] = None) -> PawEvents:
    """발 하나의 착지·이지와 보행 주기"""
    events = PawEvents(paw=paw, slot=slot)
    length = length or body_length(frames)
    if not length or fps <= 0:
        return events
    if body_speed is None:
        body_speed = trunk_speed(frames, fps, length) or 0.0

    speeds = _moving_median(_speeds([_point(f, slot) for f in frames], fps, length), SMOOTH_FRAMES)
    limit = max(STANCE_MIN_SPEED, STANCE_RATIO * body_speed)
    mask = [None if s is None else s < limit for s in speeds]
    min_frames = max(1, math.ceil(MIN_STANCE_S * fps))

    n = len(frames)
    for first, last in _runs(mask, MAX_GAP_FRAMES):
        if last - first + 1 < min_frames:
            continue
        seen_start = first > 0 and mask[first - 1] is False      # 직전 프레임에 발이 움직이는 걸 봤나
        seen_end = last + 1 < n and mask[last + 1] is False
        events.stances.append(Stance(
            touchdown=first if seen_start else None,
            liftoff=last + 1 if seen_end else None,
            first_frame=first,
            last_frame=last,
        ))

    for a, b in zip(events.stances, events.stances[1:]):
        if a.touchdown is None or b.touchdown is None:
            continue
        events.strides.append(Stride(start=a.touchdown, end=b.touchdown,
                                     stance_frames=a.last_frame - a.first_frame + 1))
    return events


def trunk_speed(frames: Sequence[Frame], fps: float, length: float) -> Optional[float]:
    """몸통 가운데의 속도 중앙값(몸통 길이/초). 통과의 대표 보행 속도"""
    centers = []
    for f in frames:
        a, b = _point(f, T13), _point(f, ILIAC)
        centers.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) if a and b else None)
    speeds = [s for s in _speeds(centers, fps, length) if s is not None]
    return statistics.median(speeds) if speeds else None


def detect_pass(frames: Sequence[Frame], fps: float, camera_side: str) -> dict:
    """통과 하나에서 카메라 쪽 앞발·뒷발의 착지·이지. 몸통 길이를 못 재면 빈 결과"""
    length = body_length(frames)
    if not length:
        return {}
    speed = trunk_speed(frames, fps, length) or 0.0
    return {
        paw: detect_paw(frames, fps, slot, paw=paw, length=length, body_speed=speed)
        for paw, slot in PAWS[camera_side].items()
    }
