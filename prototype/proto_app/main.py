"""Paw oh Paw 웹 프로토타입 (디자인 PawOhPaw_web.html을 FastAPI + Jinja2로 옮김).

실행: prototype 폴더에서  uvicorn proto_app.main:app --reload --port 8001
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional
from urllib.parse import quote, unquote

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config, views
from .analysis import finish_due_jobs, start_job
from .seed import DEMO_ID, demo_account, seed
from .store import Account, Dog, new_id, store

COOKIE = "pp_acct"
TOAST = "pp_toast"

app = FastAPI(title="Paw oh Paw 프로토타입")
config.UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=config.BASE_DIR / "static"), name="static")
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")
templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))
templates.env.globals.update(SEX=config.SEX, SIZE=config.SIZE, LIMB=config.LIMB, STEPS=config.STEPS,
                             MAX_SHOTS=config.MAX_SHOTS)
seed()

# 화면 바로가기 (디자인 검토용): 이름, 주소, 로그인 필요 여부
JUMPS = [
    ("랜딩", "/", False), ("서비스 소개 (로그인 전)", "/about", False), ("로그인", "/login", False),
    ("기관 회원가입", "/signup", False), ("홈 · 반려견 · 측정 이력", "/home", True), ("반려견 등록", "/home?modal=pet", True),
    ("영상 업로드", "/upload", True), ("업로드 · 영상 첨부 중", "/upload?demo=7", True), ("분석 중", "/analyzing/demo", True),
    ("분석 결과", "/results", True), ("회차 결과", "/results/r1", True), ("회차 결과 · 일부 유효", "/results/r2", True),
    ("회차 결과 · 실패", "/results/r3", True), ("보고서", "/results/r1/report", True), ("경과 비교", "/compare/d1", True),
    ("서비스 소개", "/about", True), ("마이페이지", "/my", True), ("기본 정보", "/account", True),
]


# ── 공통 ──
def current(request: Request) -> Optional[Account]:
    acct = store.get(request.cookies.get(COOKIE))
    if acct:
        finish_due_jobs(acct)
    return acct


def redirect(url: str, toast: str = "") -> RedirectResponse:
    resp = RedirectResponse(url, status_code=303)
    if toast:
        resp.set_cookie(TOAST, quote(toast), max_age=30)
    return resp


def need_login() -> RedirectResponse:
    return redirect("/login", "로그인해 주세요")


def finished_notices(acct: Account, skip_job: str = "") -> list:
    """끝났지만 아직 알리지 않은 분석."""
    out = []
    for job in acct.jobs:
        if job.result_id and not job.notified and job.id != skip_job:
            job.notified = True
            d = acct.dog(job.dog)
            out.append(f"{d.name if d else ''} 분석이 끝났어요")
    return out


def page(request: Request, name: str, acct: Optional[Account] = None, nav: str = "", **ctx):
    toast = unquote(request.cookies.get(TOAST, ""))
    if acct:
        notices = finished_notices(acct, ctx.get("job_id", ""))
        toast = toast or (notices[0] if notices else "")
    ctx.update(acct=acct, nav=nav, toast=toast, jumps=JUMPS,
               live_dogs=[j.dog for j in acct.active_jobs()] if acct else [],
               has_active=bool(acct and acct.active_jobs()),
               breeds=config.BREEDS, dogs_data={d.id: vars(d) for d in acct.dogs} if acct else {})
    resp = templates.TemplateResponse(request, name, ctx)
    if request.cookies.get(TOAST):
        resp.delete_cookie(TOAST)
    return resp


# ── 로그인 전 ──
@app.get("/")
def landing(request: Request):
    return page(request, "landing.html", current(request))


@app.get("/about")
def about(request: Request):
    acct = current(request)
    return page(request, "about.html", acct, nav="about")


@app.get("/login")
def login_page(request: Request):
    return page(request, "login.html")


@app.post("/login")
def login(login_id: str = Form(""), password: str = Form("")):
    if len(login_id) < 2 or len(password) < 4:
        return redirect("/login", "아이디와 비밀번호를 입력해 주세요")
    acct = store.by_login(login_id)
    if acct and acct.password != password:
        return redirect("/login", "비밀번호가 맞지 않아요")
    acct = acct or demo_account()   # 가입하지 않은 아이디는 데모 기관(예시 데이터를 처음 상태로)으로 들어간다
    resp = redirect("/home")
    resp.set_cookie(COOKIE, acct.id, httponly=True)
    return resp


@app.get("/signup")
def signup_page(request: Request):
    return page(request, "signup.html")


@app.post("/signup")
def signup(org: str = Form(""), loc: str = Form(""), dev: str = Form(""), login_id: str = Form(""),
           pw: str = Form(""), pw2: str = Form(""), t0: str = Form(""), t1: str = Form(""), t2: str = Form(""),
           t3: str = Form("")):
    if not (t0 and t1 and t2):
        return redirect("/signup", "필수 약관에 동의해 주세요")
    if pw2 and pw != pw2:
        return redirect("/signup", "비밀번호가 서로 달라요")
    if not (org and dev and len(login_id) >= 4 and len(pw) >= 4 and pw == pw2):
        return redirect("/signup", "입력하지 않은 항목이 있어요")
    if store.by_login(login_id):
        return redirect("/signup", "이미 쓰고 있는 아이디예요")
    acct = store.add(Account(new_id("a"), login_id, pw, org, loc or "-", dev))
    resp = redirect("/home", f"{org} 가입을 환영해요")
    resp.set_cookie(COOKIE, acct.id, httponly=True)
    return resp


@app.post("/logout")
def logout():
    resp = redirect("/")
    resp.delete_cookie(COOKIE)
    return resp


@app.get("/jump/{idx}")
def jump(idx: int):
    """화면 바로가기: 디자인 검토용. 로그인이 필요한 화면은 데모 기관으로 들어간다."""
    _, url, need = JUMPS[idx]
    if not need:
        resp = redirect(url)
        resp.delete_cookie(COOKIE)
        return resp
    acct = store.get(DEMO_ID)
    if not acct or not acct.result("r1"):
        acct = demo_account()
    resp = redirect(url)
    resp.set_cookie(COOKIE, acct.id, httponly=True)
    return resp


# ── 홈 ──
@app.get("/home")
def home(request: Request, dog: str = "", q: str = "", modal: str = ""):
    acct = current(request)
    if not acct:
        return need_login()
    cur = acct.dog(dog) or (acct.dogs[0] if acct.dogs else None)
    strip = []
    for d in acct.dogs:
        all_ = [r for r in acct.results if r.dog == d.id]
        strip.append({"id": d.id, "init": d.name[0], "name": d.name, "breed": d.breed or "견종 미입력",
                      "meta": f"{len(all_)}회차 · {views.short(all_[0].date)}" if all_ else "측정 전",
                      **views.avatar(cur is not None and d.id == cur.id)})
    recent = []
    for i, r in enumerate([r for r in acct.results if acct.dog(r.dog)][:12]):
        d = acct.dog(r.dog)
        recent.append({"id": r.id, "init": d.name[0], "name": d.name, "when": f"{r.date} · {views.sess_no(acct, r)}회차",
                       **views.st_chip(r.st), "bt": "1px solid #F2EFEA" if i else "none"})
    ctx = {"cur": cur, "strip": strip, "recent": recent, "q": q, "modal": modal}
    if cur:
        ctx["dd"] = views.dog_detail(acct, cur)
        latest = next((r for r in acct.results if r.dog == cur.id), None)
        ctx["latest"] = views.result_view(acct, latest, home=True)["rd"] if latest else None
    return page(request, "home.html", acct, nav="home", **ctx)


def _pet_from_form(name, breed, kg, birth, sex, size, rehab, focus, memo) -> dict:
    return {"name": name.strip(), "breed": breed.strip(), "kg": kg.strip(), "birth": birth.strip(),
            "sex": sex if sex in config.SEX else "m", "size": size if size in config.SIZE else "",
            "rehab": rehab, "focus": focus if focus in config.LIMB else None, "memo": memo.strip()}


@app.post("/dogs")
def dog_save(request: Request, dog_id: str = Form(""), name: str = Form(""), breed: str = Form(""),
             kg: str = Form(""), birth: str = Form(""), sex: str = Form("m"), size: str = Form(""),
             rehab: str = Form(""), focus: str = Form(""), memo: str = Form(""), next_url: str = Form("/home")):
    acct = current(request)
    if not acct:
        return need_login()
    data = _pet_from_form(name, breed, kg, birth, sex, size, rehab, focus, memo)
    if not (data["name"] and data["breed"] and data["kg"]):
        return redirect(next_url, "이름·견종·체중을 입력해 주세요")
    manual = bool(data["size"])
    data["size"] = data["size"] or config.auto_size(data["breed"], data["kg"])
    data["size_manual"] = manual
    d = acct.dog(dog_id)
    if d:
        for k, v in data.items():
            setattr(d, k, v)
        return redirect(next_url, "저장했어요")
    d = Dog(new_id("p"), **data)
    acct.dogs.append(d)
    sep = "&" if "?" in next_url else "?"
    target = next_url if next_url.startswith("/upload") or next_url.startswith("/my") else "/home"
    return redirect(f"{target}{sep}dog={d.id}", f"{d.name} 등록을 마쳤어요")


@app.post("/dogs/{dog_id}/delete")
def dog_delete(request: Request, dog_id: str):
    acct = current(request)
    if not acct:
        return need_login()
    d = acct.dog(dog_id)
    if not d:
        return redirect("/my")
    acct.dogs = [x for x in acct.dogs if x.id != dog_id]
    acct.results = [r for r in acct.results if r.dog != dog_id]
    acct.jobs = [j for j in acct.jobs if j.dog != dog_id]
    return redirect("/my", f"{d.name} 정보를 삭제했어요")


@app.post("/dogs/{dog_id}/base")
def set_base(request: Request, dog_id: str, rid: str = Form(...)):
    acct = current(request)
    if not acct:
        return need_login()
    d, r = acct.dog(dog_id), acct.result(rid)
    if d and r and r.st != "fail":
        d.base = r.id
        return redirect(f"/home?dog={dog_id}", f"{r.date} 회차를 기준으로 정했어요")
    return redirect(f"/home?dog={dog_id}")


# ── 영상 업로드 · 분석 ──
@app.get("/upload")
def upload(request: Request, dog: str = "", demo: int = 0):
    acct = current(request)
    if not acct:
        return need_login()
    if not acct.dogs:
        return redirect("/home?modal=pet", "먼저 반려견을 등록해 주세요")
    sel = acct.dog(dog) or acct.dogs[0]
    dogs = [{"id": d.id, "init": d.name[0], "name": d.name, "breed": d.breed or "견종 미입력", "kg": d.kg,
             **views.avatar(d.id == sel.id)} for d in acct.dogs]
    return page(request, "upload.html", acct, nav="upload", dogs=dogs, sel=sel, demo=max(0, min(demo, 16)))


@app.post("/analyze")
def analyze(request: Request, dog: str = Form(...), weight: str = Form(""), demo_count: int = Form(0),
            files: list[UploadFile] = File(default=[])):
    acct = current(request)
    if not acct:
        return need_login()
    if not acct.dog(dog):
        return redirect("/upload", "반려견을 골라 주세요")
    saved = []
    for f in files[: config.MAX_SHOTS]:
        if not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        if ext not in config.VIDEO_EXT and not (f.content_type or "").startswith("video/"):
            return redirect(f"/upload?dog={dog}", "영상 파일(MP4 · MOV)만 올릴 수 있어요")
        dest = config.UPLOAD_DIR / f"{new_id('v')}{ext or '.mp4'}"
        with dest.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        saved.append(f"/uploads/{dest.name}")
    n = len(saved) or max(0, min(demo_count, config.MAX_SHOTS))
    if not n:
        return redirect(f"/upload?dog={dog}", "보행 영상을 1개 이상 올려 주세요")
    job = start_job(acct, dog, n, weight.strip(), saved)
    return redirect(f"/analyzing/{job.id}")


@app.get("/analyzing/{job_id}")
def analyzing(request: Request, job_id: str):
    acct = current(request)
    if not acct:
        return need_login()
    job = acct.job(job_id) if job_id != "demo" else None
    if job_id == "demo":   # 화면 바로가기: 진행 중인 분석이 없으면 새로 하나 띄운다
        job = (acct.active_jobs() or [None])[0] or start_job(acct, acct.dogs[0].id if acct.dogs else "", 16, "", [])
        return redirect(f"/analyzing/{job.id}")
    if not job:
        return redirect("/results")
    if job.result_id:
        job.notified = True
        return redirect(f"/results/{job.result_id}")
    d = acct.dog(job.dog)
    return page(request, "analyzing.html", acct, job_id=job.id, job=job, dog_name=d.name if d else "")


@app.get("/api/jobs/{job_id}")
def job_status(request: Request, job_id: str):
    acct = current(request)
    job = acct.job(job_id) if acct else None
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    p = job.progress()
    if job.result_id:
        job.notified = True
    return {"pct": round(p / 5 * 100), "step": config.STEPS[min(4, int(p))], "done": bool(job.result_id),
            "url": f"/results/{job.result_id}" if job.result_id else None}


@app.get("/api/notices")
def notices(request: Request):
    """다른 화면에 있을 때 분석이 끝나면 알림을 띄우려고 부른다."""
    acct = current(request)
    if not acct:
        return {"active": 0, "notices": []}
    return {"active": len(acct.active_jobs()), "notices": finished_notices(acct)}


# ── 분석 결과 ──
@app.get("/results")
def results(request: Request, dog: str = "all"):
    acct = current(request)
    if not acct:
        return need_login()
    filt = dog if acct.dog(dog) else "all"
    chips = [{"id": "all", "init": "전체", "name": "전체", "breed": "", **views.avatar(filt == "all")}]
    chips += [{"id": d.id, "init": d.name[0], "name": d.name, "breed": d.breed or "견종 미입력", **views.avatar(filt == d.id)}
              for d in acct.dogs]
    rows = []
    for i, r in enumerate([r for r in acct.results if acct.dog(r.dog) and (filt == "all" or r.dog == filt)]):
        rows.append({"id": r.id, "name": acct.dog(r.dog).name, "when": f"{r.date} · {views.sess_no(acct, r)}회차",
                     **views.st_chip(r.st), "pass": "—" if r.st == "fail" else f"{r.ps[1]} / {r.ps[0]}",
                     "sym": "—" if r.st == "fail" else f"{r.sym}%", "w": f"{r.w}kg", "bt": "1px solid #F2EFEA" if i else "none"})
    return page(request, "results.html", acct, nav="results", chips=chips, rows=rows)


@app.get("/results/{rid}")
def result_detail(request: Request, rid: str, gait: str = "trot"):
    acct = current(request)
    if not acct:
        return need_login()
    r = acct.result(rid)
    if not r:
        return redirect("/results", "회차를 찾을 수 없어요")
    gait = gait if gait in ("walk", "trot") else "trot"
    v = views.result_view(acct, r, gait)
    return page(request, "detail.html", acct, nav="results", rd=v["rd"], gait=gait,
                gait_segs=views.seg([("walk", "평보"), ("trot", "속보")], gait), video=(r.videos or [None])[0])


@app.get("/results/{rid}/report")
def report(request: Request, rid: str, type: str = "g"):
    acct = current(request)
    if not acct:
        return need_login()
    r = acct.result(rid)
    if not r or r.st == "fail":
        return redirect(f"/results/{rid}" if r else "/results", "보고서를 만들 수 없는 회차예요")
    kind = type if type in ("g", "v") else "g"
    v = views.result_view(acct, r)
    return page(request, "report.html", acct, nav="results", rd=v["rd"], rp=v["rp"], kind=kind,
                segs=views.seg([("g", "보호자용"), ("v", "수의사용")], kind),
                status=f"생성 완료 · {'9.1' if kind == 'v' else '8.4'}초 · 분석 모델 {r.model} · 템플릿 1.0")


# ── 경과 비교 ──
@app.get("/compare/{dog_id}")
def compare(request: Request, dog_id: str, cmp: str = "base", tk: str = "rom"):
    acct = current(request)
    if not acct:
        return need_login()
    d = acct.dog(dog_id)
    if not d:
        return redirect("/home")
    if len(views.valid(acct, d.id)) < 2:
        return redirect(f"/home?dog={dog_id}", "유효한 회차가 2개 이상 있어야 비교할 수 있어요")
    cmp = cmp if cmp in ("base", "prev") else "base"
    tk = tk if tk in dict(views.TREND_KEYS) else "rom"
    trend = [{"key": k, "label": label, "on": k == tk} for k, label in views.TREND_KEYS]
    return page(request, "compare.html", acct, nav="home", dog=d, cp=views.compare_view(acct, d, cmp, tk), cmp=cmp, tk=tk,
                segs=views.seg([("base", "기준 회차 대비"), ("prev", "직전 회차 대비")], cmp), trend=trend)


# ── 마이페이지 ──
@app.get("/my")
def my(request: Request):
    acct = current(request)
    if not acct:
        return need_login()
    dogs = [{"id": d.id, "init": d.name[0], "name": d.name, "desc": f"{views.desc(d)} · {config.SEX.get(d.sex or 'm')}",
             "bt": "1px solid #F2EFEA" if i else "none"} for i, d in enumerate(acct.dogs)]
    return page(request, "my.html", acct, nav="my", dogs=dogs)


@app.post("/my/notif")
def toggle_notif(request: Request):
    acct = current(request)
    if not acct:
        return need_login()
    acct.notif_on = not acct.notif_on
    return redirect("/my")


@app.get("/account")
def account(request: Request):
    acct = current(request)
    if not acct:
        return need_login()
    rows = [("계정 유형", "기관 회원"), ("기관명", acct.name), ("아이디", acct.login_id), ("기관 주소", acct.loc),
            ("디바이스 번호", acct.dev), ("가입일", acct.joined)]
    return page(request, "account.html", acct, nav="my", rows=rows)
