"""10-22 오후·저녁 실험(E-029~E-045, 노션 실험 28~35. E-028 까지는 시트에 붙임)을 팀 시트 형식으로 내보낸다. 항목 이름 열 없이 실험 번호 줄부터.
E-040~E-044 는 정답 상자 대신 '영상에서 탐지·보간한 상자'로 찍은 점을 채점한 값이라 E-024 이전 값과 바로 비교하지 않는다."""

import json
import os
import sys
from pathlib import Path

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")
_OUT = os.environ.get("CREAMOFF_OUT", "C:/Users/SSAFY/Downloads")


sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(f"{_OUT}/구글시트_붙여넣기_1022_오후/")
GT1, FP1 = "keypoints_260820 (205장, 221건)", "a08e9d47b680"
GT2 = "keypoints_wowwow 검증 288장 (사람 확인분, 5분 간격 묶음 분할)"
FP2 = (
    __import__("hashlib")
    .sha256(open(f"{_PJT}/splits/wowwow/wowwow_val.json", "rb").read())
    .hexdigest()[:12]
)
VB = " [영상 상자로 채점: 정답 사진의 원본 영상을 추적해 그 프레임 점을 씀]"
WW = {
    t: json.load(open(f"results/vww_{t}.json", encoding="utf-8"))["kpi"]["KPI-04"]["mae"]
    for t in ("s1", "s3", "s4", "s5", "s3h")
    if Path(f"results/vww_{t}.json").exists()
}
ww = lambda t: f" / 와우와우 같은 방식 {WW[t]}°" if t in WW else ""
POSE = [
    dict(
        id="E-033",
        f="results/fs-v4-fp16.json",
        what="가중치를 fp16 으로 저장 (같은 모델, 크기 줄이기)",
        name="fs-v4-fp16",
        model="models/fs-v4-fp16.toml",
        diff="E-000 과 같은 모델, det.pth·pose.pth 숫자만 16비트로 저장(불러올 때 32비트로 계산)",
        judge="채택 (크기 150.8→80.6MiB, KPI-17 통과, 정확도 그대로 8.02°)",
        nxt="계산도 16비트로(E-044·E-045)",
    ),
    dict(
        id="E-034",
        f="results/dark_gt.json",
        what="flip + DARK 소수점 좌표 읽기",
        name="fs-v4-flip-dark",
        model="models/fs-v4-flip-dark.toml",
        diff="E-002 에서 점 읽기 방식만 DARK",
        judge="안 씀 (전체 7.89→7.78° 지만 고친 점 13.17→13.48° 악화, 엇갈림)",
        nxt="-",
    ),
    dict(
        id="E-035",
        f="results/dark_ww.json",
        what="[와우와우 정답] flip + DARK",
        name="fs-v4-flip-dark",
        model="models/fs-v4-flip-dark.toml",
        diff="E-034 와 같은 방법, 채점 정답만 와우와우",
        gt=GT2,
        gfp=FP2,
        judge="작은 개선 (17.68→17.49°). E-034 와 엇갈려 안 씀",
        nxt="-",
    ),
    dict(
        id="E-036",
        f="results/rot/gt/ms5_rot_hind.json",
        what="★ flip + 배율 5 + 회전 ±8° + 뒷다리 좌우 바로잡기",
        name="fs-v4-flip + 배율 5 + 회전 ±8 + lr_fix(hind)",
        diff="E-027 + 사진을 상자 가운데 기준 ±8° 돌려 추론 후 되돌려 평균(rotate_tta.py), 7가지 평균",
        judge="현재 최선 (7.36→7.32°, 현행 대비 −8.8%, 고친 점 12.13°, 엄격 PCK 0.760)",
        nxt="시험 라벨로 학습한 가중치에 얹어 다시 잼",
    ),
    dict(
        id="E-037",
        f="results/rot/ww/ms5_rot.json",
        what="[와우와우 정답] flip + 배율 5 + 회전 ±8°",
        name="fs-v4-flip + 배율 5 + 회전 ±8",
        diff="E-036 에서 뒷다리 보정 뺌(와우와우엔 효과 없음), 채점 정답만 와우와우",
        gt=GT2,
        gfp=FP2,
        judge="개선 (배율 5 17.29→17.16°). 기업 정답과 같은 방향",
        nxt="-",
    ),
    dict(
        id="E-038",
        f="results/rot/gt/ms5_rot_ts1_0.25.json",
        what="flip + 배율 5 + 회전 + 앞뒤 1프레임 점 평균(가중 0.25)",
        name="+ temporal_smooth k1 w0.25",
        diff="E-036 의 뒷다리 보정 전 단계(7.55°)에 영상 앞뒤 프레임 점을 다리별 좌우 맞춘 뒤 가중 평균(temporal_smooth.py)",
        judge="안 씀 (7.55→8.33°, 몸통 이동 보정해도 8.46°, 섞을수록 악화)",
        nxt="영상 앞뒤 정보는 좌우 고르기에만 씀",
    ),
    dict(
        id="E-039",
        f="results/rot/ww/ms5_rot_ts1_0.25.json",
        what="[와우와우 정답] 앞뒤 1프레임 점 평균",
        name="+ temporal_smooth k1 w0.25",
        diff="E-038 과 같은 방법, 채점 정답만 와우와우",
        gt=GT2,
        gfp=FP2,
        judge="안 씀 (17.16→18.19°)",
        nxt="-",
    ),
    dict(
        id="E-040",
        f="results/vgt_s1.json",
        what="매 프레임 탐지 (탐지 간격 비교의 기준)" + VB,
        name="fs-v4 (det_stride 1)",
        model="models/fs-v4.toml",
        diff="E-000 모델 그대로, flip 없음. 정답 상자 대신 영상 추적 상자",
        judge=f"비교 기준 7.07°{ww('s1')}",
        nxt="E-041~E-043 과 비교",
    ),
    dict(
        id="E-041",
        f="results/vgt_s3.json",
        what="3프레임마다 한 번만 탐지, 사이는 상자 선형 보간" + VB,
        name="fs-v4 (det_stride 3)",
        model="models/fs-v4.toml",
        diff="E-040 에서 탐지 횟수만 1/3 (det_stride.py)",
        judge=f"정확도 손해 (7.07→7.37°, 엄격 PCK 0.808→0.779){ww('s3')}. 속도 38%",
        nxt="정확도 우선이라 보류",
    ),
    dict(
        id="E-042",
        f="results/vgt_s4.json",
        what="4프레임마다 탐지" + VB,
        name="fs-v4 (det_stride 4)",
        model="models/fs-v4.toml",
        diff="E-041 에서 간격 4",
        judge=f"정확도 손해 (7.40°){ww('s4')}. 속도 30%",
        nxt="보류",
    ),
    dict(
        id="E-043",
        f="results/vgt_s5.json",
        what="5프레임마다 탐지" + VB,
        name="fs-v4 (det_stride 5)",
        model="models/fs-v4.toml",
        diff="E-041 에서 간격 5",
        judge=f"정확도 손해 (7.62°){ww('s5')}. 속도 26%",
        nxt="보류",
    ),
    dict(
        id="E-044",
        f="results/vgt_s3h.json",
        what="3프레임마다 탐지 + fp16 계산" + VB,
        name="fs-v4 (det_stride 3, fp16 autocast)",
        model="models/fs-v4.toml",
        diff="E-041 + 탐지·관절점 계산을 16비트로(torch.autocast)",
        judge="정확도 손해 (E-041 7.37→7.51°, fp16 계산만으로 +0.14°)" + ww("s3h") + ". 속도 28%",
        nxt="보류",
    ),
]
POSE = [e for e in POSE if Path(e["f"]).exists()]
DET = [  # 탐지기 실험: 관절점 정확도는 따로 안 잼(관절점 모델은 그대로). 속도·KPI-23 은 처리 성능 탭
    dict(
        id="E-029",
        what="가벼운 탐지기 2판 tiny (문턱 0.25)",
        name="fs-v4-dettiny-ft2",
        diff="탐지기만 RTMDet-tiny 를 크림오프 개 상자 7,434장으로 학습",
        judge="KPI-23 불합격(최악 −11.8%p). ※ 기존 모델 구조 유지 원칙으로 채택 안 함",
        nxt="문턱 낮추기(E-030)",
    ),
    dict(
        id="E-030",
        what="가벼운 탐지기 2판 tiny (문턱 0.08)",
        name="fs-v4-dettiny-ft2-t08",
        diff="E-029 의 점수 문턱 0.25→0.08",
        judge="KPI-14·17·23 통과(헛상자 476장). ※ 구조가 달라 채택 안 함",
        nxt="헛상자 거르기(E-031)",
    ),
    dict(
        id="E-031",
        what="E-030 + 화면 끝 헛상자 거르기",
        name="fs-v4-dettiny-ft2-t08 + edge_filter",
        diff="E-030 + edge_filter.py",
        judge="KPI-23 최악 −0.50%p(경계), 와우와우에선 효과 거의 없음. ※ 채택 안 함",
        nxt="-",
    ),
    dict(
        id="E-032",
        what="전체 조합: 2판 tiny(0.08) + flip + 뒷다리 보정",
        name="dettiny-ft2-t08 + fs-v4-flip + lr_fix(hind)",
        diff="E-030 탐지기 + E-017 관절점 설정",
        judge="속도 47.5% 통과, KPI-04 7.87°(E-017 과 같음). ※ 구조가 달라 채택 안 함",
        nxt="-",
    ),
]
for e in DET:
    e["f"] = None
POSE = DET + POSE
pct = lambda x: f"{100 * x:.1f}%"


def worst(d, touched=False):
    j = d["KPI-22"]
    if touched:
        return min(
            (v["touched_only"], n)
            for n, v in j.items()
            if v.get("touched_only") is not None and v.get("n_touched")
        )
    return min((v["value"], n) for n, v in j.items())


R = {e["id"]: json.load(open(e["f"], encoding="utf-8"))["kpi"] if e["f"] else None for e in POSE}
rows = [[e["id"] for e in POSE]]


def add(fn):
    def cell(e):
        try:
            return str(fn(e, R[e["id"]]))
        except TypeError:  # 탐지기 실험(정확도 없음)
            return "-"

    rows.append([cell(e) for e in POSE])


add(lambda e, d: "2026-10-22")
add(lambda e, d: "박규원")
add(lambda e, d: e["what"])
add(lambda e, d: e["name"])
add(lambda e, d: e.get("model", "models/fs-v4-flip.toml"))
add(lambda e, d: "a4261a107bc8")
add(lambda e, d: "-(기업 전달본)")
add(lambda e, d: e["diff"])
add(lambda e, d: "-")
add(lambda e, d: "cuda:0")
add(lambda e, d: "2.1.2+cu121")
add(lambda e, d: "1.3.2")
add(lambda e, d: "0.1.0")
add(lambda e, d: "v1")
add(lambda e, d: "RTX 4070 Laptop (박규원)")
add(lambda e, d: "-(학습 안 함)")
add(lambda e, d: e.get("gt", GT1))
add(lambda e, d: e.get("gfp", FP1))
add(lambda e, d: d["KPI-04"]["mae"])
add(lambda e, d: "")
add(lambda e, d: f"{d['KPI-19']['value']:.4f}")
add(lambda e, d: pct(d["KPI-21"]["front"]["value"]))
add(lambda e, d: pct(d["KPI-21"]["hind"]["value"]))
add(lambda e, d: f"{worst(d)[0]:.4f}")
add(lambda e, d: worst(d)[1])
add(lambda e, d: d["KPI-04"]["touched_only"]["mae"])
add(lambda e, d: f"{d['KPI-19']['touched_only']:.4f}")
add(lambda e, d: pct(d["KPI-21"]["front"]["touched_only"]))
add(lambda e, d: pct(d["KPI-21"]["hind"]["touched_only"]))
add(lambda e, d: f"{worst(d, True)[0]:.4f}")
add(lambda e, d: f"{d['KPI-18']['value']:.4f}")
add(lambda e, d: f"{d['KPI-20']['value']:.4f}")
add(lambda e, d: "미측정")
add(lambda e, d: "미측정")
add(lambda e, d: "미측정")
add(lambda e, d: e["judge"])
add(lambda e, d: e["nxt"])
add(
    lambda e, d: "paw_eval/" + e["f"]
    if e["f"]
    else "paw_eval/results/speed_dettiny_ft2.json, combo_speed.json"
)
last = POSE[-1]["id"]
(OUT / f"8_실험기록_E029-E{last[2:]}.tsv").write_text(
    "\n".join("\t".join(r) for r in rows) + "\n", encoding="utf-8-sig"
)

POSE = [e for e in POSE if e["f"]]
names = list(R[POSE[0]["id"]]["KPI-22"].keys())
jr = [
    [f"{e['id']} {s}" for e in POSE for s in ("맞힌 비율", "고친 점만 맞힌 비율", "고친 점 개수")]
]
for n in names:
    r = []
    for e in POSE:
        v = R[e["id"]]["KPI-22"][n]
        r += [
            f"{v['value']:.4f}",
            "" if v.get("touched_only") is None else f"{v['touched_only']:.4f}",
            str(v.get("n_touched", 0)),
        ]
    jr.append(r)
(OUT / f"9_관절별_E033-E{last[2:]}.tsv").write_text(
    "\n".join("\t".join(r) for r in jr) + "\n", encoding="utf-8-sig"
)

# 처리 성능: 같은 작업(results/stride_fp16_speed_1022.txt)에서 잰 값. 기준 = 매 프레임 탐지 3.077초
SP = {
    "1": (3.077, 2.92, 0.15),
    "3": (1.168, 1.00, 0.17),
    "4": (0.915, 0.75, 0.17),
    "5": (0.795, 0.62, 0.17),
    "h1": (2.013, 1.82, 0.19),
    "h3": (0.873, 0.65, 0.22),
}
base = SP["1"][0]
old7 = [
    l.split("	")
    for l in (OUT / "7_처리성능_E024-E032.tsv").read_text(encoding="utf-8-sig").splitlines()
]
cols = [
    [r[i] for r in old7] for i, h in enumerate(old7[0]) if h in ("E-029", "E-030", "E-031", "E-032")
]


def sp(i, key, size, note):
    t, dt, pt = SP[key]
    cols.append(
        [
            i,
            "2026-10-22",
            "RTX 4070 Laptop (박규원)",
            "충전 중",
            "cuda:0",
            f"{t:.3f}",
            f"{t / base:.3f}",
            "",
            "",
            "미측정",
            "미측정",
            size,
            f"{dt:.2f}/{pt:.2f}",
            "paw_eval/results/stride_fp16_speed_1022.txt",
            note,
        ]
    )


cols.append(
    [
        "E-033",
        "2026-10-22",
        "RTX 4070 Laptop (박규원)",
        "-",
        "-",
        "-",
        "-",
        "",
        "",
        "-",
        "-",
        "80.6",
        "-",
        "paw_eval/models/fs-v4-fp16/",
        "탐지 52.5 + 관절점 28.1MiB. KPI-17(100MiB 이하) 통과. 계산은 32비트라 속도는 E-000 과 같음",
    ]
)
# 정확도만 잰 실험: 속도 안 잼
NOSP = {
    "E-034": "DARK 는 안 쓰기로 해서 속도 안 잼",
    "E-035": "E-034 의 와우와우 채점판, 속도 안 잼",
    "E-036": "회전은 사진을 돌려 따로 추론해 채점만 함(rotate_tta.py), 실시간 추론엔 아직 없어 속도 안 잼. 참고: 배율 5까지는 3.859초(E-027)",
    "E-037": "E-036 의 와우와우 채점판, 속도 안 잼",
    "E-038": "영상 앞뒤 평균은 안 쓰기로 해서 속도 안 잼",
    "E-039": "E-038 의 와우와우 채점판, 속도 안 잼",
}
for i, note in NOSP.items():
    cols.append(
        [
            i,
            "2026-10-22",
            "RTX 4070 Laptop (박규원)",
            "-",
            "-",
            "미측정",
            "-",
            "",
            "",
            "-",
            "-",
            "150.8",
            "-",
            "-",
            note,
        ]
    )
sp("E-040", "1", "150.8", "det_stride.py 로 잰 기준(매 프레임 탐지). 영상 10건 × 3회 중앙값")
sp("E-041", "3", "150.8", "KPI-14 통과. 영상 KPI-23 통과·KPI-24 99회(기준 91)")
sp("E-042", "4", "150.8", "KPI-23 통과(최악 −0.46%p)·KPI-24 85회·KPI-02 12.43°")
sp("E-043", "5", "150.8", "KPI-23 통과(0.0%p)·KPI-24 84회·KPI-02 12.05°")
sp("E-044", "h3", "150.8", "fp16 계산 + 3프레임마다. KPI-23 통과·KPI-24 97회·KPI-02 13.25°")
sp("E-045", "h1", "150.8", "fp16 계산(torch.autocast)만, 매 프레임 탐지. 정확도는 미측정")
rows3 = [list(r) for r in zip(*cols)]
(OUT / "10_처리성능_E029-E045.tsv").write_text(
    "\n".join("\t".join(r) for r in rows3) + "\n", encoding="utf-8-sig"
)
print(
    len(POSE),
    "실험(",
    POSE[0]["id"],
    "~",
    last,
    ") /",
    len(jr) - 1,
    "관절 /",
    len(cols),
    "열(처리 성능)",
)
