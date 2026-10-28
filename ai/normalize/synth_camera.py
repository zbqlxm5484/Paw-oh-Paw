"""카메라 오차 합성 — 영상 프레임과 관절점에 같은 변환을 적용한다. 검토용 구현이며 기업 확인 전이다.

    python synth_camera.py --video a.mp4 --track a.track.json --out-dir out/ [--only yaw,roll] [--sample]
    python synth_camera.py --track a.track.json --out-dir out/ --points-only     # 영상 없이 관절점만
    python synth_camera.py --self-test

정규화가 카메라 위치·각도에 흔들리지 않는지 보려고, 한 영상을 여러 "가짜 카메라" 로 다시 찍은 것처럼 만든다.
변환은 모두 3x3 호모그래피 H 하나로 적고, 프레임(cv2.warpPerspective)과 관절점·상자에 똑같이 곱한다.

- yaw / pitch / roll: 카메라가 제자리에서 도는 것. H = K R K^-1 (K = 카메라 내부 행렬, 기본 f 는 촬영 카메라 보정값
  715~775px 의 가운데 745px @1920). 제자리 회전은 이 식이 정확하다. 위치가 바뀌는 것(앞뒤 이동)은 아래 zoom 으로 근사.
- zoom: 화면 가운데 기준 확대·축소(카메라 거리·화각 차이).
- shift_x / shift_y: 화면 안 위치 이동(카메라 높이·좌우 위치 차이). 화면 크기 비율.

범위(RANGES)는 10-26 실제 촬영 4대(260820 main·sub1~3, 72건) 차이를 근거로 정했다(docs/normalize/synthCamera.md).
변환 값(정답)은 영상마다 <이름>.json 에 H 와 함께 적는다. 관절점은 원본 track 의 kp 를 변환한 것으로,
모델이 합성 영상에서 다시 낸 관절점과 비교하는 기준이 된다.
"""

import argparse
import copy
import json
import math
import sys
from pathlib import Path

import numpy as np

F_DEFAULT, W_REF = 745.0, 1920.0
# 종류 -> 값 목록. 각도는 도, zoom 은 배율, shift 는 화면 크기 비율.
RANGES = {
    "roll": [-4, -2, 2, 4],
    "yaw": [-15, -10, -5, 5, 10, 15],
    "pitch": [-10, -5, 5, 10],
    "zoom": [0.8, 0.9, 1.1, 1.2],
    "shift_x": [-0.05, 0.05],
    "shift_y": [-0.08, -0.04, 0.04, 0.08],
}

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def intrinsics(W, H, f=None):
    f = f or F_DEFAULT * W / W_REF
    return np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1.0]])


def homography(kind, value, W, H, f=None):
    K = intrinsics(W, H, f)
    if kind in ("yaw", "pitch", "roll"):
        a = math.radians(value)
        c, s = math.cos(a), math.sin(a)
        R = {
            "yaw": [[c, 0, s], [0, 1, 0], [-s, 0, c]],
            "pitch": [[1, 0, 0], [0, c, -s], [0, s, c]],
            "roll": [[c, -s, 0], [s, c, 0], [0, 0, 1]],
        }[kind]
        return K @ np.array(R) @ np.linalg.inv(K)
    if kind == "zoom":
        return np.array(
            [[value, 0, (1 - value) * W / 2], [0, value, (1 - value) * H / 2], [0, 0, 1.0]]
        )
    if kind == "shift_x":
        return np.array([[1, 0, value * W], [0, 1, 0], [0, 0, 1.0]])
    if kind == "shift_y":
        return np.array([[1, 0, 0], [0, 1, value * H], [0, 0, 1.0]])
    raise ValueError(kind)


def warp_points(Hm, pts):
    p = np.asarray(pts, float)
    q = np.c_[p[:, :2], np.ones(len(p))] @ Hm.T
    return q[:, :2] / q[:, 2:3]


def warp_frame(f, Hm, W, H):
    """track 프레임 하나 -> 변환한 프레임. 화면 밖으로 나간 관절점은 확신도 0, 상자는 네 꼭짓점을 변환해 감싼다."""
    if f is None:
        return None
    kp = warp_points(Hm, [k[:2] for k in f["kp"]])
    x0, y0, x1, y1 = f["box"]
    c = warp_points(Hm, [[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    box = [
        max(0.0, c[:, 0].min()),
        max(0.0, c[:, 1].min()),
        min(W, c[:, 0].max()),
        min(H, c[:, 1].max()),
    ]
    if box[2] - box[0] < 2 or box[3] - box[1] < 2:
        return None
    out = []
    for (x, y), k in zip(kp, f["kp"]):
        inside = 0 <= x < W and 0 <= y < H
        out.append([round(float(x), 2), round(float(y), 2), k[2] if inside else 0.0])
    return {"box": [round(float(v), 2) for v in box], "kp": out}


def warp_track_video(v, Hm):
    W, H = v["width"], v["height"]
    nv = copy.deepcopy({k: v[k] for k in v if k != "frames"})
    nv["frames"] = [warp_frame(f, Hm, W, H) for f in v["frames"]]
    return nv


def warp_video(src, dst, Hm):
    import cv2

    cap = cv2.VideoCapture(str(src))
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    wr = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    n = 0
    while True:
        ok, im = cap.read()
        if not ok:
            break
        wr.write(
            cv2.warpPerspective(
                im, Hm, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT
            )
        )
        n += 1
    cap.release()
    wr.release()
    return n


def plan(only=None):
    return [(k, v) for k, vals in RANGES.items() if not only or k in only for v in vals]


def name_of(stem, kind, value):
    return f"{stem}.{kind}{value:+g}"


def run(a):
    tr = json.loads(Path(a.track).read_text(encoding="utf-8"))
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    only = set(a.only.split(",")) if a.only else None
    vids = tr["videos"]
    if a.video:
        stem = Path(a.video).name
        vids = [v for v in vids if v["video"] == stem]
        if not vids:
            sys.exit(f"track 에 {stem} 이 없다")
    items = plan(only)
    if a.sample:  # 종류마다 가장 큰 값 하나
        items = [(k, max(vals, key=abs)) for k, vals in RANGES.items() if not only or k in only]
    for v in vids:
        W, H = v["width"], v["height"]
        stem = Path(v["video"]).stem
        for kind, val in items:
            Hm = homography(kind, val, W, H, a.focal)
            nm = name_of(stem, kind, val)
            nt = dict(tr, videos=[dict(warp_track_video(v, Hm), video=nm + ".mp4")])
            nt["meta"] = dict(
                tr["meta"], synth_camera={"kind": kind, "value": val, "source": v["video"]}
            )
            (out / f"{nm}.track.json").write_text(json.dumps(nt), encoding="utf-8")
            frames = None
            if a.video and not a.points_only:
                frames = warp_video(a.video, out / f"{nm}.mp4", Hm)
            info = {
                "name": nm,
                "source": v["video"],
                "kind": kind,
                "value": val,
                "unit": "deg" if kind in ("yaw", "pitch", "roll") else "ratio",
                "focal_px": float(intrinsics(W, H, a.focal)[0, 0]),
                "size": [W, H],
                "H": Hm.round(8).tolist(),
                "frames": frames,
            }
            (out / f"{nm}.json").write_text(
                json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            print(f"-> {nm}" + (f" ({frames} 프레임)" if frames else ""))


def self_test():
    W, H = 1920, 1080
    I = np.eye(3)
    for k in RANGES:
        assert np.allclose(homography(k, 0 if k != "zoom" else 1.0, W, H), I), k
    # 화면 가운데는 roll·zoom 에서 안 움직인다
    for k, v in (("roll", 4), ("zoom", 1.2)):
        assert np.allclose(
            warp_points(homography(k, v, W, H), [[W / 2, H / 2]]), [[W / 2, H / 2]]
        ), k
    # yaw 는 가운데 점을 f*tan(a) 만큼 옆으로 민다
    p = warp_points(homography("yaw", 10, W, H), [[W / 2, H / 2]])[0]
    assert (
        abs(p[0] - (W / 2 + F_DEFAULT * math.tan(math.radians(10)))) < 1e-6
        and abs(p[1] - H / 2) < 1e-6
    ), p
    # 같은 변환을 되돌리면 원래 점
    Hm = homography("pitch", 7, W, H)
    q = warp_points(np.linalg.inv(Hm), warp_points(Hm, [[100, 200], [1500, 900]]))
    assert np.allclose(q, [[100, 200], [1500, 900]])
    # 화면 밖으로 나간 점은 확신도 0
    f = {"box": [1800, 500, 1900, 600], "kp": [[1850, 550, 0.9]] * 22}
    g = warp_frame(f, homography("shift_x", 0.05, W, H), W, H)
    assert g["kp"][0][2] == 0.0 and g["box"][2] == W, g
    print("self-test OK")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--video", help="원본 영상. 없으면 track 의 영상 전부를 관절점만 변환")
    ap.add_argument("--track", help="paw_eval video_kpi track json (원본 관절점)")
    ap.add_argument("--out-dir")
    ap.add_argument("--only", help="쉼표로 종류 제한: " + ",".join(RANGES))
    ap.add_argument("--sample", action="store_true", help="종류마다 가장 큰 값 하나만")
    ap.add_argument("--points-only", action="store_true", help="영상은 만들지 않는다")
    ap.add_argument(
        "--focal", type=float, help="초점 거리(px). 기본은 보정값 745px 를 화면 너비에 맞춰 늘림"
    )
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not (a.track and a.out_dir):
        ap.error("--track 과 --out-dir 이 필요하다")
    run(a)


if __name__ == "__main__":
    main()
