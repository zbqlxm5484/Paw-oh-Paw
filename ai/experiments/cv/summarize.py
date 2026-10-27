import collections
import json
from pathlib import Path

CV = Path("/exp/cv") if Path("/exp/cv").exists() else Path(__file__).parent
rows = [json.loads(l) for l in (CV / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
base = {r["fold_test"]: r["eval"] for r in rows if r["id"].startswith("B0_")}
by = collections.defaultdict(dict)
desc = {}
ext = [r for r in rows if set(r.get("evals", {})) & {"ww", "pilot", "fall"}]
rows = [r for r in rows if isinstance(r["fold_test"], int)]
for r in rows:
    jid = r["id"].rsplit("_f", 1)[0]
    by[jid][r["fold_test"]] = r["eval"]
    desc[jid] = (r["group"], r["desc"])

keys = [("kpi04", "각도"), ("kpi04_t", "각도(고친점)"), ("hind", "뒷발끝"), ("front", "앞발끝"), ("pck05", "PCK@0.05")]
lines = ["| 실험 | 묶음 | 내용 | flip | " + " | ".join(f"{n} f1, f0" for _, n in keys) + " | 각도 변화(평균) |",
         "| :--- | :--- | :--- | :--- | " + " | ".join("---:" for _ in keys) + " | ---: |"]
for jid, ev in by.items():
    for flip in ("flip0", "flip1"):
        cells = []
        for k, _ in keys:
            vals = [ev[t][flip][k] if t in ev else None for t in (1, 0)]
            fmt = (lambda v: f"{v:.2f}") if k.startswith("kpi04") else (lambda v: f"{v * 100:.1f}" if k in ("hind", "front") else f"{v:.3f}")
            cells.append(", ".join("-" if v is None else fmt(v) for v in vals))
        d = [ev[t][flip]["kpi04"] - base[t][flip]["kpi04"] for t in ev if t in base]
        delta = f"{sum(d) / len(d):+.2f}" if d else "-"
        g, ds = desc[jid]
        lines.append(f"| {jid} | {g} | {ds} | {flip[-1]} | " + " | ".join(cells) + f" | {delta} |")
for test, title in (("fall", "제니 205장 전체 (와우와우로 학습한 모델)"), ("pilot", "팀 시험 라벨 93장 (학습에 안 쓴 14마리)"), ("ww", "와우와우 good+ambiguous (학습에 안 쓴 개)")):
    sel = [r for r in ext if test in r["evals"]]
    if not sel:
        continue
    lines += ["", title, "",
              "| 실험 | 내용 | flip | 각도 | 각도(고친점) | 뒷발끝 | 앞발끝 | PCK@0.05 | PCK@0.10 | 오차 중앙값 | 편향 뺀 오차 |",
              "| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in sel:
        for flip in ("flip0", "flip1"):
            e = r["evals"][test][flip]
            n = lambda v, f: "-" if v is None else format(v, f)
            lines.append(f"| {r['id']} | {r['desc']} | {flip[-1]} | {n(e['kpi04'], '.2f')} | {n(e['kpi04_t'], '.2f')} | {n(e['hind'] * 100, '.1f')} | {n(e['front'] * 100, '.1f')} | "
                         f"{n(e['pck05'], '.3f')} | {n(e['pck10'], '.3f')} | {n(e.get('raw'), '.4f')} | {n(e.get('residual'), '.4f')} |")
text = "\n".join(lines)
(CV / "summary.md").write_text(text + "\n", encoding="utf-8")
print(text)
