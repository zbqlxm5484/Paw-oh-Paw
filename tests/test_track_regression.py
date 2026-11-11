"""실제 관절점 회귀 테스트: 제니 관절점(data/tracks/, 기업 데이터라 저장소에 없음)으로 문서에 적은 수치가 그대로 나오는지 본다.
S15P31A404-260

엔진을 고쳤을 때 문서(docs/engine/gaitMetrics.md 4절, jointRom.md 5절)의 수치가 몰래 바뀌지 않게 하려는 것이다.
값이 바뀌어야 하는 수정이면 문서와 이 파일의 기댓값을 같이 고친다. 관절점 파일이 없으면(CI 등) 건너뛴다.
"""
import json
import statistics
from pathlib import Path

import pytest

pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
FS_V4 = ROOT / "data" / "tracks" / "fs-v4.track.json"
pytestmark = pytest.mark.skipif(not FS_V4.exists(), reason="data/tracks/fs-v4.track.json 없음 (기업 데이터)")


@pytest.fixture(scope="module")
def summary():
    from engine.gait_metrics import summarize_track
    return summarize_track(str(FS_V4))


@pytest.fixture(scope="module")
def rom():
    from engine.gait_metrics import summarize_track
    from engine.joint_rom import joint_metrics
    return summarize_track(str(FS_V4), joint_metrics)


def median(xs):
    return round(statistics.median(xs), 1)


def test_validity_counts():
    """영상 26개 중 25개 유효, 260820-144036은 뛰어서(RUNNING) 무효. 유효 통과 26개"""
    from engine.validity import judge_shot, load_config
    cfg = load_config()
    data = json.loads(FS_V4.read_text(encoding="utf-8"))
    results = {Path(v["video"]).name: judge_shot(v, cfg) for v in data["videos"]}
    invalid = {name: r["validity_reason"] for name, r in results.items() if r["validity"] != "valid"}
    assert invalid == {"260820-144036-제니-9.8kg-main.mp4": "RUNNING"}
    assert sum(r["summary"]["used"] for r in results.values()) == 26


def test_gait_metrics_match_doc(summary):
    """docs/engine/gaitMetrics.md 4절 표 (fs-v4)"""
    v = summary["values"]
    assert summary["valid_passes"] == 26
    assert (median(v["stride_length_front"]), median(v["stride_length_hind"])) == (352.3, 374.0)
    assert (median(v["stance_ratio_front"]), median(v["stance_ratio_hind"])) == (42.9, 35.7)
    assert round(statistics.median(v["walk_speed"]), 1) == 7.9
    assert (len(v["stride_length_front"]), len(v["stride_length_hind"])) == (17, 13)    # 주기를 잰 통과


def test_joint_rom_match_doc(rom):
    """docs/engine/jointRom.md 5절 표 (fs-v4 열)"""
    v = rom["values"]
    expected = {"shoulder": 32.4, "elbow": 63.4, "carpus": 109.3, "hip": 39.1, "stifle": 51.5, "tarsus": 48.8}
    assert {j: median(v[f"rom_{j}"]) for j in expected} == expected
    assert median(v["angle_median_carpus"]) == 186.7          # 180° 넘음: 디딤 때 앞발목 과신전
    assert len(v["stifle_cycle_rom"]) == 13
    assert not [k for k, _ in rom["missing"] if k.startswith("rom_")]   # 가동 범위 측정 불가 0건


def test_same_input_same_output():
    """같은 관절점이면 결과가 값과 순서까지 같다(재현성). 집합 순서나 난수에 기대지 않는지 본다"""
    from engine.gait_metrics import summarize_track
    a, b = summarize_track(str(FS_V4)), summarize_track(str(FS_V4))
    assert a == b and list(a["values"]) == list(b["values"])
