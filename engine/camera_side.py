"""카메라 쪽 다리 판정 — 기업 paw_eval(score.py, video_kpi.py)과 같은 규칙."""
import math

T13, ILIAC = 2, 13          # 등뼈 중간, 장골능(골반 윗부분)
CONF = 0.3                  # 관절점 확신도 바닥 (기업 서비스와 같음)
SIDE_MIN = 0.5              # |가로 차이| / 몸통 길이 가 이보다 작으면 옆모습 아님 → 판정 안 함
LEFT = {0, 3, 4, 5, 6, 7, 14, 15, 16, 17}
RIGHT = {1, 8, 9, 10, 11, 12, 18, 19, 20, 21}


def heading(kp, conf=CONF):
    """+1 = 머리가 화면 오른쪽, -1 = 왼쪽, None = 판정 불가. kp[i] = (x, y[, 확신도])"""
    a, b = kp[T13], kp[ILIAC]
    if (len(a) > 2 and a[2] < conf) or (len(b) > 2 and b[2] < conf):
        return None
    dx, dy = a[0] - b[0], a[1] - b[1]
    length = math.hypot(dx, dy)
    if length < 1e-6 or abs(dx) / length < SIDE_MIN:
        return None
    return 1 if dx > 0 else -1


def camera_side(kp):
    """프레임 하나 → 'right' / 'left' / None (기업 규칙: 머리가 오른쪽이면 right)"""
    h = heading(kp)
    return None if h is None else ("right" if h > 0 else "left")


def near_slots(side):
    """카메라 쪽 다리의 관절 번호 집합"""
    return RIGHT if side == "right" else LEFT


def pass_side(frames):
    """통과 한 번(프레임 여러 장) → 다수결. 동률이면 left (기업 코드와 같음)"""
    signs = [h for h in (heading(kp) for kp in frames) if h is not None]
    if not signs:
        return None
    return "right" if sum(signs) > 0 else "left"