import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, "C:/Users/SSAFY/Desktop/jjh/ssafy/paw_eval")
files = sys.argv[1:]
sys.argv = [sys.argv[0], str(HERE / "key")]
import compare as C  # noqa: E402
import score as S  # noqa: E402

GT = HERE / "key" / "gt_calib.json"
tmp = Path(tempfile.mkdtemp())
runs = {"모델": HERE / "key" / "prelabel.json"}
for f in files:
    lab = C.read_xml(f)
    rows, filled = [], 0
    for name, im in C.by_name.items():
        a = C.anns[im["id"]]
        p = C.pre[a["id"]]
        pts = lab.get(name)
        kp = []
        for i in range(22):
            if pts and pts[i][2]:
                kp += [pts[i][0], pts[i][1], 1.0]
            else:
                kp += [p[3 * i], p[3 * i + 1], 0.0]
                filled += 1
        rows.append({"ann_id": a["id"], "keypoints": kp})
    w = Path(f).stem.replace("_calib", "")
    out = tmp / f"{w}.json"
    out.write_text(json.dumps({"predictions": rows}), encoding="utf-8")
    runs[w] = out
    print(f"{w}: 빈 점 {filled}개는 모델 점으로 채움", file=sys.stderr)

joints = list(S.FLEX_SIDE)
print("| | KPI-04 평균 | " + " | ".join(joints) + " | 각도 수 |")
print("| :--- | ---: |" + " ---: |" * (len(joints) + 1))
for w, p in runs.items():
    k = S.score(GT, p)["kpi"]["KPI-04"]
    pj = k["per_joint"]
    print(f"| {w} | {k['mae']:.2f} | " + " | ".join(f"{pj[j]['mae']:.1f}" if pj[j].get("mae") is not None else "-" for j in joints) + f" | {k['n']} |")
