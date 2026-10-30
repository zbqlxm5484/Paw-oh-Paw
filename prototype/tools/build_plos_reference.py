"""공개 데이터(건강한 대형견 6마리)로 관절 각도 정상 참고 곡선을 만든다.

    python prototype/tools/build_plos_reference.py <S1_DataSet 폴더> <출력.json>

출처: Catavitello G, Ivanenko YP, Lacquaniti F (2015) Planar Covariation of Hindlimb and Forelimb Elevation Angles
during Terrestrial and Aquatic Locomotion of Dogs. PLOS ONE 10(7): e0133936. doi:10.1371/journal.pone.0133936
부록 S1_Dataset, CC BY 4.0. 골든·래브라도 리트리버 6마리(35±4 kg), 옆에서 찍은 영상의 표지점 2D 좌표(60/120 fps).

- 카메라 쪽 다리 한쪽만 있다. 뒷다리 표지점 SCA·GTR(대전자)·KNE·ANK·VMT·DPH, 앞다리 SCA·SHO·ELB·WRI·DPF.
- 관절각은 engine/angles.py v1 정의(굽히는 쪽에서 잰 0~360)로 우리와 같게 계산한다. 머리 방향 = 대전자 → 어깨뼈.
  우리 22점과의 짝: 무릎(14,15,16)=GTR·KNE·ANK, 뒷발목(15,16,17)=KNE·ANK·VMT, 어깨(3,4,5)=SCA·SHO·ELB,
  팔꿈치(4,5,6)=SHO·ELB·WRI, 앞발목(5,6,7)≈ELB·WRI·DPF(발끝이라 우리 5번째 손허리뼈 끝보다 조금 아래). 고관절은 장골능 점이 없어 뺀다.
- 한 걸음 = 저자가 표시한 같은 발 착지 → 다음 착지(cp). N_PHASE 칸으로 다시 뽑아 개마다 평균한 뒤, 6마리 평균과 최소·최대.
"""

import json
import statistics
import sys
from pathlib import Path

import numpy as np
import scipy.io as sio

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.angles import ANGLE_DEF, FLEX_SIDE, flexion_angle  # noqa: E402

N_PHASE = 50
JOINTS = {   # 관절: (다리, 근위, 꼭짓점, 원위)
    "무릎": ("hindlimb", "GTR", "KNE", "ANK"),
    "뒷발목": ("hindlimb", "KNE", "ANK", "VMT"),
    "어깨": ("forelimb", "SCA", "SHO", "ELB"),
    "팔꿈치": ("forelimb", "SHO", "ELB", "WRI"),
    "앞발목": ("forelimb", "ELB", "WRI", "DPF"),
}
GAITS = {"walking": "walk", "trotting": "trot"}


def as_list(x):
    return x if isinstance(x, list) else [x]


def strides(trial, joint):
    """한 시행의 걸음마다 관절각 곡선(N_PHASE 칸)"""
    _, a, v, b = JOINTS[joint]
    P = {p["label"]: np.c_[p["X"], p["Y"]] for p in trial["P"]}
    hp = {p["label"]: np.c_[p["X"], p["Y"]] for p in trial["_hind"]["P"]}   # 머리 방향용 대전자는 뒷다리 쪽에 있다
    sca, gtr = P.get("SCA", hp.get("SCA")), hp["GTR"]
    out = []
    for td0, _, td1 in np.atleast_2d(trial["cp"]).astype(int):
        vals = []
        for f in range(td0, td1):
            cranial = sca[f] - gtr[f]
            ang = flexion_angle(P[v][f], P[a][f], P[b][f], cranial, FLEX_SIDE[joint])
            vals.append(np.nan if ang is None or not np.isfinite(ang) else ang)
        vals = np.array(vals, float)
        if np.isnan(vals).mean() > 0.2 or len(vals) < 5:
            continue
        x = np.arange(len(vals))
        ok = ~np.isnan(vals)
        vals = np.interp(x, x[ok], vals[ok])
        out.append(np.interp(np.arange(N_PHASE) * len(vals) / N_PHASE, x, vals))
    return out


def main(src, dst):
    src = Path(src)
    res = {"source": "Catavitello et al. 2015, PLOS ONE 10(7): e0133936, S1_Dataset (CC BY 4.0)",
           "dogs": "골든·래브라도 리트리버 6마리, 35±4 kg, 건강", "angle_def": ANGLE_DEF, "n_phase": N_PHASE, "gaits": {}}
    for mo, gk in GAITS.items():
        g = {}
        for joint, (limb, *_) in JOINTS.items():
            per_dog, n_str = [], 0
            for f in sorted((src / "Dogs Data").glob("Dog*.mat")):
                D = sio.loadmat(f, simplify_cells=True)["dogdata"][mo]
                curves = []
                for t, th in zip(as_list(D[limb]), as_list(D["hindlimb"])):
                    t = dict(t, _hind=th)
                    curves += strides(t, joint)
                if curves:
                    per_dog.append(np.mean(curves, axis=0))
                    n_str += len(curves)
            M = np.array(per_dog)
            g[joint] = {"dogs": len(per_dog), "strides": n_str, "mean": np.round(M.mean(0), 2).tolist(),
                        "min": np.round(M.min(0), 2).tolist(), "max": np.round(M.max(0), 2).tolist(),
                        "rom_by_dog": [round(float(np.ptp(c)), 1) for c in per_dog]}
        res["gaits"][gk] = g
    Path(dst).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for gk, g in res["gaits"].items():
        for j, v in g.items():
            m = v["mean"]
            print(gk, j, f"{v['dogs']}마리 {v['strides']}걸음", f"평균 {statistics.fmean(m):.0f}° 폭 {max(m) - min(m):.0f}°", "개별 폭", v["rom_by_dog"])


if __name__ == "__main__":
    main(*sys.argv[1:3])
