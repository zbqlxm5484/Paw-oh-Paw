"""사유 문장(engine/reasons.py) 테스트. 유효 판별 테스트의 가상 개로 사유마다 잰 값과 기준값이 문장에 들어가는지 본다."""
import re
from pathlib import Path

import pytest

pytest.importorskip("yaml")

from test_validity import walk  # noqa: E402

from engine.reasons import REASON_TEXT, pass_reason_detail  # noqa: E402
from engine.validity import judge_shot, load_config  # noqa: E402

SPEC = Path(__file__).resolve().parents[1] / "backend" / "docs" / "backend-spec.md"
# 보고서 금지 표현(backend/app/report/terms.yaml)의 대표 패턴: 문장이 진단·원인·정상 여부를 단정하지 않아야 한다
FORBIDDEN = re.compile(r"진단|소견|의심|추정|원인|때문|아프|통증|파행|정상|이상\s?(이|가)\s?있|위험|질환|질병")


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def _pass(result):
    return next(p for p in result["passes"] if p["reason_code"])


def test_running_detail_has_measured_speed_and_threshold(cfg):
    r = judge_shot(walk(speed=2200.0, seconds=1.5), cfg)
    p = _pass(r)
    assert p["reason_code"] == "RUNNING"
    assert f"{p['checks']['speed_body_per_s']:.1f}배" in p["reason_detail"]
    assert "11배" in p["reason_detail"]
    assert r["validity_reason_text"].startswith(f"{p['index']}번 통과: ")     # 어느 통과 때문인지


def test_stopped_and_sitting_details(cfg):
    stop = lambda t: (0.0 if 1.0 <= t < 2.0 else 1.0, 1, 500.0)
    sit = lambda t: (0.0 if 1.0 <= t < 2.0 else 1.0, 1, 620.0 if 1.0 <= t < 2.0 else 500.0)
    p = _pass(judge_shot(walk(seconds=4.0, plan=stop), cfg))
    assert p["reason_code"] == "STOPPED" and "초 동안 멈췄습니다(기준 0.5초)" in p["reason_detail"]
    p = _pass(judge_shot(walk(seconds=4.0, plan=sit), cfg))
    assert p["reason_code"] == "SITTING" and "골반 높이" in p["reason_detail"]


def test_turned_and_partial_details(cfg):
    turn = lambda t: (-1.0, -1, 500.0) if 1.0 <= t < 1.6 else (1.0, 1, 500.0)
    p = _pass(judge_shot(walk(seconds=4.0, plan=turn), cfg))
    assert p["reason_code"] == "TURNED" and "한 방향으로" in p["reason_detail"]
    p = _pass(judge_shot(walk(seconds=1.4), cfg))
    assert p["reason_code"] == "PARTIAL_PASS" and "영상이 끝났습니다" in p["reason_detail"]


def test_no_dog_shot_text(cfg):
    r = judge_shot({"fps": 30, "width": 1920, "height": 1080, "frames": [None] * 90}, cfg)
    assert r["validity_reason"] == "NO_DOG" and "0%뿐입니다" in r["validity_reason_text"]


def test_valid_shot_has_no_text(cfg):
    r = judge_shot(walk(), cfg)
    assert r["validity_reason_text"] is None and r["passes"][0]["reason_detail"] is None


def test_details_avoid_report_forbidden_words(cfg):
    checks = {"speed_body_per_s": 13.2, "stopped_s": 0.8, "sitting_s": 0.7, "opposite_ratio": 0.3, "reverse_s": 0.5,
              "height_scale": 1.5, "inside_s": 0.2, "side_view_ratio": 0.6, "occluded_ratio": 0.4, "no_dog_ratio": 0.5}
    for code in REASON_TEXT:
        text = pass_reason_detail(code, checks, cfg)
        assert text and not FORBIDDEN.search(text), (code, text)


def test_base_text_matches_backend_spec_14_3():
    """기본 문장은 백엔드 명세 14.3 표와 글자까지 같다 (저장소 안에서만 확인)"""
    if not SPEC.is_file():
        pytest.skip("backend/docs/backend-spec.md 없음")
    section = SPEC.read_text(encoding="utf-8").split("### 14.3", 1)[1].split("### 14.4", 1)[0]
    spec = {m.group(1): m.group(2).strip() for m in re.finditer(r"^\| `([A-Z_]+)` \| [^|]+ \| ([^|]+) \|", section, re.M)}
    for code, text in REASON_TEXT.items():
        assert spec.get(code) == text, code
