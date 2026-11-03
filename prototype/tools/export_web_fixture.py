"""React 웹(web/)의 시연·화면 비교용 데이터를 웹 시제품의 시연 데이터 그대로 JSON 으로 내보낸다(11-02).

    python prototype/tools/export_web_fixture.py

- 출력: web/src/mocks/fixture.json. 웹은 백엔드에 아직 없는 기능(메모·바이탈·진단 이력·영상·회차 결과)을 이 데이터로 채우고,
  `--mode mock` 이면 모든 화면을 이 데이터로 그린다. 시제품과 같은 데이터라 두 화면을 픽셀 단위로 견줄 수 있다.
- 날짜는 내보낸 날 기준 상대값이다. 웹은 `exported_on` 과 오늘의 차이만큼 날짜를 밀어서 쓴다(매일 "오늘" 탭이 같은 모양).
- 회사 데이터(company_sample.json)는 있어도 읽지 않는다.
"""

import dataclasses
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "prototype"))

from proto_app import real  # noqa: E402

real.REAL_FILES = [real.ASSETS / "demo_sessions.json"]   # 회사 데이터 빼기
real.sessions.cache_clear()

from proto_app import seed  # noqa: E402
from proto_app.store import store  # noqa: E402

OUT = ROOT / "web" / "src" / "mocks" / "fixture.json"


def plain(o):
    if dataclasses.is_dataclass(o):
        return {k: plain(v) for k, v in dataclasses.asdict(o).items()}
    if isinstance(o, dict):
        return {k: plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [plain(v) for v in o]
    return o


def main():
    seed.seed()
    now = time.time()
    accounts = []
    for a in store.accounts.values():
        d = plain(a)
        for j in d["jobs"]:
            j["started_ago"] = round(now - j.pop("started"), 3)   # 시작 시각 대신 "몇 초 전" (웹이 불러온 때 기준으로 다시 맞춘다)
        accounts.append(d)
    doc = {"exported_on": date.today().isoformat(), "note": "prototype/tools/export_web_fixture.py 로 만든 시연 데이터. 회사 데이터 없음",
           "accounts": accounts, "staff": [plain(s) for s in store.staff.values()], "codes": [plain(c) for c in store.codes.values()],
           "sessions": [{k: v for k, v in s.items() if k != "angle_series"} for s in real.sessions()]}   # 프레임별 각도는 화면에 안 씀
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False) + "\n", encoding="utf-8")
    print(OUT, f"{OUT.stat().st_size / 1e6:.1f}MB", {a["id"]: len(a["dogs"]) for a in accounts})


if __name__ == "__main__":
    main()
