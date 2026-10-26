"""화면이 뜨는지, 로그인 → 반려견 등록 → 업로드 → 분석 → 결과 흐름이 도는지 확인한다."""

import time

import pytest
from fastapi.testclient import TestClient
from proto_app import config
from proto_app.main import app
from proto_app.seed import demo_account
from proto_app.store import store


@pytest.fixture()
def client():
    demo_account()
    with TestClient(app) as c:
        yield c


def login(c):
    r = c.post("/login", data={"login_id": "hanbit", "password": "1234"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/home"


@pytest.mark.parametrize("url", ["/", "/about", "/login", "/signup"])
def test_public_pages(client, url):
    assert client.get(url).status_code == 200


def test_app_pages_need_login(client):
    r = client.get("/home", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


@pytest.mark.parametrize("url", [
    "/home", "/home?dog=d3", "/home?modal=pet", "/upload", "/upload?demo=7", "/results", "/results?dog=d1",
    "/results/r1", "/results/r1?gait=walk", "/results/r2", "/results/r3", "/results/r1/report",
    "/results/r1/report?type=v", "/compare/d1", "/compare/d1?cmp=prev&tk=sym", "/my", "/account", "/about",
])
def test_app_pages(client, url):
    login(client)
    r = client.get(url)
    assert r.status_code == 200, url


def test_flow_register_upload_analyze(client, monkeypatch):
    login(client)
    r = client.post("/dogs", data={"name": "하늘", "breed": "푸들", "kg": "4.1", "sex": "f", "next_url": "/upload"},
                    follow_redirects=False)
    assert r.headers["location"].startswith("/upload?dog=")
    acct = store.get("demo")
    dog = acct.dogs[-1]
    assert dog.name == "하늘" and dog.size == "S"

    r = client.post("/analyze", data={"dog": dog.id, "weight": "4.0"},
                    files=[("files", ("a.mp4", b"x", "video/mp4")), ("files", ("b.mov", b"y", "video/quicktime"))],
                    follow_redirects=False)
    job_url = r.headers["location"]
    assert job_url.startswith("/analyzing/")
    job = acct.job(job_url.rsplit("/", 1)[1])
    assert job.n == 2 and len(job.videos) == 2

    monkeypatch.setattr(config, "ANALYSIS_SEC", 0.01)
    time.sleep(0.02)
    status = client.get(f"/api/jobs/{job.id}").json()
    assert status["done"] and status["url"].startswith("/results/")
    assert client.get(status["url"]).status_code == 200
    # 첫 측정이라 경과 비교는 막힌다
    r = client.get(f"/compare/{dog.id}", follow_redirects=False)
    assert r.status_code == 303


def test_upload_rejects_non_video(client):
    login(client)
    r = client.post("/analyze", data={"dog": "d1"}, files=[("files", ("x.txt", b"x", "text/plain"))],
                    follow_redirects=False)
    assert r.headers["location"] == "/upload?dog=d1"


def test_signup_then_login(client):
    r = client.post("/signup", data={"org": "새봄동물병원", "dev": "PP-1", "login_id": "saebom", "pw": "abcd",
                                     "pw2": "abcd", "t0": "1", "t1": "1", "t2": "1"}, follow_redirects=False)
    assert r.headers["location"] == "/home"
    assert "새봄동물병원" in client.get("/home").text
    client.post("/logout")
    r = client.post("/login", data={"login_id": "saebom", "password": "wrong"}, follow_redirects=False)
    assert r.headers["location"] == "/login"


def test_set_base_and_delete(client):
    login(client)
    client.post("/dogs/d1/base", data={"rid": "r4"})
    assert store.get("demo").dog("d1").base == "r4"
    client.post("/dogs/d4/delete")
    assert store.get("demo").dog("d4") is None
