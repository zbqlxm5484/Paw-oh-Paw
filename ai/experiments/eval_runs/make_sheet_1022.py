"""10-22 실험을 팀 실험 기록 시트 형식(탭 3개)으로 내보낸다. 레포 밖, 기업 도구 아님."""

import hashlib
import json
import os
import sys

_PJT = os.environ.get("CREAMOFF_ROOT", "C:/Users/SSAFY/Desktop/PJT")
_OUT = os.environ.get("CREAMOFF_OUT", "C:/Users/SSAFY/Downloads")


sys.stdout.reconfigure(encoding="utf-8")
OUT = f"{_OUT}/구글시트_붙여넣기_1022/"
GT1 = "keypoints_260820 (205장, 221건)"
GT2 = "keypoints_wowwow 검증 288장 (사람 확인분, 5분 간격 묶음 분할)"
FP1 = "a08e9d47b680"
FP2 = hashlib.sha256(open(f"{_PJT}/splits/wowwow/wowwow_val.json", "rb").read()).hexdigest()[:12]
WW = "keypoints_wowwow 학습 1,144장 (사람 확인분, unusable 제외)"
NOV = ("-", "-", "-")  # 영상 KPI 는 26건(260820) 기준이라 와우와우 채점 열에는 해당 없음
E = [
    dict(
        id="E-011",
        f="results/ww_val.fs-v4.json",
        what="[새 정답] 와우와우 검증 288장으로 현행 fs-v4 재기 (기준선)",
        name="fs-v4",
        toml="models/fs-v4.toml",
        w="a4261a107bc8",
        start="-(기업 전달본)",
        diff="E-001 과 같은 모델, 채점 정답만 와우와우",
        seed="-",
        train="-(학습 안 함)",
        gt=GT2,
        gfp=FP2,
        vid=NOV,
        judge="기준선(와우와우)",
        nxt="E-013 비교 기준. 명세 현행값(15.2°, PCK 0.650)과 비슷한 수준",
    ),
    dict(
        id="E-012",
        f="results/ww_val.fs-v4-flip.json",
        what="[새 정답] 와우와우 검증으로 flip test 재기",
        name="fs-v4-flip",
        toml="models/fs-v4-flip.toml",
        w="a4261a107bc8",
        start="-(기업 전달본)",
        diff="E-002 와 같은 모델, 채점 정답만 와우와우",
        seed="-",
        train="-(학습 안 함)",
        gt=GT2,
        gfp=FP2,
        vid=NOV,
        judge="기준선(와우와우, flip)",
        nxt="-",
    ),
    dict(
        id="E-013",
        f="results/ww_val.ft-ww-e1.json",
        what="★ 10-21 추가 라벨(와우와우 사람 라벨)로 이어 학습 — 와우와우 검증 채점",
        name="ft-ww-e1",
        toml="models/ft-ww-e1.toml",
        w="9806b712ef88",
        start="fs-v4 pose.pth",
        diff="사람 라벨 1,144장, 10에폭 lr 5e-5, BN 고정(norm_eval), flip test 켬",
        seed="42",
        train=WW,
        gt=GT2,
        gfp=FP2,
        vid=NOV,
        judge="와우와우에선 개선 (고친 점 각도 22.3→17.6°, 뒷발끝 8.9→2.0%)",
        nxt="E-014 와 같이 판단",
    ),
    dict(
        id="E-014",
        f="results/ft-ww-e1.json",
        what="★ E-013 모델을 기업 정답으로 채점",
        name="ft-ww-e1",
        toml="models/ft-ww-e1.toml",
        w="9806b712ef88",
        start="fs-v4 pose.pth",
        diff="E-013 과 같은 모델",
        seed="42",
        train=WW,
        gt=GT1,
        gfp=FP1,
        vid=("미측정", "미측정", "미측정"),
        judge="기각 (고관절 27°·무릎 19° 로 무너짐). 두 라벨의 고관절·무릎 위치가 몸통 길이 약 5% 다름",
        nxt="기업에 두 라벨 기준·인수 정답 확인 후 결정",
    ),
    dict(
        id="E-015",
        f="results/ww_val.ft-ww-e2.json",
        what="와우와우 학습, 정의 갈리는 8점(어깨뼈·어깨·고관절·무릎) 손실에서 뺌 — 와우와우 검증 채점",
        name="ft-ww-e2",
        toml="models/ft-ww-e2.toml",
        w="09d45e2c107e",
        start="fs-v4 pose.pth",
        diff="E-013 + 8점 가시성 0",
        seed="42",
        train=WW + ", 8점 제외",
        gt=GT2,
        gfp=FP2,
        vid=NOV,
        judge="E-013 보다 약간 나쁨",
        nxt="-",
    ),
    dict(
        id="E-016",
        f="results/ft-ww-e2.json",
        what="E-015 모델을 기업 정답으로 채점",
        name="ft-ww-e2",
        toml="models/ft-ww-e2.toml",
        w="09d45e2c107e",
        start="fs-v4 pose.pth",
        diff="E-015 와 같은 모델",
        seed="42",
        train=WW + ", 8점 제외",
        gt=GT1,
        gfp=FP1,
        vid=("미측정", "미측정", "미측정"),
        judge="기각 (뺀 점도 따라 움직여 flip 보다 나쁨)",
        nxt="점 몇 개 빼는 방식은 재시도 안 함",
    ),
    dict(
        id="E-017",
        f="results/lrx.hind.0.02.json",
        what="flip test + 뒷다리만 영상 좌우 바로잡기 (후처리)",
        name="fs-v4-flip + lr_fix(hind)",
        toml="models/fs-v4-flip.toml",
        w="a4261a107bc8",
        start="-(기업 전달본)",
        diff="E-004 에서 앞다리는 안 바꿈(원래 뒤바뀜 3.96% 라 바꾸면 틀림), 벌점 0.02, lr_fix.py --legs hind",
        seed="-",
        train="-(학습 안 함)",
        gt=GT1,
        gfp=FP1,
        vid=("0.1154", "14.01", "22"),
        judge="현재 최선 (각도·PCK·뒷발끝 최고, KPI-01 −6.9%, KPI-24 현행의 24%)",
        nxt="속도 재기, 다른 개 영상으로 재확인. E-004 대신 기본값 후보",
    ),
]
R = {e["id"]: json.load(open(e["f"], encoding="utf-8"))["kpi"] for e in E}
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


rows = [("묶음", "항목", "목표 (PRD)") + tuple(e["id"] for e in E)]


def add(group, item, goal, fn):
    rows.append((group, item, goal) + tuple(str(fn(e, R[e["id"]])) for e in E))


add("실험 정보", "날짜", "", lambda e, d: "2026-10-22")
add("", "담당자", "", lambda e, d: "박규원")
add("", "무엇을 해 본 실험인지", "명세서 3.2 목표값", lambda e, d: e["what"])
add("모델 설정", "모델 이름", "", lambda e, d: e["name"])
add("", "설정 파일 (.toml)", "", lambda e, d: e["toml"])
add("", "가중치 파일 지문 (앞 12자)", "", lambda e, d: e["w"])
add("", "학습 시작 가중치", "", lambda e, d: e["start"])
add("", "이전 실험과 다른 점", "", lambda e, d: e["diff"])
add("실행 환경", "난수 시드", "", lambda e, d: e["seed"])
add("", "실행 장치 (CPU/GPU)", "", lambda e, d: "cuda:0")
add(
    "",
    "torch 버전",
    "",
    lambda e, d: "2.1.2+cu121" + (" (학습은 컨테이너 2.7.0+cu128)" if e["seed"] == "42" else ""),
)
add("", "mmpose 버전", "", lambda e, d: "1.3.2")
add("", "채점기 버전", "", lambda e, d: "0.1.0")
add("", "각도 정의 버전", "", lambda e, d: "v1")
add("", "측정 PC", "", lambda e, d: "RTX 4070 Laptop (박규원)")
add("데이터", "학습에 쓴 데이터", "", lambda e, d: e["train"])
add("", "채점에 쓴 정답", "", lambda e, d: e["gt"])
add("", "정답 파일 지문 (앞 12자)", "", lambda e, d: e["gfp"])
add("핵심 지표 5개", "KPI-04 관절 각도 평균 오차 (°)", "7", lambda e, d: d["KPI-04"]["mae"])
add("", "KPI-12 유효 영상을 무효로 잘못 본 비율", "0.05", lambda e, d: "")
add("", "KPI-19 관절 맞힌 비율 (엄격, 5% 안)", "0.5000", lambda e, d: f"{d['KPI-19']['value']:.4f}")
add("", "KPI-21 앞발끝 좌우 바뀐 비율", "3.0%", lambda e, d: pct(d["KPI-21"]["front"]["value"]))
add("", "KPI-21 뒷발끝 좌우 바뀐 비율", "3.0%", lambda e, d: pct(d["KPI-21"]["hind"]["value"]))
add(
    "",
    "KPI-22 가장 못 맞힌 관절의 비율",
    "6.5.3 기준 모든 관절점",
    lambda e, d: f"{worst(d)[0]:.4f}",
)
add("", "KPI-22 그 관절 이름", "", lambda e, d: worst(d)[1])
add(
    "사람이 고친 점만 센 값",
    "관절 각도 평균 오차 (°)",
    "",
    lambda e, d: d["KPI-04"]["touched_only"]["mae"],
)
add("", "관절 맞힌 비율 (엄격)", "", lambda e, d: f"{d['KPI-19']['touched_only']:.4f}")
add("", "앞발끝 좌우 바뀐 비율", "", lambda e, d: pct(d["KPI-21"]["front"]["touched_only"]))
add("", "뒷발끝 좌우 바뀐 비율", "", lambda e, d: pct(d["KPI-21"]["hind"]["touched_only"]))
add("", "가장 못 맞힌 관절의 비율", "", lambda e, d: f"{worst(d, True)[0]:.4f}")
add(
    "참고 지표",
    "KPI-18 관절 맞힌 비율 (느슨, 10% 안)",
    "0.8000",
    lambda e, d: f"{d['KPI-18']['value']:.4f}",
)
add(
    "",
    "KPI-20 위치 오차 중앙값 (몸통 길이 대비)",
    "0.0500",
    lambda e, d: f"{d['KPI-20']['value']:.4f}",
)
add("", "KPI-01 다리 길이 흔들림 (변동계수)", "현행 대비 -30%", lambda e, d: e["vid"][0])
add("", "KPI-02 화면 왼쪽·오른쪽 각도 차 (°)", "현행 대비 -50%", lambda e, d: e["vid"][1])
add("", "KPI-24 좌우 다리 바뀐 횟수", "현행의 50% 이하", lambda e, d: e["vid"][2])
add("결론", "판단", "", lambda e, d: e["judge"])
add("", "다음 할 일", "", lambda e, d: e["nxt"])
add("", "결과 파일 위치", "", lambda e, d: "paw_eval/" + e["f"])
open(OUT + "1_실험기록_E011-E017.tsv", "w", encoding="utf-8-sig").write(
    "\n".join("\t".join(r) for r in rows) + "\n"
)

names = list(R["E-011"]["KPI-22"].keys())
jr = [
    ["관절 이름", "관절별 목표 (명세서 6.5.3)"]
    + [f"{e['id']} {s}" for e in E for s in ("맞힌 비율", "고친 점만 맞힌 비율", "고친 점 개수")]
]
for n in names:
    r = [n, "0.9000" if n in ("t13_spinous_process", "iliac_crest") else ""]
    for e in E:
        v = R[e["id"]]["KPI-22"][n]
        r += [
            f"{v['value']:.4f}",
            "" if v.get("touched_only") is None else f"{v['touched_only']:.4f}",
            str(v.get("n_touched", 0)),
        ]
    jr.append(r)
open(OUT + "2_관절별_E011-E017.tsv", "w", encoding="utf-8-sig").write(
    "\n".join("\t".join(r) for r in jr) + "\n"
)
print(len(rows) - 1, "항목 /", len(jr) - 1, "관절")
