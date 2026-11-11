"""착지·이지 정답 대조(engine/gait_eval.py)와 시간 기준값 변환 테스트"""
from engine.gait_eval import evaluate, load_gt, match
from engine.gait_events import frames_for


def test_frames_for_follows_fps():
    assert frames_for(0.15, 30, odd=True) == 5
    assert frames_for(0.15, 60, odd=True) == 9
    assert frames_for(0.05, 30) == 2 and frames_for(0.05, 60) == 3


def test_match_pairs_nearest_first():
    errors, missed, extra = match([10, 30, 50], [11, 29, 70], tol=3)
    assert sorted(errors) == [-1, 1]
    assert missed == 1 and extra == 1


def test_match_uses_each_detection_once():
    errors, missed, extra = match([10, 12], [11], tol=3)
    assert len(errors) == 1 and missed == 1 and extra == 0


def test_load_gt_groups_by_marker(tmp_path):
    p = tmp_path / "gt.csv"
    p.write_text("video,paw,event,frame,marker\n"
                 "a.mp4,front,touchdown,30,A\n"
                 "a.mp4,front,touchdown,10,A\n"
                 "a.mp4,front,touchdown,11,B\n"
                 "# 메모 줄,,,0,\n", encoding="utf-8")
    gt = load_gt(p)
    assert gt[("a.mp4", "front", "touchdown")]["A"] == [10, 30]
    assert gt[("a.mp4", "front", "touchdown")]["B"] == [11]


def test_evaluate_reports_videos_missing_from_track():
    res = evaluate({}, {("none.mp4", "front", "touchdown"): {"A": [5]}})
    assert res["videos_without_track"] == ["none.mp4"]
    assert res["rows"] == {}


def test_evaluate_on_virtual_walk_meets_kpi05():
    """정답을 아는 가상 보행(test_gait_events)으로 대조 전체를 돌린다. 착지·이지를 맞히고 KPI-05(2프레임) 안.
    뒷발 첫 이지(3프레임)만 못 찾는다: 영상 첫 프레임부터 이어진 디딤이 3프레임이라 최소 디딤(0.06초, 4프레임)보다 짧다.
    두 번째 표시자는 정답보다 1프레임 늦게 찍은 것으로 넣어 사람 사이 차이(약 16.7ms)도 나오는지 본다"""
    from test_gait_events import FPS, make_frames, true_events

    n, phases = 150, {"front": 0.0, "hind": 0.2}
    frames = make_frames(n=n)
    gt = {}
    for paw, phase in phases.items():
        tds, los = true_events(n, phase)
        for event, truth in (("touchdown", tds), ("liftoff", los)):
            gt[("v.mp4", paw, event)] = {"A": truth, "B": [t + 1 for t in truth]}
    res = evaluate({"v.mp4": (FPS, frames)}, gt)
    assert set(res["rows"]) == {"front/touchdown", "front/liftoff", "hind/touchdown", "hind/liftoff"}
    for name, row in res["rows"].items():
        assert row["hit_rate"] == (0.857 if name == "hind/liftoff" else 1.0), (name, row)   # 6/7, 셋째 자리 반올림
        assert row["extra"] == 0, (name, row)
        assert row["median_error_frames"] <= 1 and row["kpi05_ok"], (name, row)
    assert all(abs(ms - 1000 / FPS) < 0.1 for ms in res["human_median_ms"].values())
