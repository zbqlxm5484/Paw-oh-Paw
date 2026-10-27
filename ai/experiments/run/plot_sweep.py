import csv
import json
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

R = Path(sys.argv[1] if len(sys.argv) > 1 else "/exp/results/sweep_1027")
speed = json.loads((R / "speed.json").read_text(encoding="utf-8"))
base = speed["results"][0]

rows = []
for r in speed["results"][1:]:
    name = r["name"]
    k = int(name.split("-")[0][1:])
    fp16 = name.endswith("fp16")
    ratio = r["ratio_to_first"]
    row = {"name": name, "k": k, "fp16": fp16, "kpi14_ratio": ratio["KPI-14"], "kpi15_ratio": ratio["KPI-15"],
           "kpi16_ratio": ratio["KPI-16"], "median_s": r["kpi"]["KPI-14"]["median_s"],
           "per_round_s": r["kpi"]["KPI-14"]["per_round_s"]}
    v = R / f"{name}.video.json"
    if v.exists():
        d = json.loads(v.read_text(encoding="utf-8"))
        j = d["judge"]
        row["kpi01_change_pct"] = None if j["KPI-01"]["reduction"] is None else -100 * j["KPI-01"]["reduction"]
        row["kpi02_change_pct"] = None if j["KPI-02"]["reduction"] is None else -100 * j["KPI-02"]["reduction"]
        row["kpi24_change_pct"] = None if j["KPI-24"]["ratio"] is None else 100 * (j["KPI-24"]["ratio"] - 1)
        row["kpi23_worst_pp"] = j["KPI-23"]["worst_diff_pp"]
        nk = d["results"][1]["kpi"]
        row["kpi01_n"], row["kpi02_n"], row["kpi24_swaps"] = nk["KPI-01"]["n"], nk["KPI-02"]["n"], nk["KPI-24"]["swaps"]
    rows.append(row)

keys = list(dict.fromkeys(k for r in rows for k in r))
with open(R / "sweep.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=keys)
    w.writeheader()
    w.writerows(rows)
print(f"base median {base['kpi']['KPI-14']['median_s']:.2f}s rounds {base['kpi']['KPI-14']['per_round_s']}")
for r in sorted(rows, key=lambda x: (x["fp16"], x["k"])):
    print(f"{r['name']:>10s} time x{r['kpi14_ratio']:.3f} rounds {[round(x, 2) for x in r['per_round_s']]}"
          f" KPI-01 {r.get('kpi01_change_pct')} KPI-02 {r.get('kpi02_change_pct')}"
          f" KPI-24 {r.get('kpi24_change_pct')} KPI-23 {r.get('kpi23_worst_pp')}")

matplotlib.use("Agg")

panels = [("kpi01_change_pct", "KPI-01 leg length CV, change vs fs-v4 (%)"),
          ("kpi02_change_pct", "KPI-02 left/right angle diff, change vs fs-v4 (%)"),
          ("kpi24_change_pct", "KPI-24 L/R swaps, change vs fs-v4 (%)"),
          ("kpi23_worst_pp", "KPI-23 detect rate, worst video change (%p)")]
fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
styles = {False: dict(color="#2a6fdb", marker="o", label="fp32"), True: dict(color="#d9480f", marker="s", label="fp16")}
for ax, (key, title) in zip(axes.flat, panels):
    for fp16 in (False, True):
        pts = sorted((r for r in rows if r["fp16"] == fp16 and r.get(key) is not None), key=lambda x: x["k"])
        if not pts:
            continue
        xs, ys = [p["kpi14_ratio"] for p in pts], [p[key] for p in pts]
        ax.plot(xs, ys, linewidth=2, markersize=8, **styles[fp16])
        for p, x, y in zip(pts, xs, ys):
            ax.annotate(f"K={p['k']}", (x, y), textcoords="offset points", xytext=(4, 6), fontsize=8,
                        color=styles[fp16]["color"])
    ax.axvline(0.5, color="#555", linestyle="--", linewidth=1)
    ax.axhline(0, color="#bbb", linewidth=0.8)
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("KPI-14 processing time ratio vs fs-v4 (target <= 0.5)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
fig.suptitle("Detection interval K x fp16 sweep (" + speed["created"] + ")")
fig.savefig(R / "sweep.png", dpi=150)
print(f"-> {R / 'sweep.png'}, {R / 'sweep.csv'}")
