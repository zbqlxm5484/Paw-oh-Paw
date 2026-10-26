"""데모 기관(한빛동물병원)의 예시 데이터. 디자인의 DOGS · RES와 같은 값이다."""

from __future__ import annotations

import time

from . import config
from .store import Account, Dog, Job, Result, new_id, store

DEMO_ID = "demo"


def J(a, b, c):
    return [["무릎", a[0], a[1]], ["고관절", b[0], b[1]], ["팔꿈치", c[0], c[1]]]


def demo_account() -> Account:
    """데모 계정을 처음 상태로 (다시) 만든다."""
    acct = Account(id=DEMO_ID, login_id="hanbit_vet", password="demo", name="한빛동물병원",
                   loc="서울 마포구 월드컵북로", dev="PP-2410-0381")
    acct.dogs = [
        Dog("d1", "보리", "골든 리트리버", "2019", "28.4", "fs", rehab="2026-08-18", focus="RH",
            memo="TPLO 수술 후 재활 9주차. 오른뒤 체중 부하 관찰 중"),
        Dog("d2", "콩이", "말티즈", "2022", "3.2", "f"),
        Dog("d3", "두부", "비글", "2021", "11.2", "mn", rehab="2026-10-01", focus="LF"),
        Dog("d4", "탄이", "진돗개", "2017", "19.8", "m"),
    ]
    for d in acct.dogs:
        d.size = config.auto_size(d.breed, d.kg)
    acct.results = [
        Result("r2", "d3", "10월 15일", "17:40", "part", "11.0", sym=84, rom=44, sL=30, sR=27,
               j=J([58, 49], [40, 36], [47, 45]), ps=(14, 7), ex=[("다리가 가려짐", 4), ("뛰었음", 3)], rep=True),
        Result("r3", "d4", "10월 15일", "11:05", "fail", "19.6"),
        Result("r1", "d1", "10월 14일", "14:20", "ok", "28.1", sym=92, rom=48, sL=41, sR=38,
               j=J([66, 58], [44, 41], [52, 50]), ps=(18, 12), ex=[("뛰었음", 4), ("중간에 멈춤", 2)], rep=True),
        Result("r4", "d1", "10월 1일", "10:12", "ok", "28.3", sym=88, rom=48, sL=40, sR=37,
               j=J([65, 56], [43, 40], [51, 49]), ps=(17, 11), ex=[("뛰었음", 3), ("일직선이 아님", 3)], rep=True),
        Result("r5", "d2", "9월 28일", "16:30", "ok", "3.2", sym=95, rom=52, sL=18, sR=18,
               j=J([55, 53], [38, 37], [44, 44]), ps=(16, 13), ex=[("중간에 멈춤", 3)], rep=True),
        Result("r6", "d1", "9월 18일", "15:02", "part", "28.6", sym=87, rom=47, sL=40, sR=36,
               j=J([64, 55], [43, 39], [51, 48]), ps=(15, 8), ex=[("다리가 가려짐", 4), ("뛰었음", 3)], rep=True),
        Result("r7", "d1", "9월 3일", "11:48", "ok", "28.9", sym=86, rom=46, sL=39, sR=35,
               j=J([63, 54], [42, 38], [50, 47]), ps=(18, 12), ex=[("뛰었음", 6)], rep=False),
        Result("r8", "d1", "8월 20일", "09:30", "ok", "29.4", model="v0", sym=85, rom=45, sL=39, sR=34,
               j=J([62, 53], [42, 38], [50, 47]), ps=(16, 10), ex=[("중간에 멈춤", 4), ("앉음", 2)], rep=True),
    ]
    # 콩이는 로그인할 때 분석이 절반쯤 진행 중이다 (홈의 '측정 중' 표시, 끝나면 알림)
    acct.jobs = [Job(new_id("job"), "d2", 16, "", time.time() - 2.3 / 5 * config.ANALYSIS_SEC)]
    return store.add(acct)


def seed() -> None:
    if DEMO_ID not in store.accounts:
        demo_account()
