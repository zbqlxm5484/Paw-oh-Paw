"""담당자 스냅샷 캐시 (명세 11.6 인증 캐시).

요청마다 읽던 담당자 행을 프로세스 메모리에 AUTH_CACHE_TTL_SEC(기본 60초) 동안 둔다. 인증의 DB 왕복이 0이 된다.
11.3 "프로세스 메모리에 상태를 두지 않는다"의 유일한 예외다. DB 값의 늦은 사본일 뿐이라 어느 프로세스에서 읽어도
같은 답이 나오고, 지워져도 다시 읽으면 된다. 프로세스 사이에서 공유해야 하면 이 모듈만 Redis로 바꾼다(3절).
대가: 계정 중지·계약 만료·역할 변경이 최대 TTL만큼 늦게 반영된다(10절 Q28). 토큰 만료는 캐시와 상관없이 즉시다.
비밀번호를 바꾼 뒤 옛 토큰을 끊는 것도 다른 프로세스에서는 최대 TTL만큼 늦다(v1.48).

Spring에 빗대면 UserDetails를 Caffeine 캐시에 두고, isAccountNonExpired()는 꺼낼 때마다 평가하는 것이다.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from app.core.config import get_settings
from app.core.dates import contract_status as compute_contract_status
from app.models.enums import ContractStatus, EffectiveRole, StaffRole

# 이보다 많아지면 넣을 때 만료분을 모두 치운다. 담당자 수는 기관 수 × 10 이하라 보통 닿지 않는다
MAX_ENTRIES = 1000


def _now() -> float:
    """단조 시계(초). 테스트가 이 함수를 바꿔 끼워 시간을 흘린다."""
    return time.monotonic()


@dataclass(frozen=True)
class AuthStaff:
    """로그인한 담당자 스냅샷. ORM 객체가 아니라 DB 세션이 닫힌 뒤에도 쓴다. CurrentStaff의 타입이다(11.6).

    라우트·서비스는 id·institution_id·role만 쓰므로 Staff(ORM)를 받던 코드가 그대로 돈다.
    """

    id: uuid.UUID
    institution_id: uuid.UUID
    login_id: str
    name: str
    email: str | None
    role: str
    is_active: bool
    institution_code: str
    institution_name: str
    contract_ends_at: date | None
    notif_on: bool = True
    # 비밀번호를 마지막으로 바꾼 시각(12.5, v1.48). 이보다 먼저 받은 토큰은 get_current_staff가 돌려보낸다
    password_changed_at: datetime | None = None

    @property
    def contract_status(self) -> str:
        """계약 상태(11.6). 계산은 core/dates.contract_status 하나다(관리자 API도 같은 것을 쓴다)."""
        return compute_contract_status(self.contract_ends_at)

    @property
    def effective_role(self) -> str:
        """유효 역할(11.6). 계약이 끝난 CLIENT만 GUEST. 크림오프 쪽(ADMIN·STAFF)은 계약을 보지 않는다."""
        if self.role == StaffRole.CLIENT and self.contract_status == ContractStatus.EXPIRED:
            return EffectiveRole.GUEST
        return self.role


class AuthCache:
    """dict + Lock. 항목은 (만료 시각, 스냅샷). TTL이 0이면 아무것도 넣지 않는다(요청마다 DB)."""

    def __init__(self) -> None:
        self._entries: dict[uuid.UUID, tuple[float, AuthStaff]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def ttl() -> int:
        return get_settings().AUTH_CACHE_TTL_SEC

    def get(self, staff_id: uuid.UUID) -> AuthStaff | None:
        """스냅샷. 없거나 지났으면 None(지난 항목은 버린다)."""
        if self.ttl() <= 0:
            return None
        now = _now()
        with self._lock:
            entry = self._entries.get(staff_id)
            if entry is None:
                return None
            expires_at, snapshot = entry
            if expires_at <= now:
                del self._entries[staff_id]
                return None
            return snapshot

    def put(self, snapshot: AuthStaff) -> None:
        ttl = self.ttl()
        if ttl <= 0:
            return
        now = _now()
        with self._lock:
            if len(self._entries) >= MAX_ENTRIES:
                self._entries = {key: value for key, value in self._entries.items() if value[0] > now}
            self._entries[snapshot.id] = (now + ttl, snapshot)

    def invalidate(self, staff_id: uuid.UUID) -> None:
        """담당자를 바꾼 API가 부른다(11.6 무효화)."""
        with self._lock:
            self._entries.pop(staff_id, None)

    def invalidate_institution(self, institution_id: uuid.UUID) -> None:
        """기관(계약 종료일)을 바꾼 API가 부른다. 그 기관의 담당자 전부."""
        with self._lock:
            self._entries = {
                key: value for key, value in self._entries.items() if value[1].institution_id != institution_id
            }

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


auth_cache = AuthCache()
