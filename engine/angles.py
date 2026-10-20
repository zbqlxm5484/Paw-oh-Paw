"""관절각 정의 — PRD 6.2.1 표를 코드로 옮긴 것.

굽히는 쪽 면에서 잰 0~360 이다. 180 초과 = 과신전. arccos(0~180)는 꺾인 방향을 모르고
180 양쪽을 접어 오차를 작게 보이게 한다(같은 예측으로 15.2° vs 17.9°).

정의가 바뀌면 ANGLE_DEF 를 올리고 CHANGELOG.md 에 적는다. 모든 결과 파일에 ANGLE_DEF 가
기록되므로 정의가 다른 숫자끼리 비교하는 일을 막는다.
"""
import math

ANGLE_DEF = "v1"

# (꼭짓점, 근위 기준, 원위 기준, 관절) — 슬롯 번호는 정답 파일 categories[0].keypoints 순서
JOINTS = [
    (4, 3, 5, "어깨"), (5, 4, 6, "팔꿈치"), (6, 5, 7, "앞발목"),          # 왼쪽 앞다리
    (9, 8, 10, "어깨"), (10, 9, 11, "팔꿈치"), (11, 10, 12, "앞발목"),    # 오른쪽 앞다리
    (14, 13, 15, "고관절"), (15, 14, 16, "무릎"), (16, 15, 17, "뒷발목"),  # 왼쪽 뒷다리
    (18, 13, 19, "고관절"), (19, 18, 20, "무릎"), (20, 19, 21, "뒷발목"),  # 오른쪽 뒷다리
]

# 관절이 굽히는 쪽. +1 = 머리 쪽, -1 = 꼬리 쪽. 사지가 지그재그라 번갈아 바뀐다.
FLEX_SIDE = {"어깨": -1, "팔꿈치": +1, "앞발목": -1, "고관절": +1, "무릎": -1, "뒷발목": +1}


def angle_at(v, a, b):
    """∠(a, v, b) 0~180. 두 팔 중 하나라도 길이가 0 이면 None."""
    ux, uy = a[0] - v[0], a[1] - v[1]
    wx, wy = b[0] - v[0], b[1] - v[1]
    nu, nw = math.hypot(ux, uy), math.hypot(wx, wy)
    if nu < 1e-9 or nw < 1e-9:
        return None
    return math.degrees(math.acos(max(-1.0, min(1.0, (ux * wx + uy * wy) / (nu * nw)))))


def _bisector(v, a, b):
    ux, uy = a[0] - v[0], a[1] - v[1]
    wx, wy = b[0] - v[0], b[1] - v[1]
    nu, nw = math.hypot(ux, uy), math.hypot(wx, wy)
    sx, sy = ux / nu + wx / nw, uy / nu + wy / nw
    if math.hypot(sx, sy) < 1e-6:          # 두 팔이 거의 일직선이면 수직 방향
        sx, sy = -uy, ux
    n = math.hypot(sx, sy)
    return sx / n, sy / n


def flexion_angle(v, a, b, cranial, flex_side):
    """굽히는 쪽 면에서 잰 ∠(a, v, b) 0~360. cranial = 머리 방향 벡터(화면 좌표)."""
    d = angle_at(v, a, b)
    if d is None:
        return None
    bx, by = _bisector(v, a, b)
    opens = bx * cranial[0] + by * cranial[1]
    return d if opens * flex_side >= 0 else 360.0 - d
