"""사진을 조금 돌려 추론하고 점을 되돌리는 '회전 추론할 때 증강' 시험(10-22). 기업 도구는 안 건드린다.

    python rotate_tta.py prep --gt <정답> --images <사진 폴더 위> --deg 8 --out-dir results/rot/gt
        → 상자 가운데를 중심으로 deg 만큼 돌린 사진과 정답 사본(상자는 그대로)
    (predict.py 를 사본으로 돌린다)
    python rotate_tta.py unrotate --pred rot.preds.json --gt <원래 정답> --deg 8 --out back.preds.json
        → 예측 점을 원래 사진 좌표로 되돌린다. 그다음 multiscale_tta.py merge 로 평균

predict.py 는 정답의 상자만 쓰고 관절점 정답은 보지 않는다. 채점은 원래 정답으로 한다.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")


def centers(gt):
    return {
        a["id"]: (a["bbox"][0] + a["bbox"][2] / 2, a["bbox"][1] + a["bbox"][3] / 2)
        for a in gt["annotations"]
    }


def prep(a):
    gt = json.loads(Path(a.gt).read_text(encoding="utf-8"))
    out = Path(a.out_dir)
    images = {im["id"]: im for im in gt["images"]}
    by_img = {}
    for an in gt["annotations"]:
        by_img.setdefault(an["image_id"], []).append(an)
    for iid, anns in by_img.items():
        im = images[iid]
        src = Path(a.images) / im["file_name"]
        img = cv2.imdecode(np.fromfile(str(src), np.uint8), cv2.IMREAD_COLOR)
        x, y, w, h = anns[0]["bbox"]  # 사진 하나에 개 하나(정답 형식)
        m = cv2.getRotationMatrix2D((x + w / 2, y + h / 2), a.deg, 1.0)
        rot = cv2.warpAffine(img, m, (img.shape[1], img.shape[0]), borderMode=cv2.BORDER_REPLICATE)
        dst = out / im["file_name"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        cv2.imencode(dst.suffix, rot)[1].tofile(str(dst))
    (out / "gt.json").write_text(json.dumps(gt, ensure_ascii=False), encoding="utf-8")
    print(f"-> {out} 사진 {len(by_img)}장 {a.deg}°")


def unrotate(a):
    gt = json.loads(Path(a.gt).read_text(encoding="utf-8"))
    c = centers(gt)
    doc = json.loads(Path(a.pred).read_text(encoding="utf-8"))
    th = math.radians(a.deg)  # cv2 각도는 반시계(+). 되돌리기는 같은 각도로 반대 회전
    cs, sn = math.cos(th), math.sin(th)
    for r in doc["predictions"]:
        cx, cy = c[r["ann_id"]]
        kp = r["keypoints"]
        for i in range(0, len(kp), 3):
            dx, dy = kp[i] - cx, kp[i + 1] - cy
            # 회전 사진 좌표 = R(deg)·원래, 화면 좌표계(y 아래)에서 cv2 의 +각은 반시계 → 역변환
            kp[i], kp[i + 1] = cx + cs * dx - sn * dy, cy + sn * dx + cs * dy
    Path(a.out).write_text(json.dumps(doc), encoding="utf-8")
    print(f"-> {a.out}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep")
    p.add_argument("--gt", required=True)
    p.add_argument("--images", required=True)
    p.add_argument("--deg", type=float, required=True)
    p.add_argument("--out-dir", required=True)
    u = sub.add_parser("unrotate")
    u.add_argument("--pred", required=True)
    u.add_argument("--gt", required=True)
    u.add_argument("--deg", type=float, required=True)
    u.add_argument("--out", required=True)
    a = ap.parse_args()
    prep(a) if a.cmd == "prep" else unrotate(a)


if __name__ == "__main__":
    main()
