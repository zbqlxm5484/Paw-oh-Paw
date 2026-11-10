import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
files = sorted((HERE / "submissions").glob("*_calib.xml"))
sys.argv = [sys.argv[0], str(HERE / "key")]
import compare as C

IMG = Path("C:/Users/SSAFY/Desktop/jjh/ssafy/calib_kit_1027/images")
OUT = HERE / "fig213"
FONT = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 22)
SMALL = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 18)
labs = [C.read_xml(f) for f in files]
LIMB = {"L_front": [2, 3, 4, 5, 6, 7], "R_front": [2, 8, 9, 10, 11, 12], "L_hind": [13, 14, 15, 16, 17], "R_hind": [13, 18, 19, 20, 21]}
GROUPS = [
    ("shoulder", "어깨 끝(acromion)과 견갑골 위(dorsal scapular spine)", {"L_front": [3, 4], "R_front": [8, 9]}),
    ("hip", "고관절(femoral greater trochanter)", {"L_hind": [14], "R_hind": [18]}),
    ("front_paw", "앞발끝(fifth metacarpal distal)", {"L_front": [7], "R_front": [12]}),
    ("hind_paw", "뒷발끝(fifth metatarsal distal)", {"L_hind": [17], "R_hind": [21]}),
]
THR = 0.10


def cands(slots_by_limb):
    out = []
    for name, im in C.by_name.items():
        a = C.anns[im["id"]]
        k = a["keypoints"]
        L = math.hypot(k[3 * C.T13] - k[3 * C.ILIAC], k[3 * C.T13 + 1] - k[3 * C.ILIAC + 1]) or 1
        for limb, slots in slots_by_limb.items():
            if any(int(k[3 * i + 2]) != 2 for i in slots):
                continue
            wrong = []
            for lab in labs:
                pts = lab.get(name)
                if not pts:
                    continue
                for i in slots:
                    if pts[i][2] and math.hypot(pts[i][0] - k[3 * i], pts[i][1] - k[3 * i + 1]) / L > THR:
                        wrong.append((i, pts[i][0], pts[i][1]))
            out.append((len(wrong), name, limb, slots, wrong, k, L))
    out.sort(key=lambda r: -r[0])
    seen, pick = set(), []
    for r in out:
        if r[1] not in seen and r[0] > 0:
            pick.append(r)
            seen.add(r[1])
        if len(pick) == 2:
            break
    return pick


def tile(r):
    _, name, limb, slots, wrong, k, L = r
    img = Image.open(IMG / name).convert("RGB")
    xs = [k[3 * i] for i in LIMB[limb] if k[3 * i + 2] > 0] + [w[1] for w in wrong]
    ys = [k[3 * i + 1] for i in LIMB[limb] if k[3 * i + 2] > 0] + [w[2] for w in wrong]
    m = 0.25 * L
    box = (max(0, min(xs) - m), max(0, min(ys) - m), min(img.width, max(xs) + m), min(img.height, max(ys) + m))
    s = 520 / max(box[2] - box[0], box[3] - box[1])
    img = img.crop(box).resize((int((box[2] - box[0]) * s), int((box[3] - box[1]) * s)))
    d = ImageDraw.Draw(img)
    P = lambda x, y: ((x - box[0]) * s, (y - box[1]) * s)
    chain = [i for i in LIMB[limb] if k[3 * i + 2] > 0]
    for a, b in zip(chain, chain[1:]):
        d.line([P(k[3 * a], k[3 * a + 1]), P(k[3 * b], k[3 * b + 1])], fill=(60, 220, 60), width=3)
    for i, x, y in wrong:
        gx, gy = P(k[3 * i], k[3 * i + 1])
        wx, wy = P(x, y)
        d.line([(gx, gy), (wx, wy)], fill=(255, 80, 80), width=2)
        d.line([(wx - 8, wy - 8), (wx + 8, wy + 8)], fill=(255, 40, 40), width=4)
        d.line([(wx - 8, wy + 8), (wx + 8, wy - 8)], fill=(255, 40, 40), width=4)
    for i in chain:
        x, y = P(k[3 * i], k[3 * i + 1])
        r_ = 11 if i in slots else 5
        d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=(40, 230, 40), outline=(0, 0, 0), width=2)
    return img


for key, title, sl in GROUPS:
    pick = cands(sl)
    tiles = [tile(r) for r in pick]
    W = max(900, sum(t.width for t in tiles) + 10 * (len(tiles) + 1))
    H = max(t.height for t in tiles) + 90
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(canvas)
    d.text((10, 8), title, font=FONT, fill=(0, 0, 0))
    d.text((10, 42), "큰 초록 점: 기업 정답 위치   빨간 X: 팀원 6명 중 몸통 길이의 10% 넘게 벗어나게 찍은 위치", font=SMALL, fill=(60, 60, 60))
    x = 10
    for t in tiles:
        canvas.paste(t, (x, 80))
        x += t.width + 10
    canvas.save(OUT / f"{key}.png")
    print(key, [(r[1], r[2], r[0]) for r in pick])
