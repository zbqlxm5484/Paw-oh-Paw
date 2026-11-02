"""데모 기관(한빛동물병원)의 예시 데이터.

d1~d4 · r1~r8 은 디자인의 DOGS · RES 와 같은 값이다. 날짜는 오늘을 기준으로 다시 잡아서 언제 켜도
'변동 있음'(최근 7일)에 걸리는 환자가 생긴다. 나머지 116마리는 병원 규모(통원 포함 100마리 이상)를
보려고 만든 가상 환자다. 난수 시드를 고정해서 매번 같은 값이 나온다. 이름·보호자·연락처는 모두 지어낸 값이다.
회차의 보행 수치는 마지막에 real.fill 이 실제 영상에서 잰 회차 수치로 바꾼다.
"""

from __future__ import annotations

import random
import time
from datetime import date, timedelta

from . import config, real
from .store import (
    Account,
    DeviceCode,
    Dog,
    History,
    Image,
    Job,
    Note,
    Result,
    Staff,
    Vital,
    kdate,
    new_id,
    store,
)

DEMO_ID = "demo"
DEMO_STAFF = "s_demo"                 # 데모 기관 담당자(바로가기·둘러보기 로그인)
# 시연용 디바이스 코드(화면 확인용으로 가입 화면에 적어 둔다). 실제 서비스에서는 크림오프 관리 화면에서 발급한다
DEMO_CODE = "HNB7K" "QW9PA" "X2M8N" "H4CDE"
FULL_CODE = "FUZZ2" "QW9PA" "X2M8N" "H4CDE"     # 계정 상한이 찬 코드
EXPIRED_CODE = "EXPR3" "QW9PA" "X2M8N" "H4CDE"  # 계약이 끝난 기관의 코드
N_DOGS = 120
STAFF = ["이서연 원장", "최지우 수의사", "한도윤 수의사", "박민준 테크니션", "정하늘 테크니션"]


def J(a, b, c):
    return [["무릎", a[0], a[1]], ["고관절", b[0], b[1]], ["팔꿈치", c[0], c[1]]]


def _soap(nid: str, at: str, author: str, rid: str, s: str, o: str, a: str, p: str) -> list:
    """방문 하나의 진료 기록: 채운 칸마다 한 줄, 같은 시각·작성자로 묶인다."""
    return [Note(f"{nid}{k}", at, author, k, v, rid=rid) for k, v in zip("SOAP", (s, o, a, p)) if v]


def iso(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


def _res(rid, dog, days_ago, hm, st, w, by, **kw) -> Result:
    d = date.today() - timedelta(days=days_ago)
    return Result(rid, dog, kdate(d), hm, st, w, day=d.isoformat(), by=by, **kw)


# ── 디자인의 반려견 4마리 ──
def _design_dogs() -> tuple[list, list]:
    dogs = [
        Dog("d1", "보리", "골든 리트리버", "2019", "28.4", "fs", rehab=iso(64), focus="RH",
            memo="TPLO 수술 후 재활 9주차. 오른뒤 체중 부하 관찰 중", no="20190412", owner="김하은", phone="010-2481-7730",
            stage="rehab", stage_day=iso(64),
            history=[History(iso(80), "진단", "앞십자인대 파열", "RH", "이서연 원장", "이서연 원장"),
                     History(iso(71), "수술", "TPLO (경골 고원 수평화 절골술)", "RH", "이서연 원장", "이서연 원장"),
                     History(iso(64), "재활", "재활 시작 · 주 1회 보행 측정", "RH", "", "최지우 수의사")],
            vitals=[Vital(iso(3), "28.1", "38.6", "92", "142", "84", "박민준 테크니션"),
                    Vital(iso(16), "28.3", "38.4", "88", "138", "80", "정하늘 테크니션"),
                    Vital(iso(71), "29.4", "38.9", "104", "150", "88", "이서연 원장")],
            notes=[*_soap("n1", f"{iso(3)} 14:40", "최지우 수의사", "r1",
                          "계단 오를 때 머뭇거림이 줄었다고 함. 산책 15분 무리 없음",
                          "오른뒤 체중 부하 늘었음. 대칭 지수 92%(직전 88%). 수술 부위 부종 없음",
                          "TPLO 후 회복 순조",
                          "수중 재활 주 2회 유지, 계단 오르기는 아직 피하도록 보호자에게 안내. 2주 뒤 재측정"),
                   *_soap("n6", f"{iso(16)} 10:40", "최지우 수의사", "r4",
                          "집에서 오른뒤를 들고 서 있는 시간이 줄었다고 함", "대칭 지수 88%, 무릎 굽힘 좌우 차이 남아 있음",
                          "", "산책 10분 → 15분으로 늘리기"),
                   *_soap("n7", f"{iso(71)} 17:30", "이서연 원장", "",
                          "", "TPLO 시행, 마취 회복 양호. 수술 후 방사선에서 플레이트 위치 양호",
                          "앞십자인대 파열 · TPLO 수술 완료", "진통제 5일, 넥카라 착용, 2주 뒤 봉합사 제거"),
                   Note("n2", f"{iso(71)} 18:10", "이서연 원장", "주의", "수술 부위 핥음 → 넥카라 착용 유지", True),
                   Note("n8", f"{iso(20)} 09:15", "정하늘 테크니션", "보호자", "평일 오후 2시 이후만 통화 가능"),
                   Note("n9", f"{iso(3)} 15:05", "박민준 테크니션", "예약", "다음 측정 2주 뒤 오후, 수중 재활 직후 말고 쉬고 나서")],
            images=[Image("i1", iso(80), "pre", "골반·뒷다리 VD", "assets/xray_demo/pelvis_vd.jpg", "이서연 원장"),
                    Image("i2", iso(71), "post", "전신 측면 (참고 그림)", "assets/xray_demo/body_lateral.jpg", "이서연 원장")]),
        Dog("d2", "콩이", "말티즈", "2022", "3.2", "f", no="20220715", owner="이도윤", phone="010-5532-1048",
            stage="pre", stage_day=iso(30),
            history=[History(iso(30), "진단", "슬개골 내측 탈구 2기", "LH", "한도윤 수의사", "한도윤 수의사")],
            vitals=[Vital(iso(30), "3.2", "38.8", "128", "", "", "정하늘 테크니션")],
            notes=[Note("n3", f"{iso(30)} 16:35", "한도윤 수의사", "주의", "겁이 많아 보호자 동반 촬영", True),
                   *_soap("n10", f"{iso(30)} 16:20", "한도윤 수의사", "",
                          "왼뒤를 가끔 들고 깡충 뜀", "슬개골 내측 탈구 2기, 신전 시 통증 반응 약함",
                          "슬개골 내측 탈구 2기", "체중 관리, 4주 보존 치료 후 재평가")]),
        Dog("d3", "두부", "비글", "2021", "11.2", "mn", rehab=iso(27), focus="LF", no="20210303", owner="박서윤",
            phone="010-7714-2295", stage="rehab", stage_day=iso(27),
            history=[History(iso(35), "진단", "요척골 원위 골절", "LF", "최지우 수의사", "최지우 수의사"),
                     History(iso(33), "수술", "골절 정복술 (플레이트 고정)", "LF", "최지우 수의사", "최지우 수의사"),
                     History(iso(27), "재활", "재활 시작", "LF", "", "최지우 수의사")],
            vitals=[Vital(iso(2), "11.0", "38.7", "104", "136", "78", "박민준 테크니션"),
                    Vital(iso(33), "11.4", "38.5", "110", "", "", "최지우 수의사")],
            notes=[Note("n4", f"{iso(2)} 17:55", "박민준 테크니션", "P",
                        "오늘 촬영 중 4번 영상에서 다리 가려짐. 다음 측정 때 오른쪽에서 다시 찍기", False, rid="r2"),
                   Note("n11", f"{iso(2)} 17:58", "박민준 테크니션", "기타", "촬영 때 바닥 미끄러워함, 매트 깔고 찍기")]),
        Dog("d4", "탄이", "진돗개", "2017", "19.8", "m", no="20170921", owner="최지호", phone="010-3390-6621",
            stage="rehab", stage_day=iso(9), focus="LH",
            history=[History(iso(12), "진단", "퇴행성 관절염 (양측 고관절)", "LH", "이서연 원장", "이서연 원장"),
                     History(iso(9), "재활", "보존 치료 · 수중 재활 시작", "LH", "", "이서연 원장")],
            vitals=[Vital(iso(2), "19.6", "38.9", "84", "148", "90", "정하늘 테크니션")],
            notes=[Note("n5", f"{iso(2)} 11:20", "정하늘 테크니션", "주의", "입질 있음, 입마개 착용 후 촬영", True),
                   *_soap("n12", f"{iso(12)} 15:00", "이서연 원장", "",
                          "아침에 일어날 때 뒷다리 뻣뻣함", "양측 고관절 신전 시 통증, 방사선상 관절 간격 좁아짐",
                          "퇴행성 관절염 (양측 고관절)", "보존 치료, 수중 재활 주 2회")],
            images=[Image("i3", iso(12), "xray", "경부·흉부 측면 (참고)", "assets/xray_demo/neck_lateral.jpg", "이서연 원장")]),
    ]
    results = [
        _res("r2", "d3", 2, "17:40", "part", "11.0", "박민준 테크니션", sym=84, rom=44, sL=30, sR=27,
             j=J([58, 49], [40, 36], [47, 45]), ps=(14, 7), ex=[("다리가 가려짐", 4), ("뛰었음", 3)], rep=True),
        _res("r3", "d4", 2, "11:05", "fail", "19.6", "정하늘 테크니션"),
        _res("r1", "d1", 3, "14:20", "ok", "28.1", "박민준 테크니션", sym=92, rom=48, sL=41, sR=38,
             j=J([66, 58], [44, 41], [52, 50]), ps=(18, 12), ex=[("뛰었음", 4), ("중간에 멈춤", 2)], rep=True),
        _res("r4", "d1", 16, "10:12", "ok", "28.3", "정하늘 테크니션", sym=88, rom=48, sL=40, sR=37,
             j=J([65, 56], [43, 40], [51, 49]), ps=(17, 11), ex=[("뛰었음", 3), ("일직선이 아님", 3)], rep=True),
        _res("r5", "d2", 19, "16:30", "ok", "3.2", "정하늘 테크니션", sym=95, rom=52, sL=18, sR=18,
             j=J([55, 53], [38, 37], [44, 44]), ps=(16, 13), ex=[("중간에 멈춤", 3)], rep=True),
        _res("r6", "d1", 29, "15:02", "part", "28.6", "박민준 테크니션", sym=87, rom=47, sL=40, sR=36,
             j=J([64, 55], [43, 39], [51, 48]), ps=(15, 8), ex=[("다리가 가려짐", 4), ("뛰었음", 3)], rep=True),
        _res("r7", "d1", 44, "11:48", "ok", "28.9", "최지우 수의사", sym=86, rom=46, sL=39, sR=35,
             j=J([63, 54], [42, 38], [50, 47]), ps=(18, 12), ex=[("뛰었음", 6)], rep=False),
        _res("r8", "d1", 58, "09:30", "ok", "29.4", "최지우 수의사", model="v0", sym=85, rom=45, sL=39, sR=34,
             j=J([62, 53], [42, 38], [50, 47]), ps=(16, 10), ex=[("중간에 멈춤", 4), ("앉음", 2)], rep=True),
    ]
    return dogs, results


# ── 가상 환자 ──
NAMES = ["초코", "몽이", "코코", "보리", "콩이", "루이", "해피", "두부", "까미", "별이", "뭉치", "하루", "구름", "달이",
         "모카", "호두", "쿠키", "망고", "레오", "로이", "밤이", "땅콩", "사랑", "토리", "흰둥이", "누리", "봄이", "단비",
         "마루", "탄이", "순돌이", "복실이", "감자", "치즈", "라떼", "우유", "소금", "후추", "바둑이", "찰리", "맥스",
         "벨라", "루나", "코비", "아롱이", "다롱이", "은비", "금비", "또또", "깜순이", "솜이", "보미", "나비", "제리"]
SURNAMES = list("김이박최정강조윤장임한오서신권황안송류홍")
GIVEN = ["민준", "서연", "지훈", "하은", "도윤", "수아", "예준", "지우", "시우", "서윤", "주원", "하린", "지호", "채원",
         "은우", "지아", "현우", "수빈", "건우", "다은", "유진", "태윤", "가온", "나연"]
# (진단, 수술(없으면 보존 치료), 부위 후보, 체급 후보)
CONDITIONS = [
    ("앞십자인대 파열", "TPLO (경골 고원 수평화 절골술)", ["LH", "RH"], "ML"),
    ("슬개골 내측 탈구 3기", "슬개골 탈구 교정술", ["LH", "RH"], "S"),
    ("대퇴골두 무혈성 괴사", "대퇴골두 절제술 (FHO)", ["LH", "RH"], "S"),
    ("요척골 원위 골절", "골절 정복술 (플레이트 고정)", ["LF", "RF"], "SM"),
    ("고관절 이형성", "고관절 전치환술 (THR)", ["LH", "RH"], "L"),
    ("추간판 탈출증 (IVDD)", "반측 추궁 절제술", ["SP"], "SM"),
    ("팔꿈치 이형성", "관절경 내측 구상돌기 제거", ["LF", "RF"], "ML"),
    ("퇴행성 관절염", None, ["LH", "RH", "LF", "RF"], "SML"),
    ("근육 염좌", None, ["LH", "RH", "LF", "RF"], "SML"),
]
CAUTIONS = ["입질 있음, 입마개 착용 후 촬영", "심장약(피모벤단) 복용 중, 흥분 주의", "마취 위험군 (MMVD 2기)",
            "겁이 많아 보호자 동반 촬영", "반대쪽 다리로 체중 부하 피함", "진통제 알레르기 (멜록시캄)",
            "피부 봉합 부위 핥음, 넥카라 유지", "다른 개를 보면 흥분, 대기실 분리"]
PROGRESS = ["보행 시 절뚝임 줄어듦. 산책 10분 → 15분으로 늘리도록 안내", "체중 부하 비슷함. 수중 재활 주 2회 유지",
            "계단 오르내리기 아직 금지", "봉합사 제거, 상처 깨끗함", "근육량 좌우 차이 줄어듦 (허벅지 둘레 1cm 차)",
            "보호자 말로는 집에서 뛰려고 함 → 목줄 산책만 하도록 다시 안내", "진통제 종료, 통증 반응 없음"]
SUBJ = ["산책 후 절뚝임이 덜하다고 함", "아침에 일어날 때 뻣뻣해 보인다고 함", "집에서 뛰려고 해서 걱정된다고 함",
        "식욕·활력 양호", "계단 오를 때 머뭇거린다고 함"]
PLAN = ["2주 뒤 재측정", "수중 재활 주 2회 유지", "산책 시간 조금씩 늘리기", "진통제 3일 더, 다음 방문 때 통증 재평가",
        "체중 관리 식이 안내"]
HANDOFF = ["다음 측정은 오후로 (오전엔 보호자 출근)", "촬영 때 바닥 미끄러워 넘어질 뻔함. 매트 깔고 찍기",
           "천천히 걷게 간식으로 유도", "보호자가 결과 보고서 출력 요청"]
WEIGHTS = {"S": (2.5, 9.5), "M": (10, 24), "L": (25, 38)}
HR = {"S": (100, 150), "M": (80, 125), "L": (60, 100)}


def _gen_dog(rng: random.Random, i: int, recent: bool) -> tuple[Dog, list]:
    """가상 환자 한 마리와 그 회차들. recent=False 면 모든 기록이 8일 이상 전이라 '변동 있음'에 안 걸린다."""
    diag, surg, sites, sizes = rng.choice(CONDITIONS)
    size = rng.choice(sizes)
    pool = [b for b in config.BREEDS if config.auto_size(b, 0 if b != "믹스견" else 15) == size] or config.BREEDS
    breed = rng.choice(pool)
    lo, hi = WEIGHTS[size]
    kg = round(rng.uniform(lo, hi), 1)
    site = rng.choice(sites)
    stage = rng.choices(["pre", "rehab", "done"], [15, 65, 20])[0]
    if not surg and stage == "pre":
        stage = "rehab"
    floor = 0 if recent else 8              # 이 날보다 최근 기록은 만들지 않는다
    dr = rng.choice(STAFF[:3])              # 담당 수의사
    d = Dog(f"g{i:03d}", rng.choice(NAMES), breed, str(rng.randint(2012, 2024)), str(kg),
            rng.choice(list(config.SEX)), size=size, focus=site if site in config.LIMB else None,
            no=f"{rng.randint(2016, 2026)}{rng.randint(1000, 9999)}",
            owner=rng.choice(SURNAMES) + rng.choice(GIVEN), phone=f"010-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}",
            stage=stage)

    # 히스토리: 진단 → (수술) → 재활 시작 → (종결)
    if stage == "pre":
        t_diag = rng.randint(floor + 1, floor + 20)
        d.history = [History(iso(t_diag), "진단", diag, site, dr, dr)]
        d.stage_day = iso(t_diag)
        t_rehab = None
    else:
        t_diag = rng.randint(floor + 14, 400) if stage == "done" else rng.randint(floor + 7, 160)
        t_diag = max(t_diag, floor + 14 if stage == "done" else floor + 2)
        d.history = [History(iso(t_diag), "진단", diag, site, dr, dr)]
        t_rehab = t_diag
        if surg:
            t_op = max(floor + 1, t_diag - rng.randint(1, 5))
            d.history.append(History(iso(t_op), "수술", surg, site, dr, dr))
            t_rehab = max(floor, t_op - rng.randint(3, 8))
        d.history.append(History(iso(t_rehab), "재활", "재활 시작" if surg else "보존 치료 · 재활 시작", site, "", dr))
        d.rehab = iso(t_rehab)
        d.stage_day = iso(t_rehab)
        if stage == "done":
            t_end = max(floor, t_rehab - rng.randint(30, 90))
            if t_end >= t_rehab:
                d.stage = stage = "rehab"
            else:
                d.history.append(History(iso(t_end), "재활", "재활 종결 · 보행 정상 범위", site, "", dr))
                d.stage_day = iso(t_end)

    # 보행 측정: 재활 시작부터 10~20일 간격, 대칭 지수는 조금씩 오른다
    results = []
    sym = rng.randint(76, 86)
    if t_rehab is not None:
        newest = max(iso_days(d.stage_day) if stage == "done" else 0, floor)
        when, t = [], rng.randint(newest, newest + 6)       # 가장 최근 회차부터 거꾸로 날짜를 잡는다
        while t <= t_rehab and len(when) < 8:
            when.append(t)
            t += rng.randint(10, 20)
        for n, t in enumerate(reversed(when)):               # 오래된 회차부터 만든다
            st = rng.choices(["ok", "part", "fail"], [84, 10, 6])[0]
            by = rng.choice(STAFF[1:])
            w = f"{kg + rng.uniform(-0.6, 0.6):.1f}"
            if st == "fail":
                results.append(_res(new_id("res"), d.id, t, _hm(rng), "fail", w, by))
            else:
                sym = min(98, sym + rng.randint(-1, 4))
                L = rng.randint(58, 68)
                R = L - max(0, rng.randint(2, 10) - n)
                sl = rng.randint(30, 42)
                results.append(_res(new_id("res"), d.id, t, _hm(rng), st, w, by, sym=sym, rom=L - rng.randint(10, 16),
                                    sL=sl, sR=sl - rng.randint(0, 4), j=J([L, R], [L - 20, R - 20], [L - 12, L - 13]),
                                    ps=(rng.randint(14, 19), rng.randint(7, 13)), ex=[("뛰었음", rng.randint(2, 5))], rep=True))
    elif rng.random() < 0.5:                 # 수술 전 기준 측정
        t = rng.randint(floor, floor + 6)
        L = rng.randint(50, 60)
        results.append(_res(new_id("res"), d.id, t, _hm(rng), "ok", str(kg), rng.choice(STAFF[1:]), sym=sym, rom=L - 14,
                            sL=32, sR=27, j=J([L, L - 9], [L - 20, L - 26], [L - 12, L - 13]),
                            ps=(16, 9), ex=[("뛰었음", 4)], rep=True))

    # 바이탈은 방문마다 잰다: 빈 방문은 맨 끝 _fill_visit_vitals 가 채운다

    # 메모: 주의(중요) 일부, 예약·기타 몇 개
    if rng.random() < 0.35:
        t = rng.randint(floor, t_diag)
        d.notes.append(Note(new_id("note"), f"{iso(t)} {_hm(rng)}", rng.choice(STAFF), "주의", rng.choice(CAUTIONS), True))
    for _ in range(rng.randint(0, 2)):
        t = rng.randint(floor, t_diag)
        text = rng.choice(HANDOFF)
        d.notes.append(Note(new_id("note"), f"{iso(t)} {_hm(rng)}", rng.choice(STAFF), "예약" if "다음 측정" in text else "기타", text))
    # 진료 기록: 진단한 날과 측정한 날 몇 번(S·O·A·P 중 몇 칸)
    visit_days = [t_diag] + [iso_days(r.day) for r in results[-3:] if r.st != "fail"]
    for t in sorted(set(visit_days)):
        first = t == t_diag
        d.notes.extend(_soap(new_id("note"), f"{iso(t)} {_hm(rng)}", dr if first else rng.choice(STAFF[:3]), "",
                             "" if rng.random() < 0.4 else rng.choice(SUBJ),
                             rng.choice(PROGRESS) if not first else f"{diag} 소견",
                             diag if first else "", rng.choice(PLAN)))
    d.notes.sort(key=lambda n: n.at, reverse=True)
    return d, results


def iso_days(day: str) -> int:
    return (date.today() - date.fromisoformat(day)).days


def _hm(rng: random.Random) -> str:
    return f"{rng.randint(9, 18):02d}:{rng.choice(['00', '10', '20', '30', '40', '50'])}"


def _fill_visit_vitals(d: Dog, results: list, rng: random.Random) -> None:
    """방문(같은 날짜의 측정·진료 기록·진단/수술·영상)마다 바이탈을 하나씩 둔다(병원은 방문마다 잰다, 11-02).
    이미 있는 날은 그대로, 없는 날은 그 개 체중 근처 값으로 만든다. 측정자는 그날 기록한 사람."""
    have = {v.day for v in d.vitals}
    days = ({r.day: r.by for r in results if r.day} | {n.at[:10]: n.author for n in d.notes if n.cat in config.SOAP}
            | {h.day: h.by or h.author for h in d.history} | {im.day: im.author for im in d.images})
    kg = float(d.kg or 10)
    hr = HR.get(d.size or "M", HR["M"])
    for day, who in days.items():
        if day in have:
            continue
        d.vitals.append(Vital(day, f"{kg + rng.uniform(-0.6, 0.6):.1f}", f"{rng.uniform(37.9, 39.1):.1f}",
                              str(rng.randint(*hr)), str(rng.randint(118, 160)), str(rng.randint(68, 92)), who or rng.choice(STAFF[3:])))
    d.vitals.sort(key=lambda v: v.day, reverse=True)


def demo_account() -> Account:
    """데모 계정을 처음 상태로 (다시) 만든다."""
    acct = Account(id=DEMO_ID, login_id="hanbit_vet", password="demo", name="한빛동물병원",
                   loc="서울 마포구 월드컵북로", dev="PP-2410-0381", code="INST-HANBIT",
                   contract_ends=(date.today() + timedelta(days=362)).isoformat())
    dogs, results = _design_dogs()
    rng = random.Random(20261028)
    n_gen = N_DOGS - len(dogs)
    recent = set(rng.sample(range(n_gen), 8))     # 디자인 4마리 + 8마리 정도가 '변동 있음'
    for i in range(n_gen):
        d, rs = _gen_dog(rng, i + 1, i in recent)
        dogs.append(d)
        results += rs
    for d in dogs:
        d.size = d.size or config.auto_size(d.breed, d.kg)
        _fill_visit_vitals(d, [r for r in results if r.dog == d.id], rng)
    real.fill(results)   # 회차 수치는 실측 회차로 (이름·날짜·측정자는 지어낸 값)
    real.showcase(results, "d1")   # 시연: 대표 반려견은 오른쪽 뒷다리 절뚝임이 회차마다 나아지는 극단 합성(3D 와 같은 다리)
    acct.dogs = dogs
    acct.results = sorted(results, key=lambda r: (r.day, r.time), reverse=True)
    # 콩이는 로그인할 때 분석이 절반쯤 진행 중이다 (홈의 '측정 중' 표시, 끝나면 알림)
    acct.jobs = [Job(new_id("job"), "d2", 16, "", time.time() - 2.3 / 5 * config.ANALYSIS_SEC, by="정하늘 테크니션")]
    return store.add(acct)


def accounts_seed() -> None:
    """로그인 계정·디바이스 코드·크림오프 운영 기관(회원가입 명세 v0.3). 데모 기관 데이터와 따로 다시 만든다."""
    if "creamoff" not in store.accounts:
        store.add(Account(id="creamoff", login_id="", password="", name="크림오프", code="INST-CREAM", joined="2026년 10월 1일"))
        store.add_staff(Staff("s_admin", "creamoff_admin", "admin1234", "김운영", "creamoff", "ops@creamoff.example",
                              role="ADMIN", joined="2026년 10월 1일"))
        store.add_staff(Staff("s_temp", "creamoff_staff", "staff1234", "이스태프", "creamoff", "staff@creamoff.example",
                              role="STAFF", joined="2026년 10월 20일"))
    if not store.by_code(DEMO_CODE):
        store.add_code(DeviceCode("c_demo", DEMO_ID, DEMO_CODE, 3, note="1호기", created="2026-10-02"))
        store.add_code(DeviceCode("c_full", DEMO_ID, FULL_CODE, 1, note="2호기(상한 1)", created="2026-10-20"))
    if not store.by_login("hanbit_vet"):
        store.add_staff(Staff(DEMO_STAFF, "hanbit_vet", "demo1234", "정하늘", DEMO_ID, "hanbit@example.com",
                              device_code="c_demo", joined="2026년 10월 2일"))
        store.add_staff(Staff("s_full", "hanbit_desk", "demo1234", "박데스크", DEMO_ID, "desk@example.com",
                              device_code="c_full", joined="2026년 10월 21일"))
    if "expired" not in store.accounts:   # 계약이 끝난 기관: 로그인하면 GUEST 로 만료 안내
        store.add(Account(id="expired", login_id="", password="", name="소망동물병원", code="INST-SOMANG",
                          contract_ends=(date.today() - timedelta(days=3)).isoformat(), joined="2025년 10월 1일"))
        store.add_code(DeviceCode("c_exp", "expired", EXPIRED_CODE, 3, created="2025-10-01"))
        store.add_staff(Staff("s_exp", "somang_vet", "demo1234", "최소망", "expired", "somang@example.com",
                              device_code="c_exp", joined="2025년 10월 1일"))


def seed() -> None:
    if DEMO_ID not in store.accounts:
        demo_account()
    accounts_seed()
