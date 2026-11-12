"""촬영 판정(engine/validity.py judge_shot)의 갈래와 보행 위상(lateral_phase), 촬영 사유 문장 테스트. S15P31A404-260

통과를 하나씩 만들어 보는 test_validity.py와 달리, 여기서는 통과 판정 결과를 정해 넣고(find_passes·check_pass를 바꿔 끼움)
촬영 한 건이 valid·partial·invalid 중 무엇이 되는지, 사유가 무엇인지만 본다. 결과 형식 2절·4절, 유효 판별 규칙 4.2절.
"""
import pytest

pytest.importorskip("yaml")

from engine import validity  # noqa: E402
from engine.gait_events import PawEvents, Stance, Stride  # noqa: E402
from engine.reasons import REASON_TEXT, pass_reason_detail, shot_reason_detail  # noqa: E402
from engine.validity import (  # noqa: E402
    SHOT_INVALID_REASONS,
    judge_shot,
    lateral_phase,
    load_config,
)


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def scripted(monkeypatch, codes, found=1.0):
    """통과마다 사유 코드(None이면 유효)를 정해 둔 촬영. found는 개를 찾은 프레임 비율"""
    n = 100
    frames = [{"kp": None}] * round(n * found) + [None] * (n - round(n * found))
    monkeypatch.setattr(validity, "find_passes", lambda video, cfg: [(i * 10, i * 10 + 9, 1) for i in range(len(codes))])
    results = iter(codes)

    def check(video, a, b, head, cfg):
        return {"reason_code": next(results), "camera_side": "right", "measure_start": a, "measure_end": b,
                "checks": {}}

    monkeypatch.setattr(validity, "check_pass", check)
    return {"fps": 30, "width": 1920, "height": 1080, "frames": frames}


def test_all_valid(monkeypatch, cfg):
    r = judge_shot(scripted(monkeypatch, [None, None]), cfg)
    assert (r["validity"], r["validity_reason"], r["validity_reason_text"]) == ("valid", None, None)
    assert r["summary"] == {"passes": 2, "used": 2, "excluded": 0}
    assert all(p["reason"] is None and p["reason_detail"] is None for p in r["passes"])


def test_company_reason_makes_whole_shot_invalid_even_with_valid_passes(monkeypatch, cfg):
    """기업 무효 사유가 붙은 통과가 하나라도 있으면 나머지가 유효여도 촬영 전체가 invalid"""
    for code in sorted(SHOT_INVALID_REASONS):
        r = judge_shot(scripted(monkeypatch, [None, code, None]), cfg)
        assert (r["validity"], r["validity_reason"]) == ("invalid", code), code
        assert r["validity_reason_text"].startswith("2번 통과: ")


def test_first_company_reason_is_the_shot_reason(monkeypatch, cfg):
    r = judge_shot(scripted(monkeypatch, ["RUNNING", "STOPPED"]), cfg)
    assert r["validity_reason"] == "RUNNING"


def test_other_reasons_only_exclude_the_pass(monkeypatch, cfg):
    """기업 무효 사유가 아닌 제외(옆모습 아님 등)는 그 통과만 빼고 촬영은 partial"""
    assert cfg["shot_rules"]["min_valid_passes"] == 2
    r = judge_shot(scripted(monkeypatch, [None, "NOT_SIDE_VIEW", None]), cfg)
    assert (r["validity"], r["validity_reason"]) == ("partial", None)       # 유효 2개면 사유 없음
    r = judge_shot(scripted(monkeypatch, [None, "NOT_SIDE_VIEW"]), cfg)
    assert (r["validity"], r["validity_reason"]) == ("partial", "FEW_VALID_PASSES")
    assert "1번으로 기준(2번)" in r["validity_reason_text"]


def test_no_usable_pass(monkeypatch, cfg):
    r = judge_shot(scripted(monkeypatch, ["NOT_SIDE_VIEW", "OCCLUDED"]), cfg)
    assert (r["validity"], r["validity_reason"]) == ("invalid", "NO_VALID_PASS")
    assert r["summary"] == {"passes": 2, "used": 0, "excluded": 2}
    r = judge_shot(scripted(monkeypatch, []), cfg)                        # 통과를 하나도 못 찾음
    assert (r["validity"], r["validity_reason"]) == ("invalid", "NO_VALID_PASS")


def test_no_dog_wins_and_skips_pass_search(monkeypatch, cfg):
    """개를 찾은 프레임이 기준보다 적으면 통과를 찾지 않고 NO_DOG"""
    video = scripted(monkeypatch, [None])
    video["frames"] = [None] * 99 + [{"kp": None}]                      # 1% (기준 5%)
    r = judge_shot(video, cfg)
    assert (r["validity"], r["validity_reason"], r["passes"]) == ("invalid", "NO_DOG", [])
    assert "1%뿐입니다(기준 5%)" in r["validity_reason_text"]


# ---- 보행 위상: 같은 쪽 뒷발 착지에서 가장 가까운 앞발 착지까지 / 주기 ----


def events(hind_tds, front_tds):
    def paw(name, tds):
        e = PawEvents(paw=name, slot=0, stances=[Stance(t, t + 5, t, t + 4) for t in tds])
        e.strides = [Stride(a, b, 5) for a, b in zip(tds, tds[1:])]
        return e
    return {"hind": paw("hind", hind_tds), "front": paw("front", front_tds)}


@pytest.mark.parametrize("offset, phase", [(10, 0.5), (0, 0.0), (5, 0.25), (15, 0.25)])
def test_lateral_phase(offset, phase):
    """주기 20프레임. 속보 0.5, 측대보 0, 평보 0.25 (앞발이 15프레임 늦어도 가까운 쪽으로 재면 0.25)"""
    hind = [0, 20, 40, 60]
    assert lateral_phase(events(hind, [t + offset for t in hind])) == pytest.approx(phase)


def test_lateral_phase_needs_two_touchdowns_each():
    assert lateral_phase({}) is None
    assert lateral_phase(events([0, 20], [10])) is None
    assert lateral_phase(events([0], [10, 30])) is None


# ---- 사유 문장의 갈래 ----


def test_pass_detail_falls_back_to_base_text_without_measurements(cfg):
    """잰 값이 checks에 없으면 기본 문장(백엔드 명세 14.3)을 낸다. 코드가 없으면 None"""
    assert pass_reason_detail(None, {}, cfg) is None
    for code in ("RUNNING", "STOPPED", "TURNED", "NOT_SIDE_VIEW", "GAIT_PACE"):
        assert pass_reason_detail(code, {}, cfg) == REASON_TEXT[code]


def test_shot_text_without_reason_or_hit(cfg):
    assert shot_reason_detail(None, [], cfg, 1.0) is None
    # 기업 무효 사유인데 그 사유가 붙은 통과를 못 찾으면 기본 문장
    assert shot_reason_detail("RUNNING", [{"index": 1, "reason_code": None}], cfg, 1.0) == REASON_TEXT["RUNNING"]
    passes = [{"index": 1, "reason_code": "NOT_SIDE_VIEW"}, {"index": 2, "reason_code": "OCCLUDED"}]
    assert shot_reason_detail("NO_VALID_PASS", passes, cfg, 1.0).startswith("통과 2번 중")
