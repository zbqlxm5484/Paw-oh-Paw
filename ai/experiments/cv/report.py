import collections
import html
import json
import sys
from pathlib import Path

CV = Path(__file__).parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else CV / "report.html"
rows = [json.loads(l) for l in (CV / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

GROUP = {"기준": 0, "원인": 1, "기업라벨": 2, "가중치섞기": 3, "시드": 2, "민감도": 2}
GNAME = {0: "기준(fs-v4)", 1: "오토라벨로 학습(원인 찾기)", 2: "기업 정답으로 학습", 3: "fs-v4와 섞기"}
SHAPE = {0: "diamond", 1: "circle", 2: "square", 3: "triangle"}

cv = collections.defaultdict(dict)
meta = {}
for r in rows:
    if not isinstance(r["fold_test"], int):
        continue
    jid = r["id"].rsplit("_f", 1)[0]
    cv[jid][r["fold_test"]] = r["eval"]
    meta[jid] = (r["group"], r["desc"])


def avg(jid, key, flip="flip0"):
    ev = cv.get(jid, {})
    if len(ev) < 2:
        return None
    v = [ev[t][flip][key] for t in (0, 1)]
    return None if None in v else sum(v) / 2


done = [j for j in cv if len(cv[j]) == 2]
pts = []
for j in done:
    g = GROUP.get(meta[j][0], 2)
    pts.append({"id": j, "g": g, "desc": meta[j][1], "x": avg(j, "kpi04"), "y": avg(j, "hind") * 100,
                "pck": avg(j, "pck05"), "front": avg(j, "front") * 100, "x1": avg(j, "kpi04", "flip1"), "y1": avg(j, "hind", "flip1") * 100})

PAIRS = [
    ("학습 상자를 채점과 같게", [("C0", "C1", "오토라벨"), ("G1", "G3", "기업 정답, 머리만")]),
    ("오토라벨 대신 기업 정답", [("C0", "G0", "전체 학습, 옛 상자"), ("Call", "G6", "전체 학습, 상자 맞춤")]),
    ("fs-v4와 반반 섞기", [("G0", "W_G0_0.5", "옛 상자"), ("G6", "W_G6_0.5", "상자 맞춤")]),
    ("전체 대신 머리만 학습", [("C0", "C0h", "오토라벨"), ("G0", "G1", "기업 정답, 옛 상자")]),
    ("가려진 점 포함", [("C0", "C2", "오토라벨"), ("G1", "G2", "기업 정답"), ("G3", "G7", "기업 정답, 상자 맞춤")]),
    ("학습률 낮춤(1e-5)", [("C0", "C4", "오토라벨")]),
    ("회전 줄임", [("C0", "C3a", "30에서 10"), ("C0", "C3b", "끔")]),
    ("마지막 단계까지 학습", [("G1", "G5", "기업 정답")]),
    ("반전 증강 끔", [("C0", "C4b", "오토라벨")]),
    ("사람이 안 옮긴 점 빼기", [("G1", "G4", "기업 정답")]),
]
effects = []
for factor, plist in PAIRS:
    for a, b, note in plist:
        if a in done and b in done:
            effects.append({"factor": factor, "note": note, "a": a, "b": b,
                            "da": avg(b, "kpi04") - avg(a, "kpi04"), "dh": (avg(b, "hind") - avg(a, "hind")) * 100,
                            "dp": avg(b, "pck05") - avg(a, "pck05")})

ext = [r for r in rows if set(r.get("evals", {})) & {"pilot", "ww", "fall"}]


def esc(s):
    return html.escape(str(s), quote=True)


def shape(kind, x, y, r, cls, tip):
    t = f' data-tip="{esc(tip)}" tabindex="0"'
    if kind == "circle":
        return f'<circle class="{cls}" cx="{x:.1f}" cy="{y:.1f}" r="{r}"{t}/>'
    if kind == "square":
        return f'<rect class="{cls}" x="{x - r:.1f}" y="{y - r:.1f}" width="{2 * r}" height="{2 * r}" rx="1.5"{t}/>'
    if kind == "triangle":
        return f'<path class="{cls}" d="M{x:.1f},{y - r - 1:.1f} L{x + r + 1:.1f},{y + r:.1f} L{x - r - 1:.1f},{y + r:.1f} Z"{t}/>'
    return f'<path class="{cls}" d="M{x:.1f},{y - r - 1:.1f} L{x + r + 1:.1f},{y:.1f} L{x:.1f},{y + r + 1:.1f} L{x - r - 1:.1f},{y:.1f} Z"{t}/>'


def scatter():
    W, H, L, R, T, B = 760, 440, 56, 20, 16, 48
    xs = [p["x"] for p in pts] + [7.0]
    x0, x1 = min(xs) - 0.2, max(xs) + 0.2
    y0, y1 = 0, max(p["y"] for p in pts) + 1.5
    sx = lambda v: L + (v - x0) / (x1 - x0) * (W - L - R)
    sy = lambda v: H - B - (v - y0) / (y1 - y0) * (H - T - B)
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="실험별 각도 오차와 뒷발끝 뒤바뀜 산점도">']
    s.append(f'<rect class="goal" x="{L}" y="{sy(3):.1f}" width="{sx(7) - L:.1f}" height="{H - B - sy(3):.1f}"/>')
    s.append(f'<text class="goal-t" x="{L + 6}" y="{H - B - 8}">목표 안쪽 (각도 7° 이하, 뒷발끝 3% 이하)</text>')
    tx = 6.0
    while tx <= x1:
        if tx >= x0:
            s.append(f'<line class="grid" x1="{sx(tx):.1f}" x2="{sx(tx):.1f}" y1="{T}" y2="{H - B}"/><text class="tick" x="{sx(tx):.1f}" y="{H - B + 18}" text-anchor="middle">{tx:.1f}°</text>')
        tx += 0.5
    for ty in range(0, int(y1) + 1, 3):
        s.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{sy(ty):.1f}" y2="{sy(ty):.1f}"/><text class="tick" x="{L - 8}" y="{sy(ty) + 4:.1f}" text-anchor="end">{ty}%</text>')
    s.append(f'<line class="axis" x1="{L}" x2="{W - R}" y1="{H - B}" y2="{H - B}"/>')
    s.append(f'<line class="target" x1="{sx(7):.1f}" x2="{sx(7):.1f}" y1="{T}" y2="{H - B}"/><line class="target" x1="{L}" x2="{W - R}" y1="{sy(3):.1f}" y2="{sy(3):.1f}"/>')
    s.append(f'<text class="axis-t" x="{(L + W - R) / 2}" y="{H - 8}" text-anchor="middle">관절 각도 오차 (°, 낮을수록 좋음)</text>')
    s.append(f'<text class="axis-t" transform="translate(14 {(T + H - B) / 2}) rotate(-90)" text-anchor="middle">뒷발끝 좌우 뒤바뀜 (%)</text>')
    label = {"B0", "C0", "G0", "G3", "W_G6_0.5", "G4", "Call"}
    for p in sorted(pts, key=lambda p: p["g"]):
        tip = f'{p["id"]}: {p["desc"]} | 각도 {p["x"]:.2f}°, 뒷발끝 {p["y"]:.1f}%, 앞발끝 {p["front"]:.1f}%, PCK@0.05 {p["pck"]:.3f}'
        s.append(shape(SHAPE[p["g"]], sx(p["x"]), sy(p["y"]), 5, f"m g{p['g']}", tip))
        if p["id"] in label:
            s.append(f'<text class="lab" x="{sx(p["x"]) + 8:.1f}" y="{sy(p["y"]) - 6:.1f}">{esc(p["id"])}</text>')
    s.append("</svg>")
    return "".join(s)


def effect_chart():
    W, rh, L, R = 760, 26, 250, 70
    H = 30 + rh * len(effects) + 30
    lo = min(min(e["da"] for e in effects), -1.0) - 0.45
    hi = max(max(e["da"] for e in effects), 1.0) + 0.1
    sx = lambda v: L + (v - lo) / (hi - lo) * (W - L - R)
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="요인별 각도 오차 변화 막대">']
    t = -2.0
    while t <= hi:
        if t >= lo:
            s.append(f'<line class="grid" x1="{sx(t):.1f}" x2="{sx(t):.1f}" y1="20" y2="{H - 30}"/><text class="tick" x="{sx(t):.1f}" y="{H - 12}" text-anchor="middle">{t:+.1f}°</text>')
        t += 0.5
    y = 26
    last = None
    for e in effects:
        if e["factor"] != last:
            s.append(f'<text class="fac" x="8" y="{y + 15}">{esc(e["factor"])}</text>')
            last = e["factor"]
        s.append(f'<text class="note" x="{L - 8}" y="{y + 15}" text-anchor="end">{esc(e["note"])}</text>')
        x_a, x_b = sx(0), sx(e["da"])
        left, w = min(x_a, x_b), abs(x_b - x_a)
        tip = f'{e["factor"]} ({e["note"]}): {e["a"]} → {e["b"]} | 각도 {e["da"]:+.2f}°, 뒷발끝 {e["dh"]:+.1f}%p, PCK@0.05 {e["dp"]:+.3f}'
        cls = "bar good" if e["da"] < 0 else "bar bad"
        s.append(f'<rect class="{cls}" x="{left:.1f}" y="{y + 4}" width="{max(w, 1.5):.1f}" height="{rh - 8}" rx="3" data-tip="{esc(tip)}" tabindex="0"/>')
        tx = x_b + (6 if e["da"] >= 0 else -6)
        s.append(f'<text class="val" x="{tx:.1f}" y="{y + 16}" text-anchor="{"start" if e["da"] >= 0 else "end"}">{e["da"]:+.2f}</text>')
        y += rh
    s.append(f'<line class="zero" x1="{sx(0):.1f}" x2="{sx(0):.1f}" y1="20" y2="{H - 30}"/>')
    s.append("</svg>")
    return "".join(s)


def f(v, fmt):
    return "-" if v is None else format(v, fmt)


def table_cv():
    h = ['<table><thead><tr><th>실험</th><th>묶음</th><th>내용</th><th>각도</th><th>각도 (flip)</th><th>뒷발끝</th><th>앞발끝</th><th>PCK@0.05</th><th>기준 대비 각도</th></tr></thead><tbody>']
    base = avg("B0", "kpi04")
    for p in sorted(pts, key=lambda p: (p["g"], p["x"])):
        h.append(f'<tr><td><code>{esc(p["id"])}</code></td><td><span class="key k{p["g"]}"></span>{esc(GNAME[p["g"]])}</td><td>{esc(p["desc"])}</td>'
                 f'<td class="n">{p["x"]:.2f}°</td><td class="n">{f(p["x1"], ".2f")}°</td><td class="n">{p["y"]:.1f}%</td><td class="n">{p["front"]:.1f}%</td>'
                 f'<td class="n">{p["pck"]:.3f}</td><td class="n">{p["x"] - base:+.2f}</td></tr>')
    h.append("</tbody></table>")
    return "".join(h)


def table_ext():
    if not ext:
        return "<p class='muted'>아직 결과가 없습니다. 밤 대기열(2묶음)에서 채워집니다.</p>"
    names = {"pilot": "팀 시험 라벨 93장", "ww": "와우와우 1,100장", "fall": "제니 205장 전체"}
    h = ['<table><thead><tr><th>모델</th><th>내용</th><th>채점 데이터</th><th>각도</th><th>뒷발끝</th><th>앞발끝</th><th>PCK@0.05</th><th>편향 뺀 오차</th></tr></thead><tbody>']
    for r in ext:
        for t, e in r["evals"].items():
            x = e["flip0"]
            h.append(f'<tr><td><code>{esc(r["id"])}</code></td><td>{esc(r["desc"])}</td><td>{names.get(t, t)}</td><td class="n">{f(x["kpi04"], ".2f")}°</td>'
                     f'<td class="n">{f(x["hind"] * 100 if x["hind"] is not None else None, ".1f")}%</td><td class="n">{f(x["front"] * 100 if x["front"] is not None else None, ".1f")}%</td>'
                     f'<td class="n">{f(x["pck05"], ".3f")}</td><td class="n">{f(x.get("residual"), ".4f")}</td></tr>')
    h.append("</tbody></table>")
    return "".join(h)


legend = "".join(f'<span class="lg"><svg width="14" height="14" viewBox="0 0 14 14">{shape(SHAPE[g], 7, 7, 4.5, f"m g{g}", "")}</svg>{GNAME[g]}</span>' for g in range(4))
legend = legend.replace(' data-tip="" tabindex="0"', "")
n_runs = sum(1 for r in rows if isinstance(r["fold_test"], int))

page = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>크림오프 학습 실험 정리</title>
<style>
:root{{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;
--s0:#898781;--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--good:#2a78d6;--bad:#e34948;--goal:#e8f1fc;--line:#e1e0d9}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;
--s0:#898781;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--good:#3987e5;--bad:#e66767;--goal:#16263a;--line:#2c2c2a}}}}
:root[data-theme="dark"]{{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;
--s0:#898781;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--good:#3987e5;--bad:#e66767;--goal:#16263a;--line:#2c2c2a}}
body{{margin:0;background:var(--page);color:var(--ink);font:15px/1.7 "Pretendard","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif}}
main{{max-width:860px;margin:0 auto;padding:28px 16px 64px}}
h1{{font-size:26px;margin:0 0 6px}} h2{{font-size:19px;margin:40px 0 8px}} .sub{{color:var(--ink2);font-size:13px}}
.card{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0}}
svg{{width:100%;height:auto;display:block}} .grid{{stroke:var(--grid);stroke-width:1}} .axis,.zero{{stroke:var(--axis);stroke-width:1.5}}
.target{{stroke:var(--muted);stroke-width:1;stroke-dasharray:4 4}} .goal{{fill:var(--goal)}} .goal-t{{fill:var(--ink2);font-size:12px}}
.tick{{fill:var(--muted);font-size:11px}} .axis-t{{fill:var(--ink2);font-size:12px}} .lab{{fill:var(--ink);font-size:11px;font-weight:600}}
.m{{stroke:var(--surface);stroke-width:2;cursor:pointer}} .m.g0{{fill:var(--s0)}} .m.g1{{fill:var(--s1)}} .m.g2{{fill:var(--s2)}} .m.g3{{fill:var(--s3)}}
.m:hover,.m:focus,.bar:hover,.bar:focus{{stroke:var(--ink);outline:none}}
.bar{{cursor:pointer;stroke:var(--surface);stroke-width:1}} .bar.good{{fill:var(--good)}} .bar.bad{{fill:var(--bad)}}
.fac{{fill:var(--ink);font-size:12px;font-weight:600}} .note{{fill:var(--ink2);font-size:11px}} .val{{fill:var(--ink);font-size:11px}}
.lgs{{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;color:var(--ink2);margin:6px 0 10px}} .lg{{display:inline-flex;align-items:center;gap:6px}} .lg svg{{width:14px;height:14px;flex:none}}
.tblwrap{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}}
th{{color:var(--ink2);font-weight:600}} td.n{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}} code{{font-size:12px}}
.key{{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px}} .k0{{background:var(--s0)}} .k1{{background:var(--s1)}} .k2{{background:var(--s2)}} .k3{{background:var(--s3)}}
.muted{{color:var(--muted)}} ul{{padding-left:20px}} li{{margin:4px 0}}
#tip{{position:fixed;pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--axis);border-radius:8px;padding:8px 10px;font-size:12px;max-width:340px;box-shadow:0 4px 16px rgba(0,0,0,.12);display:none;z-index:9}}
</style></head><body><main>
<h1>크림오프 학습 실험 정리</h1>
<p class="sub">제니 촬영 18개를 번갈아 반씩 나눠 한쪽으로 학습하고 다른 쪽으로 채점한 교차 실험 {n_runs}건(두 방향 평균, flip 없이 잰 값). 같은 개 안의 상한선이며 시드는 42 하나. 결과 파일 <code>experiments/cv/results.jsonl</code>, 다시 만들기 <code>python experiments/cv/report.py</code></p>

<div class="card"><b>한 줄 요약.</b> 학습을 망가뜨린 것은 상자 여백이었고, 상자를 채점과 맞춘 뒤 기업 정답으로 학습하면 각도와 뒷발끝 뒤바뀜이 함께 목표 안으로 들어온다. 가려진 점과 회전은 거의 영향이 없고, 머리만 학습과 전체 학습의 차이는 상자를 맞추고 나면 작아지며, 사람이 안 옮긴 점을 빼면 나빠진다.</div>

<h2>1. 실험마다 어디에 떨어졌나</h2>
<p>가로는 관절 각도 오차, 세로는 뒷발끝 좌우 뒤바뀜입니다. 왼쪽 아래 파란 칸이 목표 안쪽입니다. 점에 마우스를 올리면 수치가 나옵니다.</p>
<div class="card"><div class="lgs">{legend}</div>{scatter()}</div>

<h2>2. 요인별로 묶어 보면</h2>
<p>한 가지만 바꾼 실험끼리 짝을 지어, 그 요인이 각도 오차를 얼마나 바꿨는지 모았습니다. 왼쪽(파랑)은 좋아짐, 오른쪽(빨강)은 나빠짐입니다. 막대에 마우스를 올리면 뒷발끝과 PCK 변화도 나옵니다. 0.2~0.3° 안쪽 차이는 잡음일 수 있습니다(시드 반복 전).</p>
<div class="card">{effect_chart()}</div>
<ul>
<li><b>확실히 효과 있음</b>: 학습 상자를 채점과 같게, 오토라벨 대신 기업 정답. 두 요인 모두 서로 다른 조건에서 같은 방향으로 크게 나왔습니다.</li>
<li><b>효과 없음</b>: 가려진 점 포함, 회전 줄이기, 마지막 단계까지 학습.</li>
<li><b>하면 안 됨</b>: 사람이 안 옮긴 점 빼기(정답의 37%가 현행 모델 출력이라 그 점들을 함께 배워야 함), 반전 증강 끄기.</li>
<li><b>지켜볼 것</b>: fs-v4와 반반 섞기. 각도는 비슷하고 점 정확도(PCK@0.05)가 가장 높았습니다. 처음 보는 개에서 덜 무너질지 확인합니다.</li>
</ul>

<h2>3. 다른 개에서는 (진행 중)</h2>
<p>제니 205장 전부로 학습한 모델을 학습에 쓰지 않은 개로 채점합니다. 팀 시험 라벨과 와우와우 라벨은 기업의 자가 아니므로 절대 점수가 아니라 fs-v4 대비 변화, 특히 좌우 뒤바뀜과 편향을 뺀 오차를 봅니다.</p>
<div class="card tblwrap">{table_ext()}</div>

<h2>4. 전체 표</h2>
<div class="card tblwrap">{table_cv()}</div>
<p class="sub">각도와 뒷발끝, 앞발끝, PCK@0.05는 flip 없이 잰 두 방향 평균입니다. "각도 (flip)"은 좌우 반전 추론을 켠 값입니다. 박규원 E-095~E-098과 같은 묶음 나눔이지만, 같은 설정의 G1은 이 틀에서 0.4° 정도 덜 좋아서 구현 차이를 확인해야 합니다.</p>
</main>
<div id="tip" role="tooltip"></div>
<script>
const tip=document.getElementById('tip');
function show(e){{const t=e.target.getAttribute('data-tip');if(!t)return;tip.textContent=t;tip.style.display='block';
const r=e.target.getBoundingClientRect();const x=(e.clientX||r.right)+12,y=(e.clientY||r.top)+12;
tip.style.left=Math.min(x,window.innerWidth-tip.offsetWidth-8)+'px';tip.style.top=Math.min(y,window.innerHeight-tip.offsetHeight-8)+'px';}}
document.querySelectorAll('[data-tip]').forEach(el=>{{el.addEventListener('mousemove',show);el.addEventListener('focus',show);
el.addEventListener('mouseleave',()=>tip.style.display='none');el.addEventListener('blur',()=>tip.style.display='none');}});
</script></body></html>"""
OUT.write_text(page, encoding="utf-8")
print("->", OUT, len(pts), "points", len(effects), "effects")
