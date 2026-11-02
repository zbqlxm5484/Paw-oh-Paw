"""입각기 비율 참고 분포를 공개 실측 데이터에서 만든다(11-02). 회사 데이터는 쓰지 않는다.

    python prototype/tools/build_stance_reference.py <pone.0198893.s001.xlsx>

- 원자료: Mahidhar et al. / PLOS ONE 2018 "Automatic characterization of stride parameters in canines with a single
  wearable inertial sensor" 보충 자료 S1(figshare 6531881, CC BY 4.0). 개 3마리(혼종), 트레드밀 속도 6단계,
  GoPro 영상으로 사람이 표시한 걸음마다 유각기·입각기 시간(초).
- 걸음 하나 = 유각기 + 바로 뒤 입각기(같은 개·같은 속도). 입각기 비율 = 입각기 ÷ (입각기 + 유각기) × 100.
- 출력: proto_app/static/assets/stance_ref_plos2018.json = 보행 유형(walk·trot)별 걸음 목록 [입각기 %, 주기 초, 속도 단계, 개]
  build_demo_sessions.py 가 회차의 입각기 비율을 이 분포에서 뽑는다.
"""

import json
import sys
from pathlib import Path

import openpyxl

OUT = Path(__file__).resolve().parents[1] / "proto_app" / "static" / "assets" / "stance_ref_plos2018.json"


def main():
    rows = list(openpyxl.load_workbook(sys.argv[1], read_only=True, data_only=True)["Included Steps"].iter_rows(values_only=True))[2:]
    out = {"walk": [], "trot": []}
    for a, b in zip(rows, rows[1:]):
        if a[1] != "swing" or b[1] != "stance" or a[12] != b[12] or a[13] != b[13]:
            continue
        gait = str(a[5]).strip().lower()
        if gait not in out:          # 'looking up' 같은 주석 걸음은 뺀다
            continue
        sw, st = float(a[4]), float(b[4])
        out[gait].append([round(st / (st + sw) * 100, 1), round(st + sw, 3), a[13], a[12]])
    doc = {"source": "PLOS ONE 2018 (doi:10.1371/journal.pone.0198893) 보충 자료 S1, figshare 6531881, CC BY 4.0",
           "note": "개 3마리(혼종) 트레드밀, 영상에서 사람이 표시한 걸음별 입각기·유각기. [입각기 %, 주기 초, 속도 단계, 개]",
           "gaits": out}
    OUT.write_text(json.dumps(doc, ensure_ascii=False) + "\n", encoding="utf-8")
    print(OUT.name, {k: len(v) for k, v in out.items()})


if __name__ == "__main__":
    main()
