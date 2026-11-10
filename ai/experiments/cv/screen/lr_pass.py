import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from screen import BENCH, PENALTIES, SCR, score

out = SCR / "out"
res = out / "screen_results.jsonl"
rows = [json.loads(l) for l in res.read_text(encoding="utf-8").splitlines() if l.strip()]
have = {(r["key"], r["lr"]) for r in rows}
for r in [r for r in rows if r["lr"] == "none"]:
    gt, images, trk = BENCH[r["bench"]]
    if trk is None or not Path(trk).exists():
        continue
    stem = f"{r['bench']}_{r['weights']}_{r['tta']}"
    for p in PENALTIES:
        if (r["key"], f"hind{p}") in have:
            continue
        lp = out / f"{stem}_lr{p}.preds.json"
        subprocess.run([sys.executable, str(SCR.parent.parent / "eval_runs" / "lr_fix.py"), "--track", str(trk), "--gt", str(gt), "--pred", str(out / f"{stem}.preds.json"),
                        "--out", str(lp), "--penalty", str(p), "--legs", "hind"], check=True, capture_output=True)
        new = {**r, "lr": f"hind{p}", **score(gt, lp, out / f"{stem}_lr{p}.score.json")}
        with open(res, "a", encoding="utf-8") as f:
            f.write(json.dumps(new, ensure_ascii=False) + "\n")
        print(r["key"], new["lr"], new["kpi04"], "뒷발", new["hind"], flush=True)
