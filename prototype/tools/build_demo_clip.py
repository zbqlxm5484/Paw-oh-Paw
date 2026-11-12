"""3D 걷기·무릎 곡선용 시연 걸음(gait_demo.json)을 공개 데이터와 합성으로 만든다. 회사 데이터는 쓰지 않는다.

    python prototype/tools/build_demo_clip.py

- 어깨·팔꿈치·앞발목·무릎·뒷발목: gait_ref_plos.json(Catavitello et al. 2015 PLOS ONE, CC BY 4.0, 건강한 리트리버 6마리)의
  속보 한 걸음 평균 곡선(50칸, engine/angles v1). tools/build_plos_reference.py 가 만든 파일.
- 고관절: 위 자료에 없어 합성. 한 걸음 사인 곡선, 평균 HIP_MEAN°, 폭은 AI-Hub 71878 시연 회차의 고관절 가동 범위 중앙값
  (demo_sessions.json, 없으면 HIP_ROM). 무릎과 같은 박자로 둔다.
- 왼쪽·오른쪽 다리는 같은 곡선(정상견 가정). 형식은 build_gait_clip.py 의 출력과 같다(3D 는 joint 곡선의 폭만 쓴다).
"""

import json
import math
import statistics
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "proto_app" / "static" / "assets"
REF, DEMO, OUT = ASSETS / "dog3d" / "gait_ref_plos.json", ASSETS / "demo_sessions.json", ASSETS / "dog3d" / "gait_demo.json"
HIP_MEAN, HIP_ROM = 110.0, 28.0
# 시연용 극단 합성(11-02): 오른쪽 뒷다리를 거의 굽히지 않는 절뚝임. 곡선을 평균 쪽으로 이 비율만큼 줄인다.
# 3D '측정 걸음'과 보고서 무릎 곡선에서 차이가 한눈에 보이게 하려는 값이다(실제 개의 값이 아니다)
LIMP = {"RH": {"고관절": 0.3, "무릎": 0.22, "뒷발목": 0.25}}


def squeeze(curve, f):
    m = sum(curve) / len(curve)
    return [round(m + (v - m) * f, 2) for v in curve]


def main():
    ref = json.loads(REF.read_text(encoding="utf-8"))
    trot, n = ref["gaits"]["trot"], ref["n_phase"]
    hip_rom = HIP_ROM
    if DEMO.exists():
        roms = [m["rom_hip"] for s in json.loads(DEMO.read_text(encoding="utf-8"))["sessions"]
                for m in s["metrics"].values() if "rom_hip" in m]
        hip_rom = round(statistics.median(roms), 1) if roms else HIP_ROM
    hip = [round(HIP_MEAN + hip_rom / 2 * math.cos(2 * math.pi * i / n), 2) for i in range(n)]
    front = {j: trot[j]["mean"] for j in ("어깨", "팔꿈치", "앞발목")}
    hind = {"고관절": hip, "무릎": trot["무릎"]["mean"], "뒷발목": trot["뒷발목"]["mean"]}
    strides = min(trot[j]["strides"] for j in ("어깨", "무릎"))
    legs = {}
    for code in ("LF", "RF", "LH", "RH"):
        joint = dict(front if code[1] == "F" else hind)
        for j, f in LIMP.get(code, {}).items():
            joint[j] = squeeze(joint[j], f)
        legs[code] = {"strides": strides, "frames_per_stride": None, "joint": joint}
    doc = {"source": "Catavitello et al. 2015 PLOS ONE (CC BY 4.0) 속보 평균 + 고관절 합성",
           "label": f"시연용 합성: 공개 논문 리트리버 {trot['무릎']['dogs']}마리 속보 평균에서 오른쪽 뒷다리만 굽힘을 크게 줄임",
           "videos": 0, "fps": None, "angle_def": ref["angle_def"], "n_phase": n,
           "seg_names": {"F": ["위팔", "아래팔", "앞발"], "H": ["넙다리", "정강이", "뒷발허리"]},
           "hind_after_front": {"L": 0.5, "R": 0.5}, "legs": legs,
           "note": "시연용 합성. 회사 데이터 없음. 오른쪽 뒷다리 굽힘 폭을 %s 로 줄인 절뚝임 예시, 고관절은 AI-Hub 가동 범위(%.1f°)에 맞춘 합성." % (LIMP["RH"], hip_rom)}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(OUT.name, "고관절 폭", hip_rom)


if __name__ == "__main__":
    main()
