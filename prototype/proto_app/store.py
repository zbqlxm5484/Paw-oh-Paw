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
class History:
    """진단·수술·재활 단계 변경 한 건 (히스토리 탭, 홈 특이사항 배지)."""
    day: str                  # YYYY-MM-DD
    kind: str                 # 진단 | 수술 | 재활
    title: str                # 예) 앞십자인대 파열 · TPLO
    site: str = ""            # LF | RF | LH | RH | SP(척추) | ""
    by: str = ""              # 집도의·진단의
    author: str = ""          # 기록한 사람


@dataclass
class Vital:
    """방문 한 번의 바이탈. 빈 값은 그날 재지 않은 것."""
    day: str                  # YYYY-MM-DD
    kg: str = ""
    temp: str = ""            # 체온 ℃
    hr: str = ""              # 심박 bpm
    sbp: str = ""             # 수축기 혈압 mmHg
    dbp: str = ""             # 이완기 혈압 mmHg
    author: str = ""


@dataclass
class Note:
    """동물 메모(차팅). 지우지 않고, 고치면 이전 내용을 revs 에 남긴다."""
    id: str
    at: str                   # YYYY-MM-DD HH:MM
    author: str
    cat: str                  # 경과 | 특이사항 | 처치 | 전달
    text: str
    important: bool = False   # 홈 특이사항 배지에 올린다
    revs: list = field(default_factory=list)   # [(at, author, text)] 오래된 것부터
    rid: str = ""             # 회차 메모면 그 회차 id, 반려견 메모면 빈 값


@dataclass
class Image:
    """방사선·사진 한 장."""
    id: str
    day: str                  # YYYY-MM-DD 촬영일
    kind: str                 # pre | post | photo
    caption: str
    path: str
    author: str = ""


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
    no: str = ""              # 동물번호 (병원 차트 번호)
    owner: str = ""           # 보호자 이름
    phone: str = ""           # 보호자 연락처
    stage: str = "rehab"      # pre(수술 전) | rehab(재활 중) | done(종결)
    stage_day: str = ""       # 단계가 바뀐 날 YYYY-MM-DD
    history: list = field(default_factory=list)   # [History] 오래된 것부터
    vitals: list = field(default_factory=list)    # [Vital] 최신이 앞
    notes: list = field(default_factory=list)     # [Note] 최신이 앞
    images: list = field(default_factory=list)    # [Image] 최신이 앞
    version: int = 0          # 다른 담당자가 먼저 고쳤는지 확인(낙관적 잠금)


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
    day: str = ""             # YYYY-MM-DD (변동 판정·시간 축용. date 는 화면용 "10월 15일")
    by: str = ""              # 측정한 사람
    m: dict = field(default_factory=dict)   # 실측 수치 {다리: {코드: 값}} (real.py). 비어 있으면 예전 예시 공식
    src: str = ""             # 수치를 가져온 실측 회차 (출처:촬영 묶음)


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
    by: str = ""              # 측정한 사람

    def progress(self) -> float:
        return min(5.0, (time.time() - self.started) / config.ANALYSIS_SEC * 5)


CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # 혼동되는 0·O·1·I·L 제외 (회원가입 명세 v0.3 2절)


def norm_code(raw: str) -> str:
    """디바이스 코드 입력 정리: 하이픈·공백 제거, 대문자. 형식이 틀리면 빈 문자열."""
    c = "".join(ch for ch in (raw or "").upper() if ch not in "- ")
    return c if len(c) == 20 and all(ch in CODE_CHARS for ch in c) else ""


def show_code(c: str) -> str:
    return "-".join(c[i:i + 5] for i in range(0, 20, 5))


@dataclass
class DeviceCode:
    """크림오프가 기관에 발급하는 가입용 코드. 가입 때만 쓴다."""
    id: str
    inst: str                 # 기관(Account) id
    code: str                 # 20자, 하이픈 없이
    max_accounts: int = 3
    revoked: bool = False
    note: str = ""
    created: str = ""


@dataclass
class Staff:
    """로그인 계정. ADMIN·STAFF = 크림오프, CLIENT = 기관 담당자(가입으로 생김). GUEST 는 저장하지 않고 계산한다."""
    id: str
    login_id: str
    password: str
    name: str
    inst: str                 # 기관(Account) id
    email: str = ""
    role: str = "CLIENT"
    active: bool = True
    device_code: str = ""     # 가입에 쓴 DeviceCode id
    joined: str = ""
    reset_token: str = ""
    reset_until: float = 0.0


@dataclass
class Account:
    """기관. 반려견·회차·작업은 기관 소유라 같은 기관 담당자는 모두 함께 본다."""
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
    code: str = ""                       # 기관 식별 코드 (관리 화면 표시용)
    contract_ends: Optional[str] = None  # YYYY-MM-DD, 당일 포함. None = 기한 없음

    def contract_status(self) -> str:
        return "EXPIRED" if self.contract_ends and self.contract_ends < date.today().isoformat() else "ACTIVE"

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
        self.accounts: dict[str, Account] = {}   # 기관
        self.staff: dict[str, Staff] = {}        # 로그인 계정
        self.codes: dict[str, DeviceCode] = {}

    def get(self, acct_id) -> Optional[Account]:
        return self.accounts.get(acct_id or "")

    def add(self, acct: Account) -> Account:
        self.accounts[acct.id] = acct
        return acct

    def by_login(self, login_id: str) -> Optional[Staff]:
        return next((s for s in self.staff.values() if s.login_id == login_id), None)

    def add_staff(self, s: Staff) -> Staff:
        self.staff[s.id] = s
        return s

    def staff_of(self, inst_id: str) -> list:
        return [s for s in self.staff.values() if s.inst == inst_id]

    def add_code(self, c: DeviceCode) -> DeviceCode:
        self.codes[c.id] = c
        return c

    def codes_of(self, inst_id: str) -> list:
        return [c for c in self.codes.values() if c.inst == inst_id]

    def by_code(self, code: str) -> Optional[DeviceCode]:
        return next((c for c in self.codes.values() if c.code == code), None)

    def active_count(self, code_id: str) -> int:
        return sum(1 for s in self.staff.values() if s.device_code == code_id and s.active)

    def effective_role(self, s: Staff) -> str:
        acct = self.get(s.inst)
        if s.role == "CLIENT" and acct and acct.contract_status() == "EXPIRED":
            return "GUEST"
        return s.role


store = Store()
