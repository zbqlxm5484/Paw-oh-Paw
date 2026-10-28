"""매트 마커(ArUco 5x5 100~103) + 카메라 내부 파라미터로 '개가 걷는 수직 평면'에 관절점을 투영한다.
- 마커 네 중심 = 바닥 위 직사각형. 마주 보는 변의 소실점 -> 바닥의 두 축 방향, 그 외적 = 바닥 법선
- 걷는 평면 = 매트 긴 축과 바닥 법선을 품고 매트 가운데를 지나는 수직 평면
- 관절점 광선을 그 평면과 만나게 해 (긴 축, 높이) 2차원 좌표를 얻는다. 화면 위치(KPI-02 1/3)는 몸통 가운데로 고정
"""

import collections
import copy
import glob
import json
import os
import re
import sys

import cv2
import numpy as np

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")

sys.path.insert(0, rf"{_PJT}/creamoff_data/paw_eval")
import video_kpi as K  # noqa: E402

ROOT = rf"{_PJT}/creamoff_data/dataset"
A = cv2.aruco
DET = A.ArucoDetector(A.getPredefinedDictionary(A.DICT_5X5_1000))


def markers(path, n=25):
    cap = cv2.VideoCapture(path)
    N = int(cap.get(7))
    got = collections.defaultdict(list)
    for t in np.linspace(0, N - 1, n).astype(int):
        cap.set(1, int(t))
        ok, im = cap.read()
        if not ok:
            continue
        c, ids, _ = DET.detectMarkers(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
        for cc, i in zip(c or [], [] if ids is None else ids.ravel()):
            if 100 <= i <= 103:
                got[int(i)].append(cc.reshape(4, 2).mean(0))
    return {i: np.median(v, 0) for i, v in got.items() if len(v) >= 3}


def intr(date, view):
    f = os.path.join(ROOT, "calibration", f"cams_{date}_intrinsics.json")
    if not os.path.exists(f):
        return None
    d = json.load(open(f, encoding="utf-8")).get(view)
    if not d:
        return None
    Km = np.array([[d["f"][0], 0, d["c"][0]], [0, d["f"][1], d["c"][1]], [0, 0, 1.0]])
    return Km, np.array(d["dist"], float)


def selfcal(mk, W, H):
    """주점 = 화면 가운데, 왜곡 없음 가정. 직사각형 두 소실점이 직각 -> f^2 = -(v1-c).(v2-c)."""
    if len(mk) < 4:
        return None
    P = np.array([mk[i] for i in sorted(mk)])
    h = cv2.convexHull(P.astype(np.float32), returnPoints=False).ravel()
    if len(h) < 4:
        return None
    Q = np.hstack([P[h], np.ones((4, 1))])
    L = lambda p, q: np.cross(p, q)
    c = np.array([W / 2, H / 2])
    vs = []
    for v in (np.cross(L(Q[0], Q[1]), L(Q[3], Q[2])), np.cross(L(Q[1], Q[2]), L(Q[0], Q[3]))):
        if abs(v[2]) < 1e-9:
            return None
        vs.append(v[:2] / v[2] - c)
    f2 = -(vs[0] @ vs[1])
    if f2 <= 0 or not (400 < np.sqrt(f2) < 2500):
        return None
    f = np.sqrt(f2)
    return np.array([[f, 0, c[0]], [0, f, c[1]], [0, 0, 1.0]]), np.zeros(5)


def rays(pts, Km, dist):
    u = cv2.undistortPoints(np.asarray(pts, float).reshape(-1, 1, 2), Km, dist).reshape(-1, 2)
    return np.hstack([u, np.ones((len(u), 1))])


def geometry(mk, Km, dist, motion=None):
    ids = sorted(mk)
    if len(ids) < 4:
        return None
    P = np.array([mk[i] for i in ids])
    hull = cv2.convexHull(P.astype(np.float32), returnPoints=False).ravel()
    if len(hull) < 4:
        return None
    R = rays(P[hull], Km, dist)  # 정규화 좌표(동차) — 볼록 순서
    L = lambda p, q: np.cross(p, q)
    va = np.cross(L(R[0], R[1]), L(R[3], R[2]))
    vb = np.cross(L(R[1], R[2]), L(R[0], R[3]))
    da, db = va / np.linalg.norm(va), vb / np.linalg.norm(vb)
    ortho = abs(
        np.degrees(np.arccos(np.clip(abs(da @ db), 0, 1))) - 90
    )  # 내부 파라미터 검증: 0 이면 직각
    n = np.cross(da, db)
    n /= np.linalg.norm(n)
    if (n @ R.mean(0)) < 0:
        n = -n  # 카메라 -> 바닥 쪽이 +
    X = R / (R @ n)[:, None]  # 바닥 n.X = 1
    la, lb = (
        np.linalg.norm(X[1] - X[0]) + np.linalg.norm(X[2] - X[3]),
        np.linalg.norm(X[2] - X[1]) + np.linalg.norm(X[3] - X[0]),
    )
    a = (X[1] - X[0]) if la > lb else (X[2] - X[1])
    if motion is not None:  # 개가 화면에서 움직인 방향과 더 나란한 바닥 축
        C0 = X.mean(0)
        best = -1
        for cand in (X[1] - X[0], X[2] - X[1]):
            p0, p1 = C0 @ Km.T, (C0 + 0.05 * cand) @ Km.T
            d = p1[:2] / p1[2] - p0[:2] / p0[2]
            c = abs(d @ motion) / (np.linalg.norm(d) * np.linalg.norm(motion) + 1e-9)
            if c > best:
                best, a = c, cand
    a = a - (a @ n) * n
    a /= np.linalg.norm(a)
    C = X.mean(0)
    m = np.cross(a, n)
    m /= np.linalg.norm(m)
    return {"a": a, "n": n, "m": m, "C": C, "ortho": ortho, "aspect": max(la, lb) / min(la, lb)}


def to_plane(pts, g, Km, dist):
    r = rays(pts, Km, dist)
    X = r * ((g["m"] @ g["C"]) / (r @ g["m"]))[:, None]
    D = X - g["C"]
    return np.stack([D @ g["a"], -(D @ g["n"])], 1)  # (긴 축, 위쪽)


def apply(v, g, Km, dist):
    # 긴 축 방향을 화면 +x 와 맞추고, 화면 픽셀 크기로 되돌릴 배율 하나(영상 단위)
    ref = to_plane(
        [[v["width"] / 2 - 100, v["height"] / 2], [v["width"] / 2 + 100, v["height"] / 2]],
        g,
        Km,
        dist,
    )
    sgn = 1 if ref[1, 0] > ref[0, 0] else -1
    scale = None
    for f in v["frames"]:
        if not f:
            continue
        t = K._trunk(f["kp"])
        if not t:
            continue
        Q = to_plane([k[:2] for k in f["kp"]], g, Km, dist)
        Q[:, 0] *= sgn
        qc = (Q[K.T13] + Q[K.ILIAC]) / 2
        if scale is None:
            scale = t[1] / max(np.linalg.norm(Q[K.T13] - Q[K.ILIAC]), 1e-9)
        f["norm"] = [
            [
                round(t[2] + scale * (q[0] - qc[0]), 2),
                round((f["kp"][K.T13][1] + f["kp"][K.ILIAC][1]) / 2 - scale * (q[1] - qc[1]), 2),
                k[2],
            ]
            for q, k in zip(Q, f["kp"])
        ]


if __name__ == "__main__":
    out, tracks = sys.argv[1], sys.argv[2:]
    vids, seen = [], set()
    for p in tracks:
        for v in json.load(open(p, encoding="utf-8"))["videos"]:
            if v["sha256"] in seen:
                continue
            date = v["video"][:6]
            view = re.search(r"(main|sub\d)", v["video"]).group(1)
            seen.add(v["sha256"])
            path = glob.glob(
                os.path.join(ROOT, "videos", "*", date, v["video"][:13] + "*", v["video"])
            )[0]
            mk = markers(path)
            ki = intr(date, view)
            src = "보정 파일"
            if ki is None or (len(mk) == 4 and geometry(mk, *ki)["ortho"] > 5):
                ki = selfcal(mk, v["width"], v["height"])
                src = "매트로 추정"
            if (
                ki is None and len(mk) == 4
            ):  # 거의 정면이라 소실점이 멀면 같은 기종 실측값(main 약 717)으로
                ki = (
                    np.array([[720.0, 0, v["width"] / 2], [0, 720.0, v["height"] / 2], [0, 0, 1]]),
                    np.zeros(5),
                )
                src = "기본값"
            if ki is None:
                print(v["video"], f"마커 {sorted(mk)} — 못 씀")
                continue
            tc = [K._trunk(f["kp"]) for f in v["frames"] if f and K._trunk(f["kp"])]
            tcy = [
                (
                    (f["kp"][K.T13][0] + f["kp"][K.ILIAC][0]) / 2,
                    (f["kp"][K.T13][1] + f["kp"][K.ILIAC][1]) / 2,
                )
                for f in v["frames"]
                if f and K._trunk(f["kp"])
            ]
            motion = np.array(tcy[-1]) - np.array(tcy[0]) if len(tcy) > 10 else None
            g = geometry(mk, *ki, motion=motion)
            if g is None:
                print(v["video"], "마커 4개 못 찾음")
                continue
            if g["ortho"] > 5:
                print(v["video"], f"직각 오차 {g['ortho']:.1f}° — 내부 파라미터 불일치로 제외")
                continue
            base = copy.deepcopy(v)
            apply(v, g, *ki)
            vids.append((base, v))
            print(
                f"{v['video']}: {src} f={ki[0][0,0]:.0f}, 직각 오차 {g['ortho']:.1f}°, 가로세로비 {g['aspect']:.2f}"
            )
    json.dump(
        {"meta": {"model": {"name": "base"}}, "videos": [b for b, _ in vids]},
        open(out + ".base.json", "w", encoding="utf-8"),
    )
    json.dump(
        {"meta": {"model": {"name": "plane"}}, "videos": [n for _, n in vids]},
        open(out + ".plane.json", "w", encoding="utf-8"),
    )
