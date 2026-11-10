import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

KEY = Path(sys.argv[1])
FILES = sys.argv[2:]
T13, ILIAC = 2, 13
SKIP = {T13, ILIAC}
MOVED = 0.01
TOES = {"앞발끝": (7, 12), "뒷발끝": (17, 21)}

gt = json.loads((KEY / "gt_calib.json").read_text(encoding="utf-8"))
names = gt["categories"][0]["keypoints"]
pre = {p["ann_id"]: p["keypoints"] for p in json.loads((KEY / "prelabel.json").read_text(encoding="utf-8"))["predictions"]}
by_name = {Path(im["file_name"]).name: im for im in gt["images"]}
anns = {a["image_id"]: a for a in gt["annotations"]}


def read_xml(p):
    out = {}
    for im in ET.parse(p).getroot().iter("image"):
        for sk in im.iter("skeleton"):
            pts = {}
            for e in sk.iter("points"):
                x, y = (float(v) for v in e.attrib["points"].split(","))
                v = 0 if e.attrib.get("outside") == "1" else (1 if e.attrib.get("occluded") == "1" else 2)
                pts[e.attrib["label"]] = (x, y, v)
            out[im.attrib["name"]] = [pts.get(n, (0, 0, 0)) for n in names]
    return out


def median(v):
    v = sorted(v)
    return None if not v else (v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2)


def analyse(lab):
    joint = {i: {"d": [], "dx": [], "dy": []} for i in range(22) if i not in SKIP}
    touch = {"둘 다 옮김": 0, "라벨러만 옮김": 0, "기업만 옮김": 0, "둘 다 그대로": 0}
    swaps = {k: [0, 0] for k in TOES}
    for name, pts in lab.items():
        im = by_name.get(name)
        if im is None:
            continue
        a = anns[im["id"]]
        k = a["keypoints"]
        p = pre[a["id"]]
        t = (a.get("attributes") or {}).get("touched") or [0] * 22
        L = math.hypot(k[3 * T13] - k[3 * ILIAC], k[3 * T13 + 1] - k[3 * ILIAC + 1]) or 1
        s = 1 if k[3 * T13] > k[3 * ILIAC] else -1
        for i in joint:
            if int(k[3 * i + 2]) == 0 or pts[i][2] == 0:
                continue
            dx, dy = (pts[i][0] - k[3 * i]) / L, (pts[i][1] - k[3 * i + 1]) / L
            joint[i]["d"].append(math.hypot(dx, dy))
            joint[i]["dx"].append(dx * s)
            joint[i]["dy"].append(dy)
            moved = math.hypot(pts[i][0] - p[3 * i], pts[i][1] - p[3 * i + 1]) / L > MOVED
            key = ("둘 다 옮김" if t[i] else "라벨러만 옮김") if moved else ("기업만 옮김" if t[i] else "둘 다 그대로")
            touch[key] += 1
        for nm, (l, r) in TOES.items():
            if min(int(k[3 * l + 2]), int(k[3 * r + 2]), pts[l][2], pts[r][2]) == 0:
                continue
            keep = math.hypot(pts[l][0] - k[3 * l], pts[l][1] - k[3 * l + 1]) + math.hypot(pts[r][0] - k[3 * r], pts[r][1] - k[3 * r + 1])
            cross = math.hypot(pts[l][0] - k[3 * r], pts[l][1] - k[3 * r + 1]) + math.hypot(pts[r][0] - k[3 * l], pts[r][1] - k[3 * l + 1])
            swaps[nm][0] += 1
            swaps[nm][1] += cross < keep
    rows = []
    alld = []
    for i, v in joint.items():
        if not v["d"]:
            continue
        alld += v["d"]
        rows.append((names[i], len(v["d"]), median(v["d"]), sum(v["dx"]) / len(v["dx"]), sum(v["dy"]) / len(v["dy"]),
                     sum(d <= 0.05 for d in v["d"]) / len(v["d"])))
    return rows, alld, touch, swaps


for f in FILES:
    lab = read_xml(f)
    rows, alld, touch, swaps = analyse(lab)
    print(f"\n## {Path(f).stem}  (사진 {len(lab)}장)")
    print(f"- 기업 정답과의 거리 중앙값 {median(alld):.3f} 몸통 길이, PCK@0.05 {sum(d <= 0.05 for d in alld) / len(alld):.2f}, PCK@0.10 {sum(d <= 0.10 for d in alld) / len(alld):.2f}")
    tot = sum(touch.values()) or 1
    print("- 손대는 범위: " + ", ".join(f"{k} {v}({v / tot:.0%})" for k, v in touch.items()))
    print("- 좌우 반대로 찍음: " + ", ".join(f"{k} {s}/{n}" for k, (n, s) in swaps.items()))
    print("\n| 관절 | 점 | 거리 중앙값 | 앞뒤 편향(+머리쪽) | 위아래 편향(+아래) | PCK@0.05 |\n| :--- | ---: | ---: | ---: | ---: | ---: |")
    for nm, n, d, bx, by, pck in sorted(rows, key=lambda r: -r[2]):
        print(f"| {nm} | {n} | {d:.3f} | {bx:+.3f} | {by:+.3f} | {pck:.2f} |")
