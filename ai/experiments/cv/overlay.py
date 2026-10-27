import json
import sys

import cv2

GT = "/exp/cv/data/gt_pilot.json"
PRED = "/exp/cv/runs/WW_B0/pilot_flip0.preds.json"
who = sys.argv[1]
n = int(sys.argv[2])
g = json.load(open(GT, encoding="utf-8"))
p = {x["ann_id"]: x["keypoints"] for x in json.load(open(PRED, encoding="utf-8"))["predictions"]}
ims = [im for im in g["images"] if im["labeler"] == who][:n]
anns = {a["image_id"]: a for a in g["annotations"]}
tiles = []
for im in ims:
    img = cv2.imread("/ssafy/pilot100_1027/" + im["file_name"])
    a = anns[im["id"]]
    k, q = a["keypoints"], p[a["id"]]
    for i in range(22):
        if k[3 * i + 2] > 0:
            cv2.circle(img, (int(k[3 * i]), int(k[3 * i + 1])), 7, (0, 255, 0), -1)
            cv2.line(img, (int(k[3 * i]), int(k[3 * i + 1])), (int(q[3 * i]), int(q[3 * i + 1])), (255, 255, 255), 2)
        cv2.circle(img, (int(q[3 * i]), int(q[3 * i + 1])), 6, (0, 0, 255), 2)
    x, y, w, h = a["bbox"]
    m = 0.4 * max(w, h)
    x0, y0 = max(0, int(x - m)), max(0, int(y - m))
    crop = img[y0:int(y + h + m), x0:int(x + w + m)]
    tiles.append(cv2.resize(crop, (640, int(640 * crop.shape[0] / crop.shape[1]))))
hmax = max(t.shape[0] for t in tiles)
tiles = [cv2.copyMakeBorder(t, 0, hmax - t.shape[0], 0, 0, cv2.BORDER_CONSTANT) for t in tiles]
cv2.imwrite(f"/exp/cv/overlay_{who}.jpg", cv2.hconcat(tiles))
print("ok", len(tiles))
