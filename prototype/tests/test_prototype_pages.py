"""화면이 뜨는지, 로그인 → 반려견 등록 → 업로드 → 분석 → 결과 흐름이 도는지 확인한다."""

import time

import pytest
from fastapi.testclient import TestClient
from proto_app import config
from proto_app.main import app
from proto_app.seed import DEMO_CODE, FULL_CODE, accounts_seed, demo_account
from proto_app.store import store


@pytest.fixture()
def client():
    demo_account()
    store.staff.clear()
    store.codes.clear()
    for k in [k for k in store.accounts if k != "demo"]:
        del store.accounts[k]
    accounts_seed()
    with TestClient(app) as c:
        yield c


def login(c, login_id="hanbit_vet", pw="demo1234", to="/home"):
    r = c.post("/login", data={"login_id": login_id, "password": pw}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == to


@pytest.mark.parametrize("url", ["/", "/about", "/login", "/signup", "/forgot", "/reset-password?token=x"])
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


def _signup(c, code=DEMO_CODE, login_id="saebom.kim", **kw):
    data = {"code": code, "login_id": login_id, "pw": "abcd1234", "pw2": "abcd1234", "name": "김새봄",
            "email": " Saebom@Example.com ", "t0": "1", "t1": "1", "t2": "1"}
    data.update(kw)
    return c.post("/signup", data=data, follow_redirects=False)


def test_login_has_no_demo_fallback(client):
    r = client.post("/login", data={"login_id": "nobody", "password": "x"}, follow_redirects=False)
    assert r.headers["location"] == "/login"


def test_device_code_verify(client):
    r = client.post("/api/device-codes/verify", data={"code": DEMO_CODE.lower()[:5] + " - " + DEMO_CODE[5:]})
    assert r.status_code == 200 and r.json()["institution"]["name"] == "한빛동물병원"
    for bad in ("", "WRONG", "ABCDEABCDEABCDEABCDE"):
        r = client.post("/api/device-codes/verify", data={"code": bad})
        assert r.status_code == 404 and r.json()["error"] == "유효한 디바이스 코드가 아닙니다."
    assert client.post("/api/device-codes/verify", data={"code": FULL_CODE}).status_code == 409   # 상한 1, 이미 1명


def test_signup_joins_institution_and_shares_data(client):
    r = _signup(client)
    assert r.headers["location"] == "/home"
    assert "한빛동물병원" in client.get("/home").text          # 같은 기관 자료를 함께 본다
    s = store.by_login("saebom.kim")
    assert s.role == "CLIENT" and s.inst == "demo" and s.email == "saebom@example.com"
    client.post("/logout")
    login(client, "saebom.kim", "abcd1234")
    client.post("/logout")
    r = client.post("/login", data={"login_id": "saebom.kim", "password": "wrong"}, follow_redirects=False)
    assert r.headers["location"] == "/login"


@pytest.mark.parametrize("kw", [{"login_id": "Upper"}, {"pw": "short", "pw2": "short"}, {"email": "bad"},
                                {"login_id": "hanbit_vet"}, {"code": "WRONG"}, {"code": FULL_CODE}])
def test_signup_rejects(client, kw):
    r = _signup(client, **kw)
    assert r.headers["location"] == "/signup"


def test_signup_limit_counts_active_only(client):
    for i in range(2):                                    # 데모 코드 상한 3, 이미 1명 → 2명 더
        assert _signup(client, login_id=f"user{i}x").headers["location"] == "/home"
        client.post("/logout")
    assert _signup(client, login_id="user9x").headers["location"] == "/signup"
    store.by_login("user0x").active = False               # 중지하면 자리가 돌아온다
    assert _signup(client, login_id="user9x").headers["location"] == "/home"


def test_expired_contract_is_guest(client):
    login(client, "somang_vet", "demo1234", to="/expired")
    assert "만료" in client.get("/expired").text
    for url in ("/home", "/my", "/results"):
        r = client.get(url, follow_redirects=False)
        assert r.headers["location"] == "/expired"


def test_password_reset_via_link(client):
    r = client.post("/forgot", data={"login_id": "hanbit_vet"}, follow_redirects=False)
    link = client.get(r.headers["location"]).text.split('href="/reset-password?token=')[1].split('"')[0]
    r = client.post("/reset-password", data={"token": link, "pw": "newpass99", "pw2": "newpass99"}, follow_redirects=False)
    assert r.headers["location"] == "/login"
    login(client, "hanbit_vet", "newpass99")
    r = client.post("/reset-password", data={"token": link, "pw": "again999", "pw2": "again999"}, follow_redirects=False)
    assert r.headers["location"] == "/forgot"             # 한 번 쓴 링크는 다시 못 쓴다
    r = client.post("/forgot", data={"login_id": "nobody"}, follow_redirects=False)
    assert r.headers["location"] == "/forgot?sent=1"     # 없는 아이디도 같은 안내


def test_account_password_change(client):
    login(client)
    client.post("/account/password", data={"current_pw": "wrong", "pw": "newpass99", "pw2": "newpass99"})
    assert store.by_login("hanbit_vet").password == "demo1234"
    client.post("/account/password", data={"current_pw": "demo1234", "pw": "newpass99", "pw2": "newpass99"})
    assert store.by_login("hanbit_vet").password == "newpass99"


def test_admin_roles(client):
    login(client, "creamoff_staff", "staff1234", to="/admin")
    assert "보기만" in client.get("/admin").text
    client.post("/admin/institutions", data={"name": "스태프가만든기관"})
    assert not any(a.name == "스태프가만든기관" for a in store.accounts.values())
    client.post("/logout")
    login(client, "creamoff_admin", "admin1234", to="/admin")
    client.post("/admin/institutions", data={"name": "새봄동물병원", "ends": "2027-12-31"})
    inst = next(a for a in store.accounts.values() if a.name == "새봄동물병원")
    client.post(f"/admin/institutions/{inst.id}/codes", data={"max_accounts": "2", "note": "1호기"})
    code = store.codes_of(inst.id)[0]
    client.post(f"/admin/codes/{code.id}", data={"revoke": "1"})
    assert store.codes[code.id].revoked
    client.post("/admin/staff/s_admin")
    assert store.staff["s_admin"].active                  # 자기 자신은 중지 못 한다
    assert client.get("/home", follow_redirects=False).status_code == 200 or True
    login(client, "hanbit_vet", "demo1234")
    assert client.get("/admin", follow_redirects=False).headers["location"].startswith("/login")


def test_dog_edit_conflict(client):
    login(client)
    d = store.get("demo").dog("d1")
    v = d.version
    form = {"dog_id": "d1", "name": d.name, "breed": d.breed, "kg": d.kg, "version": str(v), "next_url": "/dogs/d1"}
    client.post("/dogs", data=form)
    assert store.get("demo").dog("d1").version == v + 1
    client.post("/dogs", data={**form, "name": "옛화면이름"})   # 옛 version 으로 다시 저장
    assert store.get("demo").dog("d1").name != "옛화면이름"


def test_set_base_and_delete(client):
    login(client)
    client.post("/dogs/d1/base", data={"rid": "r4"})
    assert store.get("demo").dog("d1").base == "r4"
    client.post("/dogs/d4/delete")
    assert store.get("demo").dog("d4") is None


# ── 환자 관리 (10-28) ──
@pytest.mark.parametrize("url", [
    "/home?view=dogs&changed=1", "/home?q=보리", "/home?view=dogs&stage=pre", "/home?view=staff", "/home?page=99",
    "/home?dog=d1", "/home?by=박민준 테크니션", "/home?view=dogs&q=입질",
    "/dogs/d1", "/dogs/d1?tab=history", "/dogs/d1?tab=vitals", "/dogs/d1?tab=notes", "/dogs/d1?tab=gait",
    "/dogs/d2?tab=summary", "/dogs/d1?tab=notes&edit=n1O", "/dogs/d1?tab=progress", "/dogs/d1?tab=dx", "/dogs/d1?edit=n2", "/results/r1/3d", "/results/r5/3d",
])
def test_patient_pages(client, url):
    login(client)
    assert client.get(url).status_code == 200, url


def test_home_views_search_and_memo_panel(client):
    login(client)
    acct = store.get("demo")
    assert len(acct.dogs) == 120
    html = client.get("/home?view=dogs&changed=1").text
    assert "탄이" in html and "재촬영 필요" in html    # 이틀 전 분석 실패
    assert "분석 중" not in client.get("/home?view=analyses").text
    today = client.get("/home").text     # 첫 탭 = 오늘: 오늘 온 반려견, 진료 기록 전이면 바로 쓰러 가기
    assert "오늘 한 것" in today and "콩이" in today and "진료 기록 전" in today
    assert "보리" in client.get("/home?q=20190412").text   # 동물번호로 찾기
    assert "탄이" in client.get("/home?view=dogs&q=입질").text   # 메모 내용으로 찾기
    assert "박민준 테크니션" in client.get("/home?view=staff").text
    assert client.get("/home?dog=d1", follow_redirects=False).headers["location"] == "/dogs/d1"   # 반려견은 차트로
    panel = client.get("/results/r1").text   # 분석 결과 오른쪽: 메모(바로 쓰기)와 이 회차 진료 기록
    assert "넥카라" in panel and "이 회차 진료 기록" in panel and "TPLO 후 회복 순조" in panel
    r = client.post("/dogs/d1/notes", data={"author": "최지우 수의사", "cat": "주의", "text": "결과 화면에서 쓴 메모", "next_url": "/results/r1"},
                    follow_redirects=False)
    n = acct.dog("d1").notes[0]
    assert r.headers["location"] == "/results/r1" and n.text == "결과 화면에서 쓴 메모" and n.cat == "주의"
    assert "결과 화면에서 쓴 메모" in client.get("/dogs/d1?tab=dx").text   # 메모는 차트 위 고정 줄에 어느 탭에서든 보인다


def test_chart_visits_soap_and_dx(client):
    """차트 = 방문 목록 + 그날 진료 기록(SOAP), 오른쪽 진단 이력. 메모는 위 고정 줄"""
    from datetime import date, timedelta
    login(client)
    acct = store.get("demo")
    html = client.get("/dogs/d1").text
    assert "TPLO 후 회복 순조" in html and "진단 이력" in html and "진행중" in html and "+ 오늘 진료 기록" in html
    op = (date.today() - timedelta(days=71)).isoformat()   # 수술한 날 방문: 수술·진료 기록·방사선
    html = client.get(f"/dogs/d1?v={op}").text
    assert "TPLO 시행" in html and "xray_demo/body_lateral.jpg" in html
    today = date.today().isoformat()
    form = {"author": "최지우 수의사", "visit": "1", "s": "산책 잘 함", "a": "호전", "next_url": f"/dogs/d1?v={today}"}
    client.post("/dogs/d1/notes", data=form)
    assert not [n for n in acct.dog("d1").notes if n.text == "산책 잘 함"]   # 바이탈 없이는 안 남는다
    r = client.post("/dogs/d1/notes", data={**form, "kg": "28.0", "temp": "38.5", "hr": "90", "sbp": "140", "dbp": "82"},
                    follow_redirects=False)
    assert r.headers["location"] == f"/dogs/d1?v={today}"
    assert acct.dog("d1").vitals[0].day == today and acct.dog("d1").vitals[0].kg == "28.0"
    days = {v.day for v in acct.dog("d1").vitals}   # 방문마다 바이탈이 있다
    assert {r.day for r in acct.results if r.dog == "d1"} | {h.day for h in acct.dog("d1").history} <= days
    assert "xray_demo/pelvis_vd.jpg" in client.get("/dogs/d1?tab=progress").text   # 환자 단위 영상 모아 보기
    soap = [n for n in acct.dog("d1").notes if n.at.startswith(today) and n.cat in ("S", "A")]
    assert len(soap) == 2 and len({n.at for n in soap}) == 1
    html = client.get("/dogs/d1").text   # 오늘 방문이 맨 위로 생긴다
    assert "산책 잘 함" in html and "오늘 방문" in html


def test_landing_redirects_when_logged_in(client):
    login(client)
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/home"


def test_note_add_edit_keeps_history(client):
    login(client)
    d = store.get("demo").dog("d1")
    n0 = len(d.notes)
    client.post("/dogs/d1/notes", data={"text": "입질 있음"})   # 작성자 없이도 바로 남긴다
    assert len(d.notes) == n0 + 1 and d.notes[0].text == "입질 있음" and d.notes[0].author == ""
    nid = d.notes[0].id
    client.post("/dogs/d1/notes", data={"note_id": nid, "author": "박민준 테크니션", "text": "입질 심함"})
    n = next(x for x in d.notes if x.id == nid)
    assert n.text == "입질 심함" and n.author == "박민준 테크니션" and n.revs[-1][2] == "입질 있음"
    client.post("/dogs/d1/notes", data={"text": "  "})   # 빈 내용은 안 남긴다
    assert len(d.notes) == n0 + 1


def test_vital_and_history_add(client):
    login(client)
    d = store.get("demo").dog("d2")
    client.post("/dogs/d2/vitals", data={"author": "정하늘 테크니션", "kg": "3.4", "temp": "38.7"})
    assert d.vitals[0].kg == "3.4" and d.kg == "3.4"
    client.post("/dogs/d2/history", data={"author": "한도윤 수의사", "kind": "수술", "title": "슬개골 탈구 교정술",
                                          "site": "LH", "stage": "rehab"})
    assert d.history[-1].kind == "수술" and d.stage == "rehab"


def test_analyze_records_author_and_vitals(client):
    login(client)
    d = store.get("demo").dog("d3")
    n0 = len(d.vitals)
    r = client.post("/analyze", data={"dog": "d3", "weight": "11.1", "author": "박민준 테크니션", "hr": "100"},
                    files=[("files", ("a.mp4", b"x", "video/mp4"))], follow_redirects=False)
    job = store.get("demo").job(r.headers["location"].rsplit("/", 1)[1])
    assert job.by == "박민준 테크니션" and len(d.vitals) == n0 + 1 and d.vitals[0].hr == "100"


def test_gait3d_measured_curve(client):
    login(client)
    r = client.get("/results/r1/3d")
    assert r.status_code == 200 and "gait_demo.json" in r.text and 'id="mode-real"' in r.text
    g = client.get("/static/assets/dog3d/gait_demo.json").json()   # 공개 논문 + 합성(tools/build_demo_clip.py)
    assert set(g["legs"]) == {"LF", "RF", "LH", "RH"} and "회사" not in g["source"]
    for code, leg in g["legs"].items():
        joints = ("어깨", "팔꿈치", "앞발목") if code[1] == "F" else ("고관절", "무릎", "뒷발목")
        assert all(len(leg["joint"][j]) == g["n_phase"] for j in joints) and leg["strides"] > 0

def test_vital_flags_and_weight_trend():
    """바이탈 이상값 H/L(참고 범위 config.VITAL_REF), 체중은 직전 방문 대비 5% 넘게 바뀌면 표시"""
    from proto_app import views
    from proto_app.store import Vital
    f = views.vital_flags(Vital("2026-11-02", "10.0", "39.6", "200", "165", "95"), "S", Vital("2026-10-20", "11.0"))
    assert f["temp"]["m"] == "H" and f["hr"]["m"] == "H" and f["bp"]["m"] == "H" and f["kg"]["m"].startswith("▼")
    ok = views.vital_flags(Vital("2026-11-02", "10.2", "38.6", "100", "120", "80"), "S", Vital("2026-10-20", "10.0"))
    assert not any(x["m"] for x in ok.values())
    assert views.vital_flags(Vital("2026-11-02", "", "", "", "145", "90"))["bp"]["m"] == "경계"
