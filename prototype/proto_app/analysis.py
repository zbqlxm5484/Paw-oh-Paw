"""분석 작업 흉내.

실서비스: 업로드 → 분석 API(관절점 추출 · 유효 판별 · 보행 수치) → 회차 결과 저장.
여기서는 시작 시각으로 진행률을 계산하고, 끝나면 직전 회차를 바탕으로 결과를 만든다 (디자인의 finishAna).
"""

from __future__ import annotations

import time
from datetime import datetime

from . import config
from .seed import J
from .store import Account, Job, Result, kdate, new_id


def start_job(acct: Account, dog_id: str, n: int, weight: str, videos: list) -> Job:
    job = Job(new_id("job"), dog_id, n, weight, time.time(), videos=videos)
    acct.jobs.append(job)
    return job


def finish_due_jobs(acct: Account) -> list:
    """진행이 끝난 작업을 결과로 바꾼다. 새로 끝난 작업 목록을 돌려준다."""
    done = []
    for job in acct.active_jobs():
        if job.progress() >= 5:
            job.result_id = _make_result(acct, job).id
            done.append(job)
    return done


def _make_result(acct: Account, job: Job) -> Result:
    dog = acct.dog(job.dog)
    prev = next((r for r in acct.results if r.dog == job.dog and r.st != "fail"), None)
    if prev:
        b_sym, b_rom, b_sL, b_sR, b_j = prev.sym, prev.rom, prev.sL, prev.sR, prev.j
    else:
        b_sym, b_rom, b_sL, b_sR, b_j = 88, 46, 30, 28, J([60, 55], [42, 39], [50, 48])
    n = job.n or config.MAX_SHOTS
    meas = round(n * 1.1)
    used = round(meas * 0.68)
    exc = meas - used
    ex = [(name, c) for name, c in (("뛰었음", -(-exc // 2)), ("중간에 멈춤", exc // 2)) if c > 0]
    r = Result(
        id=new_id("res"), dog=job.dog, date=kdate(), time=datetime.now().strftime("%H:%M"), st="ok",
        w=job.w or (dog.kg if dog and dog.kg else "-"),
        sym=min(98, b_sym + 2), rom=b_rom + 1, sL=b_sL, sR=min(b_sL, b_sR + 1),
        j=[[nm, left, min(left, right + 2)] for nm, left, right in b_j],
        ps=(meas, used), ex=ex, rep=True, videos=job.videos,
    )
    acct.results.insert(0, r)
    return r
