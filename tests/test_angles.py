from engine.angles import angle_at, flexion_angle


def test_straight_line_is_180():
    assert angle_at((0, 0), (-1, 0), (1, 0)) == 180


def test_right_angle_is_90():
    assert round(angle_at((0, 0), (1, 0), (0, 1)), 6) == 90


def test_zero_length_arm_returns_none():
    assert angle_at((0, 0), (0, 0), (1, 0)) is None


def test_flex_side_decides_90_or_270():
    v, a, b, cranial = (0, 0), (1, 1), (1, -1), (1, 0)
    assert round(flexion_angle(v, a, b, cranial, +1), 6) == 90
    assert round(flexion_angle(v, a, b, cranial, -1), 6) == 270