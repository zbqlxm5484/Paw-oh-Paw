"""views.py·real.py 화면 값을 JSON 으로 떠서 TS 옮김(web/src/views)과 견준다(11-02).

    python prototype/tools/export_web_fixture.py   # 같은 날 fixture 먼저
    python web/scripts/dump_views.py
    cd web && npx vitest run src/views

- 시제품을 export_web_fixture.py 와 똑같이 불러온다(회사 데이터 빼기, 같은 seed) → fixture.json 과 같은 데이터.
- 출력: web/src/views/__parity__/expected.json. 무엇을 뜨는지는 CASES(아래)와 views.parity.test.ts 가 같다.
- 몸 그림 svg 는 SVG_FULL 회차만 통째로 담고 나머지는 뺀다(파일 크기).
"""

import dataclasses
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "prototype"))

from proto_app import real  # noqa: E402

real.REAL_FILES = [real.ASSETS / "demo_sessions.json"]   # 회사 데이터 빼기(export_web_fixture.py 와 같게)
real.sessions.cache_clear()

from proto_app import seed, views  # noqa: E402  (views 는 불러올 때 ROM_REF 를 sessions() 로 계산)
from proto_app.store import store  # noqa: E402

OUT = ROOT / "web" / "src" / "views" / "__parity__" / "expected.json"
SVG_FULL = {"r1", "r2", "r3", "r4", "r5"}
CMP_DOGS = ["d1", "d2", "d3", "d4", "g001", "g002", "g003"]
HOME = [  # (view, q, dog, by, changed, stage, page)
    ("today", "", "", "", False, "", 1), ("dogs", "", "", "", False, "", 1), ("dogs", "", "", "", False, "", 2),
    ("dogs", "", "", "", False, "", 99), ("dogs", "", "", "", True, "", 1), ("dogs", "보리", "", "", False, "", 1),
    ("dogs", "", "", "", False, "rehab", 1), ("dogs", "", "", "", False, "done", 1), ("dogs", "", "", "", False, "zzz", 1),
    ("staff", "", "", "", False, "", 1), ("staff", "이서연", "", "", False, "", 1),
    ("analyses", "", "", "", False, "", 1), ("analyses", "", "", "", False, "", 3), ("analyses", "", "d1", "", False, "", 1),
    ("analyses", "", "", "최지우 수의사", False, "", 1), ("analyses", "", "", "", True, "pre", 1), ("analyses", "TPLO", "", "", False, "", 1),
    ("other", "", "", "", False, "", 1), ("today", "", "", "", True, "", 1),
]


def plain(o):
    if dataclasses.is_dataclass(o):
        return {k: plain(v) for k, v in dataclasses.asdict(o).items()}
    if isinstance(o, dict):
        return {str(k): plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [plain(v) for v in o]
    if isinstance(o, set):
        return sorted(plain(v) for v in o)
    return o


def main():
    seed.seed()
    acct = store.accounts[seed.DEMO_ID]
    out = {"ROM_REF": views.ROM_REF, "MEDIAN_SPEED": views.MEDIAN_SPEED, "home": [], "dogs": {}, "results": {}, "compare": {}}
    for args in HOME:
        out["home"].append({"args": list(args), "out": views.home_view(acct, *args)})
    out["today_rows"] = views.today_rows(acct, acct.dogs)
    out["analysis_rows"] = views.analysis_rows(acct, acct.results)
    out["staff_rows"] = views.staff_rows(acct, acct.results)
    live = {j.dog for j in acct.active_jobs()}
    for d in acct.dogs:
        out["dogs"][d.id] = {
            "patient_row": views.patient_row(acct, d, live), "dog_detail": views.dog_detail(acct, d),
            "visits": views.visits(acct, d), "dx_history": views.dx_history(acct, d), "memos": views.memos(d),
            "memo_panel": views.memo_panel(acct, d, next((r.id for r in acct.results if r.dog == d.id), "")),
            "soap_entries": views.soap_entries(d, acct), "note_rows": views.note_rows(d, acct), "vital_rows": views.vital_rows(d),
            "kg_trend": views.kg_trend(d), "chart_summary": views.chart_summary(acct, d), "care_team": views.care_team(acct, d),
            "image_list": views.image_list(d), "dog_text": views.dog_text(d), "compare": views.compare_view(acct, d, "prev", "rom"),
        }
    for did in CMP_DOGS:
        d = acct.dog(did)
        out["compare"][did] = {f"{mode}/{tk}": views.compare_view(acct, d, mode, tk)
                               for mode in ("base", "prev") for tk in ("rom", "stride", "stance", "sym", "zzz")}
    for r in acct.results:
        x = {"trot": views.result_view(acct, r), "walk": views.result_view(acct, r, "walk"),
             "home": views.result_view(acct, r, "walk", True), "sym_view": views.sym_view(acct, r)}
        if r.st != "fail":
            bm = views.body_map(acct, r)
            x["best_view"] = views.best_view(bm)
            if r.id not in SVG_FULL:
                bm.pop("svg")
            x["body_map"] = bm
        out["results"][r.id] = x
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(plain(out), ensure_ascii=False), encoding="utf-8")
    print(OUT, f"{OUT.stat().st_size / 1e6:.1f}MB", len(out["dogs"]), "dogs", len(out["results"]), "results")


if __name__ == "__main__":
    main()
