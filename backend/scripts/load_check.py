"""동시 처리 점검(S15P31A404-274). 떠 있는 API·워커에 여러 계정으로 동시에 요청을 보내고 결과를 센다.

backend 폴더에서 실행한다. API와 워커는 미리 띄워 둔다(같은 .env, 분석 API는 mock이어도 된다).

    python -m scripts.load_check --base-url http://127.0.0.1:8000 --video <영상> [--big-video <큰 영상>] [--out <json>]

- 시험 전용 DB에서만 돌린다. 기관·계정·반려견·회차를 만들고 지우지 않는다. 팀 서버에는 돌리지 않는다.
- 계정은 DB에 직접 만든다(scripts.seed.create_account). 비밀번호는 실행할 때마다 새로 만들고 어디에도 찍지 않는다.
- 세 가지를 본다.
  1. 흐름: 기관 여럿의 담당자가 동시에 반려견 등록 → 회차 시작 → 촬영 올리기 → 분석 대기 → 측정 종료 → 보고서 받기.
     그동안 다른 스레드가 목록 조회를 계속 보내고, DB에서 분석 중인 촬영 수(전체·기관별)를 0.5초마다 센다.
  2. 경합: 같은 회차·같은 반려견에 같은 요청을 동시에 보낸다(올리기, 회차 시작, 측정 종료, 반려견 수정, 바이탈, 취소).
  3. 몰림: 조회 요청과 큰 영상 올리기를 한꺼번에 보낸다(DB 연결 수보다 많이).
- 끝나면 DB에서 어긋난 것을 센다(겹친 촬영 순번, 멈춘 촬영·회차, 보고서 수).
"""

from __future__ import annotations

import argparse
import json
import random
import secrets
import statistics
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text

from app.core.db import SessionLocal
from scripts.seed import create_account

API = "/api/v1"
IN_FLIGHT = ("SUBMITTED", "ANALYZING")
SHOT_END = ("DONE", "FAILED")
SESSION_END = ("DONE", "FAILED")
REPORT_END = ("DONE", "FAILED")


@dataclass
class Recorder:
    """요청마다 (이름, 상태 코드, 오류 코드, ms)를 적는다. 스레드 여럿이 함께 쓴다."""

    rows: list[tuple[str, int, str, float]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, name: str, status: int, code: str, ms: float) -> None:
        with self.lock:
            self.rows.append((name, status, code, ms))

    def summary(self) -> dict[str, Any]:
        groups: dict[str, list[tuple[int, str, float]]] = defaultdict(list)
        for name, status, code, ms in self.rows:
            groups[name].append((status, code, ms))
        out = {}
        for name, items in sorted(groups.items()):
            times = sorted(ms for _, _, ms in items)
            out[name] = {
                "n": len(items),
                "status": dict(Counter(f"{status}{' ' + code if code else ''}" for status, code, _ in items)),
                "p50_ms": round(statistics.median(times)),
                "p95_ms": round(times[min(len(times) - 1, int(len(times) * 0.95))]),
                "max_ms": round(times[-1]),
            }
        return out


def error_code(body: Any) -> str:
    """오류 응답 {"error": {"code": ...}}의 코드. 모양이 다르면 빈 글자."""
    error = body.get("error") if isinstance(body, dict) else None
    return str(error.get("code", "")) if isinstance(error, dict) else ""


class Api:
    """담당자 한 명의 요청. 실패(연결 오류·시간 초과)는 상태 0으로 적는다."""

    def __init__(self, base_url: str, recorder: Recorder, token: str = "") -> None:
        self.client = httpx.Client(base_url=base_url, timeout=120)
        self.recorder = recorder
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    def call(self, name: str, method: str, path: str, **kwargs: Any) -> tuple[int, Any]:
        started = time.perf_counter()
        try:
            response = self.client.request(method, API + path, headers=self.headers, **kwargs)
        except httpx.HTTPError as error:
            self.recorder.add(name, 0, type(error).__name__, (time.perf_counter() - started) * 1000)
            return 0, None
        body: Any = None
        if response.headers.get("content-type", "").startswith("application/json"):
            body = response.json()
        code = error_code(body) if response.status_code >= 400 else ""
        self.recorder.add(name, response.status_code, code, (time.perf_counter() - started) * 1000)
        return response.status_code, body

    def raw(self, name: str, url: str) -> int:
        """서명 주소(파일 내려받기). 주소가 /api/v1로 시작하므로 그대로 부른다."""
        started = time.perf_counter()
        try:
            response = self.client.get(url, headers=self.headers)
        except httpx.HTTPError as error:
            self.recorder.add(name, 0, type(error).__name__, (time.perf_counter() - started) * 1000)
            return 0
        self.recorder.add(name, response.status_code, "", (time.perf_counter() - started) * 1000)
        return response.status_code


def make_accounts(run: str, institutions: int, staff: int) -> tuple[list[list[str]], str]:
    """기관 × 담당자 계정을 만들고 (기관별 아이디 목록, 비밀번호)를 돌려준다."""
    password = "Lc-" + secrets.token_urlsafe(12)
    logins: list[list[str]] = []
    with SessionLocal() as db:
        for i in range(institutions):
            ids = []
            for s in range(staff):
                login_id = f"load-{run}-{i}-{s}"
                create_account(
                    db,
                    institution_code=f"L{run}{i}"[:20],
                    institution_name=f"부하 시험 {run} {i}",
                    login_id=login_id,
                    name=f"담당 {i}-{s}",
                    password=password,
                )
                ids.append(login_id)
            logins.append(ids)
        db.commit()
    return logins, password


def login(base_url: str, recorder: Recorder, login_id: str, password: str) -> Api:
    api = Api(base_url, recorder)
    status, body = api.call("login", "POST", "/auth/login", json={"login_id": login_id, "password": password})
    if status != 200:
        raise SystemExit(f"로그인 실패: {status}")
    return Api(base_url, recorder, body["access_token"])


def upload(api: Api, name: str, session_id: str, video: bytes) -> tuple[int, Any]:
    return api.call(name, "POST", f"/sessions/{session_id}/shots", files={"file": ("walk.mp4", video, "video/mp4")})


def new_dog(api: Api, label: str) -> dict[str, Any]:
    status, body = api.call("dog create", "POST", "/dogs", json={"name": label, "breed": "말티즈", "weight_kg": 4.2})
    if status != 201:
        raise RuntimeError(f"반려견 등록 실패 {status}")
    return body


def wait_until(deadline: float, step: float, check) -> bool:
    while time.time() < deadline:
        if check():
            return True
        time.sleep(step)
    return False


# ---- 1. 흐름 ----


def user_flow(api: Api, label: str, video: bytes, shots: int, result: dict[str, Any]) -> None:
    """담당자 한 명의 한 회차. 걸린 시간과 끝 상태를 result에 적는다."""
    started = time.time()
    dog = new_dog(api, label)
    status, session = api.call("session start", "POST", f"/dogs/{dog['id']}/sessions", json={})
    if status != 201:
        result[label] = {"error": f"session start {status}"}
        return
    sid = session["id"]
    for _ in range(shots):
        upload(api, "shot upload", sid, video)
    state: dict[str, Any] = {}

    def shots_done() -> bool:
        code, body = api.call("session poll", "GET", f"/sessions/{sid}")
        state["shots"] = [shot["status"] for shot in (body or {}).get("shots", [])] if code == 200 else []
        return bool(state["shots"]) and all(s in SHOT_END for s in state["shots"])

    analysed = wait_until(time.time() + 600, 1.0, shots_done)
    analysed_at = time.time()
    api.call("session complete", "POST", f"/sessions/{sid}/complete")

    def session_done() -> bool:
        code, body = api.call("session poll", "GET", f"/sessions/{sid}")
        state["session"] = (body or {}).get("status") if code == 200 else None
        return state["session"] in SESSION_END

    aggregated = wait_until(time.time() + 120, 1.0, session_done)
    aggregated_at = time.time()

    def reports_done() -> bool:
        code, body = api.call("reports poll", "GET", f"/sessions/{sid}/reports")
        state["reports"] = (body or {}).get("reports", []) if code == 200 else []
        return len(state["reports"]) == 2 and all(r["status"] in REPORT_END for r in state["reports"])

    reported = wait_until(time.time() + 300, 1.0, reports_done)
    files = [api.raw("report file", r["file_url"]) for r in state.get("reports", []) if r.get("file_url")]
    api.call("session result", "GET", f"/sessions/{sid}/result")
    result[label] = {
        "shots": dict(Counter(state.get("shots", []))),
        "analysed": analysed,
        "session": state.get("session") if aggregated else "TIMEOUT",
        "reports": [r["status"] for r in state.get("reports", [])] if reported else "TIMEOUT",
        "report_files": files,
        "sec_to_analysed": round(analysed_at - started, 1),
        "sec_to_reports": round(time.time() - aggregated_at, 1),
        "sec_total": round(time.time() - started, 1),
    }


def reader(api: Api, stop: threading.Event) -> None:
    """목록 조회를 쉬지 않고 보낸다. 화면이 떠 있는 다른 담당자 흉내다."""
    while not stop.is_set():
        status, body = api.call("dogs list", "GET", "/dogs", params={"size": 20})
        api.call("sessions list", "GET", "/sessions", params={"size": 20})
        items = (body or {}).get("items", []) if status == 200 else []
        if items:
            dog_id = random.choice(items)["id"]
            api.call("dog sessions", "GET", f"/dogs/{dog_id}/sessions")
            api.call("dog detail", "GET", f"/dogs/{dog_id}")
        time.sleep(0.1)


def monitor(stop: threading.Event, peaks: dict[str, int]) -> None:
    """분석 중(SUBMITTED·ANALYZING)인 촬영을 0.5초마다 세어 전체와 기관별 최댓값을 적는다."""
    query = text(
        "SELECT d.institution_id, count(*) FROM shot s JOIN measure_session m ON m.id = s.session_id "
        "JOIN dog d ON d.id = m.dog_id WHERE s.status IN ('SUBMITTED', 'ANALYZING') GROUP BY 1"
    )
    while not stop.is_set():
        with SessionLocal() as db:
            counts = [count for _, count in db.execute(query)]
        peaks["global"] = max(peaks.get("global", 0), sum(counts))
        peaks["institution"] = max(peaks.get("institution", 0), max(counts, default=0))
        peaks["samples"] = peaks.get("samples", 0) + 1
        time.sleep(0.5)


def run_flow(apis: list[list[Api]], video: bytes, shots: int, readers: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    peaks: dict[str, int] = {}
    stop = threading.Event()
    side = [threading.Thread(target=monitor, args=(stop, peaks), daemon=True)]
    flat = [api for group in apis for api in group]
    side += [threading.Thread(target=reader, args=(flat[i % len(flat)], stop), daemon=True) for i in range(readers)]
    for thread in side:
        thread.start()
    started = time.time()
    with ThreadPoolExecutor(max_workers=len(flat)) as pool:
        for i, group in enumerate(apis):
            for s, api in enumerate(group):
                pool.submit(user_flow, api, f"u{i}-{s}", video, shots, result)
    stop.set()
    for thread in side:
        thread.join(timeout=5)
    return {"users": result, "in_flight_peak": peaks, "sec": round(time.time() - started, 1)}


# ---- 2. 경합 ----


def together(count: int, work) -> list[Any]:
    """work(i)를 count개 스레드에서 같은 순간에 시작한다."""
    gate = threading.Barrier(count)

    def run(i: int) -> Any:
        gate.wait()
        return work(i)

    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(run, range(count)))


def statuses(results: list[tuple[int, Any]]) -> dict[str, int]:
    return dict(Counter(f"{s} {error_code(b)}".strip() if s >= 400 else str(s) for s, b in results))


def run_races(apis: list[Api], video: bytes, n: int = 8) -> dict[str, Any]:
    """같은 기관의 담당자들이 같은 자료에 같은 요청을 동시에 보낸다. apis는 한 기관의 담당자들이다."""
    out: dict[str, Any] = {}
    pick = lambda i: apis[i % len(apis)]  # noqa: E731

    dog = new_dog(apis[0], "race-start")
    out["session start x%d (하나만 201)" % n] = statuses(
        together(n, lambda i: pick(i).call("race session start", "POST", f"/dogs/{dog['id']}/sessions", json={}))
    )
    _, sessions = apis[0].call("dog sessions", "GET", f"/dogs/{dog['id']}/sessions")
    sid = next(item["id"] for item in sessions["items"] if item["status"] == "MEASURING")

    results = together(n, lambda i: upload(pick(i), "race upload", sid, video))
    seqs = sorted(body["shot"]["seq_no"] if "shot" in body else body["seq_no"] for s, body in results if s == 201)
    out["upload x%d (모두 201, 순번 1..%d)" % (n, n)] = {"status": statuses(results), "seq_no": seqs}

    def all_done() -> bool:
        _, body = apis[0].call("session poll", "GET", f"/sessions/{sid}")
        return all(shot["status"] in SHOT_END for shot in body["shots"])

    wait_until(time.time() + 300, 1.0, all_done)
    _, detail = apis[0].call("session poll", "GET", f"/sessions/{sid}")
    victim = detail["shots"][0]["id"]
    mixed = together(
        n,
        lambda i: pick(i).call("race shot delete", "DELETE", f"/shots/{victim}")
        if i % 2
        else pick(i).call("race complete", "POST", f"/sessions/{sid}/complete"),
    )
    out["shot delete + complete x%d (5xx 없음)" % n] = statuses(mixed)

    dog2 = new_dog(apis[0], "race-patch")
    out["dog patch x%d 같은 version (하나만 200)" % n] = statuses(
        together(
            n,
            lambda i: pick(i).call(
                "race dog patch", "PATCH", f"/dogs/{dog2['id']}", json={"name": f"r{i}", "version": dog2["version"]}
            ),
        )
    )
    day = time.strftime("%Y-%m-%d")
    out["vital put x%d 같은 날 (5xx 없음)" % n] = statuses(
        together(
            n,
            lambda i: pick(i).call(
                "race vital put", "PUT", f"/dogs/{dog2['id']}/vitals/{day}", json={"heart_rate": 80 + i}
            ),
        )
    )
    _, vitals = apis[0].call("vitals list", "GET", f"/dogs/{dog2['id']}/vitals")
    out["vital rows for the day"] = len([v for v in vitals.get("items", vitals) if v.get("measured_on") == day])

    _, session2 = apis[0].call("session start", "POST", f"/dogs/{dog2['id']}/sessions", json={})
    sid2 = session2["id"]
    upload(apis[0], "shot upload", sid2, video)
    mixed = together(
        n,
        lambda i: pick(i).call("race cancel", "DELETE", f"/sessions/{sid2}")
        if i == 0
        else upload(pick(i), "race upload vs cancel", sid2, video),
    )
    out["upload + cancel x%d (5xx 없음)" % n] = statuses(mixed)
    for _ in range(40):  # 취소가 분석 중이라 409였으면 끝난 뒤 한 번 더 지운다
        status, _ = apis[0].call("race cancel retry", "DELETE", f"/sessions/{sid2}")
        if status != 409:
            break
        time.sleep(1)
    out["cancel 뒤 회차"] = apis[0].call("session poll", "GET", f"/sessions/{sid2}")[0]
    return out


# ---- 3. 몰림 ----


def run_burst(flat: list[Api], video: bytes, big: bytes | None, readers: int, uploads: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    started = time.time()
    results = together(
        readers, lambda i: flat[i % len(flat)].call("burst dogs list", "GET", "/dogs", params={"size": 20})
    )
    out[f"dogs list x{readers}"] = {"status": statuses(results), "sec": round(time.time() - started, 2)}
    if big is None:
        return out
    sessions = []
    for i in range(uploads):
        api = flat[i % len(flat)]
        dog = new_dog(api, f"burst-{i}")
        _, session = api.call("session start", "POST", f"/dogs/{dog['id']}/sessions", json={})
        sessions.append((api, session["id"]))
    started = time.time()

    def work(i: int) -> tuple[int, Any]:
        if i < uploads:
            api, sid = sessions[i]
            return upload(api, "burst big upload", sid, big)
        return flat[i % len(flat)].call("burst dogs list during upload", "GET", "/dogs", params={"size": 20})

    results = together(uploads + readers, work)
    out[f"big upload x{uploads} + dogs list x{readers}"] = {
        "upload": statuses(results[:uploads]),
        "list": statuses(results[uploads:]),
        "sec": round(time.time() - started, 2),
    }
    return out


# ---- 끝난 뒤 DB 확인 ----

CHECKS = {
    "겹친 촬영 순번": "SELECT count(*) FROM (SELECT session_id, seq_no FROM shot GROUP BY 1, 2 HAVING count(*) > 1) t",
    "한 반려견에 MEASURING 회차 둘 이상": (
        "SELECT count(*) FROM (SELECT dog_id FROM measure_session WHERE status = 'MEASURING' "
        "GROUP BY 1 HAVING count(*) > 1) t"
    ),
    "분석이 끝나지 않은 촬영": "SELECT count(*) FROM shot WHERE status IN ('UPLOADED', 'SUBMITTED', 'ANALYZING')",
    "FAILED 촬영": "SELECT count(*) FROM shot WHERE status = 'FAILED'",
    "AGGREGATING에 멈춘 회차": "SELECT count(*) FROM measure_session WHERE status = 'AGGREGATING'",
    "FAILED 회차": "SELECT count(*) FROM measure_session WHERE status = 'FAILED'",
    "DONE 회차": "SELECT count(*) FROM measure_session WHERE status = 'DONE'",
    "보고서가 2부가 아닌 DONE 회차": (
        "SELECT count(*) FROM measure_session m WHERE m.status = 'DONE' "
        "AND (SELECT count(*) FROM report r WHERE r.session_id = m.id) <> 2"
    ),
    "DONE이 아닌 보고서": "SELECT count(*) FROM report WHERE status <> 'DONE'",
    "하루에 두 줄인 바이탈": (
        "SELECT count(*) FROM (SELECT dog_id, measured_on FROM dog_vital GROUP BY 1, 2 HAVING count(*) > 1) t"
    ),
    "결과 영상 READY": "SELECT count(*) FROM shot WHERE video_status = 'READY'",
    "결과 영상 PENDING": "SELECT count(*) FROM shot WHERE status = 'DONE' AND video_status = 'PENDING'",
    "결과 영상 FAILED": "SELECT count(*) FROM shot WHERE status = 'DONE' AND video_status = 'FAILED'",
}


def db_checks(wait_sec: float) -> dict[str, int]:
    """남은 분석·집계·보고서가 끝나기를 wait_sec까지 기다린 뒤 센다. 결과 영상은 기다리지 않는다."""
    pending = text(
        "SELECT (SELECT count(*) FROM shot WHERE status IN ('UPLOADED', 'SUBMITTED', 'ANALYZING')) + "
        "(SELECT count(*) FROM measure_session WHERE status = 'AGGREGATING') + "
        "(SELECT count(*) FROM report WHERE status IN ('PENDING', 'GENERATING'))"
    )

    def drained() -> bool:
        with SessionLocal() as db:
            return db.scalar(pending) == 0

    wait_until(time.time() + wait_sec, 2.0, drained)
    with SessionLocal() as db:
        return {name: int(db.scalar(text(sql))) for name, sql in CHECKS.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="동시 처리 점검(S15P31A404-274)")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--big-video", type=Path)
    parser.add_argument("--institutions", type=int, default=5)
    parser.add_argument("--staff", type=int, default=4)
    parser.add_argument("--shots", type=int, default=4)
    parser.add_argument("--readers", type=int, default=8)
    parser.add_argument("--burst", type=int, default=60, help="한꺼번에 보내는 조회 요청 수")
    parser.add_argument("--burst-uploads", type=int, default=20, help="한꺼번에 올리는 큰 영상 수")
    parser.add_argument("--skip", default="", help="건너뛸 것: flow,races,burst (쉼표로 구분)")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    skip = set(filter(None, args.skip.split(",")))

    run = secrets.token_hex(3)
    recorder = Recorder()
    logins, password = make_accounts(run, args.institutions, args.staff)
    started = time.time()
    flat_logins = [login_id for group in logins for login_id in group]
    with ThreadPoolExecutor(max_workers=len(flat_logins)) as pool:
        flat = list(pool.map(lambda login_id: login(args.base_url, recorder, login_id, password), flat_logins))
    apis = [flat[i * args.staff : (i + 1) * args.staff] for i in range(args.institutions)]
    report: dict[str, Any] = {
        "run": run,
        "settings": {k: v for k, v in vars(args).items() if k not in ("out", "video", "big_video", "base_url")},
        "login_all_sec": round(time.time() - started, 2),
    }
    video = args.video.read_bytes()
    if "flow" not in skip:
        report["flow"] = run_flow(apis, video, args.shots, args.readers)
    if "races" not in skip:
        report["races"] = run_races(apis[0], video)
    if "burst" not in skip:
        big = args.big_video.read_bytes() if args.big_video else None
        report["burst"] = run_burst(flat, video, big, args.burst, args.burst_uploads)
    report["db"] = db_checks(wait_sec=300)
    report["requests"] = recorder.summary()
    report["errors_5xx_or_0"] = sum(1 for _, status, _, _ in recorder.rows if status == 0 or status >= 500)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
