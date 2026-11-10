import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from tta_eval import run as tta

HOME = "@HOME@"
PAW = Path(f"{HOME}/work/ssafy/paw_eval")
CV = Path(f"{HOME}/work/exp/cv")
SCR = CV / "screen"
DATA = CV / "data"
S5 = [0.85, 0.9, 1.0, 1.1, 1.15]
TTAS = {"t0": (0, [1.0], []), "t1": (1, [1.0], []), "t2": (1, [0.9, 1.0, 1.1], []), "t3": (1, S5, []),
        "t4": (1, S5, [8.0, -8.0]), "t5": (1, S5, [4.0, -4.0, 8.0, -8.0]), "t6": (1, S5, [12.0, -12.0])}
WEIGHTS = {"fs4": PAW / "models/fs-v4/pose.pth", "team_head": CV / "runs/SCR_team_head_s42/final.pth",
           "team_full": CV / "runs/SCR_team_full_s42/final.pth", "wise03": SCR / "wise_0.3.pth", "wise05": SCR / "wise_0.5.pth"}
BENCH = {"fall": (DATA / "gt_fall.json", f"{HOME}/work/ssafy/dataset/keypoints_260820", SCR / "trk_jenny.json"),
         "pilot": (DATA / "gt_pilot.json", f"{HOME}/work/ssafy/pilot100_1027", None),
         "ww": (DATA / "gt_ww.json", f"{HOME}/work/ssafy/dataset/keypoints_wowwow", SCR / "trk_ww.json")}
PENALTIES = [0.02, 0.005]


def score(gt, pred, out):
    subprocess.run([sys.executable, "score.py", "--gt", str(gt), "--pred", str(pred), "--out", str(out)], cwd=PAW, check=True, capture_output=True)
    k = json.loads(Path(out).read_text(encoding="utf-8"))
    k = k.get("kpi", k)
    return {"kpi04": k["KPI-04"]["mae"], "kpi04_t": k["KPI-04"]["touched_only"]["mae"], "front": k["KPI-21"]["front"]["value"],
            "hind": k["KPI-21"]["hind"]["value"], "pck05": k["KPI-19"]["value"], "pck10": k["KPI-18"]["value"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    out_dir = SCR / ("smoke" if a.smoke else "out")
    out_dir.mkdir(parents=True, exist_ok=True)
    res_path = out_dir / "screen_results.jsonl"
    done = {json.loads(l)["key"] for l in res_path.read_text(encoding="utf-8").splitlines() if l.strip()} if res_path.exists() else set()
    weights = {"fs4": WEIGHTS["fs4"]} if a.smoke else WEIGHTS
    ttas = {k: TTAS[k] for k in ("t0", "t4")} if a.smoke else TTAS
    benches = {k: BENCH[k] for k in ("fall", "pilot")} if a.smoke else BENCH
    for bname, (gt, images, trk) in benches.items():
        if a.smoke:
            d = json.loads(Path(gt).read_text(encoding="utf-8"))
            d["annotations"] = d["annotations"][:3]
            ids = {x["image_id"] for x in d["annotations"]}
            d["images"] = [im for im in d["images"] if im["id"] in ids]
            gt = out_dir / f"gt_{bname}.json"
            gt.write_text(json.dumps(d), encoding="utf-8")
        for wname, w in weights.items():
            if not Path(w).exists():
                print("가중치 없음, 건너뜀", wname, flush=True)
                continue
            for tname, (flip, scales, rots) in ttas.items():
                key = f"{bname}|{wname}|{tname}"
                if key in done:
                    continue
                t0 = time.time()
                cfg = CV / "pose_flip.py" if flip else PAW / "models/fs-v4/pose.py"
                pred = out_dir / f"{bname}_{wname}_{tname}.preds.json"
                n = tta(cfg, w, gt, images, scales, rots, pred, limit=0)
                row = {"key": key, "bench": bname, "weights": wname, "tta": tname, "n": n, "lr": "none",
                       **score(gt, pred, out_dir / f"{bname}_{wname}_{tname}.score.json")}
                rows = [row]
                if trk is not None and Path(trk).exists():
                    for p in PENALTIES:
                        lp = out_dir / f"{bname}_{wname}_{tname}_lr{p}.preds.json"
                        subprocess.run([sys.executable, str(SCR.parent.parent / "eval_runs" / "lr_fix.py"), "--track", str(trk), "--gt", str(gt), "--pred", str(pred),
                                        "--out", str(lp), "--penalty", str(p), "--legs", "hind"], check=True, capture_output=True)
                        rows.append({**row, "lr": f"hind{p}", **score(gt, lp, out_dir / f"{bname}_{wname}_{tname}_lr{p}.score.json")})
                with open(res_path, "a", encoding="utf-8") as f:
                    for r in rows:
                        r["minutes"] = round((time.time() - t0) / 60, 2)
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
                print(key, " / ".join(f"{r['lr']} {r['kpi04']} 뒷발 {r['hind']}" for r in rows), f"{rows[0]['minutes']}분", flush=True)


if __name__ == "__main__":
    main()
