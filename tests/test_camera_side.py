from engine.camera_side import camera_side, pass_side


def make_kp(t13, iliac, conf=1.0):
    kp = [(0.0, 0.0, 1.0)] * 22
    kp[2] = (*t13, conf)
    kp[13] = (*iliac, conf)
    return kp


def test_head_right_is_right():
    assert camera_side(make_kp((100, 50), (0, 50))) == "right"


def test_head_left_is_left():
    assert camera_side(make_kp((0, 50), (100, 50))) == "left"


def test_front_view_is_none():
    assert camera_side(make_kp((0, 0), (10, 50))) is None


def test_low_confidence_is_none():
    assert camera_side(make_kp((100, 50), (0, 50), conf=0.1)) is None


def test_pass_majority_vote():
    r, l = make_kp((100, 50), (0, 50)), make_kp((0, 50), (100, 50))
    assert pass_side([r, r, l]) == "right"
    assert pass_side([make_kp((0, 0), (10, 50))]) is None