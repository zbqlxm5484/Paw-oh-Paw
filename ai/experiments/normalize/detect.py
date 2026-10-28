"""영상에서 측정 매트(검은 사각형) 네 꼭짓점 찾기 — 여러 프레임 중앙값 배경에서 어두운 큰 덩어리."""

import json
import os
import sys

import cv2
import numpy as np


def background(path, n=15):
    cap = cv2.VideoCapture(path)
    N = int(cap.get(7))
    fr = []
    for t in np.linspace(0, N - 1, n).astype(int):
        cap.set(1, int(t))
        ok, im = cap.read()
        if ok:
            fr.append(im)
    return np.median(np.stack(fr), axis=0).astype(np.uint8)


def mat_quad(bg):
    hsv = cv2.cvtColor(bg, cv2.COLOR_BGR2HSV)
    dark = ((hsv[..., 2] < 70) & (hsv[..., 1] < 90)).astype(np.uint8) * 255
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    cs, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = max(cs, key=cv2.contourArea)
    hull = cv2.convexHull(c)
    for eps in np.linspace(0.01, 0.08, 30):
        q = cv2.approxPolyDP(hull, eps * cv2.arcLength(hull, True), True)
        if len(q) == 4:
            return q.reshape(4, 2).astype(float), cv2.contourArea(c)
    return None, cv2.contourArea(c)


if __name__ == "__main__":
    out = {}
    for p in sys.argv[2:]:
        bg = background(p)
        q, area = mat_quad(bg)
        name = os.path.basename(p)
        out[name] = None if q is None else q.tolist()
        vis = bg.copy()
        if q is not None:
            cv2.polylines(vis, [q.astype(np.int32)], True, (0, 0, 255), 4)
        cv2.imencode(".jpg", cv2.resize(vis, (480, 270)))[1].tofile(
            os.path.join(sys.argv[1], "q_%02d.jpg" % len(out))
        )
        print(name, "없음" if q is None else np.round(q).astype(int).tolist(), int(area))
    json.dump(
        out,
        open(os.path.join(sys.argv[1], "quads.json"), "w", encoding="utf-8"),
        ensure_ascii=False,
    )
