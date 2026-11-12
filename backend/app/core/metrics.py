"""요청 수와 처리 시간 세기(15.9 `GET /metrics`, 11.8, BE-20 선택).

Prometheus 텍스트 형식(0.0.4)을 직접 쓴다. 패키지를 더하지 않으려는 것이고, 내는 지표가 셋뿐이라 그렇게 해도 짧다.
API는 프로세스 하나로 뜨므로(Dockerfile의 uvicorn) 값은 그 프로세스가 켜진 뒤의 누계다. 다시 뜨면 0부터다.

라벨에는 식별 정보를 넣지 않는다(11.8): 경로는 실제 주소가 아니라 라우트 틀(`/api/v1/dogs/{dog_id}`)이고,
라우트에 맞지 않은 요청은 모두 `unmatched` 하나로 센다. 쿼리 문자열은 보지 않는다.

Spring에 빗대면 Micrometer의 `http.server.requests` 타이머를 손으로 만든 것이다.
"""

from __future__ import annotations

import threading
from collections import defaultdict

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
UNMATCHED = "unmatched"
# 처리 시간 구간(초). 목록 조회는 0.1초 안, 영상 올리기는 몇 초가 걸려 둘 다 갈리도록 잡았다
BUCKETS: tuple[float, ...] = (0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)


def _escape(value: str) -> str:
    """라벨 값의 역슬래시·따옴표·줄바꿈을 형식대로 바꾼다."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class RequestMetrics:
    """요청 한 건마다 `observe`를 부르고, `/metrics`가 `render`로 읽는다. 스레드 여럿이 불러도 된다."""

    def __init__(self, version: str = "") -> None:
        self._version = version
        self._lock = threading.Lock()
        self._requests: dict[tuple[str, str, str], int] = defaultdict(int)
        self._buckets: dict[tuple[str, str], list[int]] = {}
        self._seconds: dict[tuple[str, str], float] = defaultdict(float)

    def observe(self, method: str, path: str, status: int, seconds: float) -> None:
        key = (method, path)
        with self._lock:
            self._requests[(method, path, str(status))] += 1
            counts = self._buckets.setdefault(key, [0] * (len(BUCKETS) + 1))
            for index, limit in enumerate(BUCKETS):
                if seconds <= limit:
                    counts[index] += 1
            counts[-1] += 1  # +Inf 칸이자 건수
            self._seconds[key] += seconds

    def render(self) -> str:
        with self._lock:
            requests = sorted(self._requests.items())
            buckets = sorted((key, list(counts)) for key, counts in self._buckets.items())
            seconds = dict(self._seconds)
        lines = [
            "# HELP app_info 서비스 버전. 값은 언제나 1이다.",
            "# TYPE app_info gauge",
            f'app_info{{version="{_escape(self._version)}"}} 1',
            "# HELP http_requests_total 처리한 요청 수(메서드, 라우트 틀, 상태 코드별).",
            "# TYPE http_requests_total counter",
        ]
        for (method, path, status), count in requests:
            lines.append(
                f'http_requests_total{{method="{_escape(method)}",path="{_escape(path)}",status="{status}"}} {count}'
            )
        lines += [
            "# HELP http_request_duration_seconds 요청 처리 시간(초, 메서드와 라우트 틀별).",
            "# TYPE http_request_duration_seconds histogram",
        ]
        for (method, path), counts in buckets:
            labels = f'method="{_escape(method)}",path="{_escape(path)}"'
            for limit, count in zip(BUCKETS, counts, strict=False):
                lines.append(f'http_request_duration_seconds_bucket{{{labels},le="{limit:g}"}} {count}')
            lines.append(f'http_request_duration_seconds_bucket{{{labels},le="+Inf"}} {counts[-1]}')
            lines.append(f"http_request_duration_seconds_sum{{{labels}}} {seconds[(method, path)]:.6f}")
            lines.append(f"http_request_duration_seconds_count{{{labels}}} {counts[-1]}")
        return "\n".join(lines) + "\n"
