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
