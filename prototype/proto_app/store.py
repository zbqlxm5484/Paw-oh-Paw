"""메모리 저장소. 서버를 다시 켜면 예시 데이터로 돌아간다.

계정(기관)마다 반려견·회차 결과·분석 작업을 따로 가진다.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from . import config

_seq = itertools.count(1)


def new_id(prefix: str) -> str:
    return f"{prefix}{next(_seq)}"


def kdate(d: Optional[date] = None) -> str:
    d = d or date.today()
    return f"{d.month}월 {d.day}일"


@dataclass
class Dog:
    id: str
    name: str
    breed: str = ""
    birth: str = ""
    kg: str = ""
    sex: str = "m"
    size: str = ""            # S | M | L
    size_manual: bool = False
    rehab: str = ""           # YYYY-MM-DD
    focus: Optional[str] = None  # LF | RF | LH | RH
    memo: str = ""
    base: Optional[str] = None   # 직접 지정한 기준 회차 id


@dataclass
class Result:
    """회차 결과 하나. j는 [이름, 왼, 오] 3개(무릎·고관절·팔꿈치 가동 범위)."""
    id: str
    dog: str
    date: str
    time: str
    st: str                   # ok | part | fail
    w: str
    model: str = config.MODEL
    sym: int = 0
    rom: int = 0
    sL: int = 0
    sR: int = 0
    j: list = field(default_factory=list)
    ps: tuple = (0, 0)        # (측정한 통과, 사용한 통과)
    ex: list = field(default_factory=list)  # [(제외 사유, 횟수)]
    rep: bool = False
    videos: list = field(default_factory=list)


@dataclass
class Job:
    """분석 작업. 시작 시각으로 진행률을 계산한다 (0~5 단계)."""
    id: str
    dog: str
    n: int
    w: str
    started: float
    videos: list = field(default_factory=list)
    result_id: Optional[str] = None
    notified: bool = False

    def progress(self) -> float:
        return min(5.0, (time.time() - self.started) / config.ANALYSIS_SEC * 5)


@dataclass
class Account:
    id: str
    login_id: str
    password: str
    name: str
    loc: str = "-"
    dev: str = "-"
    joined: str = "2026년 10월 2일"
    dogs: list = field(default_factory=list)
    results: list = field(default_factory=list)   # 최신 회차가 앞
    jobs: list = field(default_factory=list)
    notif_on: bool = True

    def dog(self, dog_id) -> Optional[Dog]:
        return next((d for d in self.dogs if d.id == dog_id), None)

    def result(self, rid) -> Optional[Result]:
        return next((r for r in self.results if r.id == rid), None)

    def job(self, jid) -> Optional[Job]:
        return next((j for j in self.jobs if j.id == jid), None)

    def active_jobs(self) -> list:
        return [j for j in self.jobs if j.result_id is None]


class Store:
    def __init__(self) -> None:
        self.accounts: dict[str, Account] = {}

    def get(self, acct_id) -> Optional[Account]:
        return self.accounts.get(acct_id or "")

    def by_login(self, login_id: str) -> Optional[Account]:
        return next((a for a in self.accounts.values() if a.login_id == login_id), None)

    def add(self, acct: Account) -> Account:
        self.accounts[acct.id] = acct
        return acct


store = Store()
