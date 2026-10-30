"""Paw oh Paw 웹 프로토타입 (디자인 PawOhPaw_web.html을 FastAPI + Jinja2로 옮김).

실행: prototype 폴더에서  uvicorn proto_app.main:app --reload --port 8001
"""

from __future__ import annotations

import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote, unquote, urlencode

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config, views
from .analysis import finish_due_jobs, start_job
from .seed import DEMO_ID, demo_account, seed
from .store import Account, Dog, History, Note, Vital, new_id, store

COOKIE = "pp_acct"
TOAST = "pp_toast"

app = FastAPI(title="Paw oh Paw 프로토타입")
config.UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=config.BASE_DIR / "static"), name="static")
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")
templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))
templates.env.globals.update(SEX=config.SEX, SIZE=config.SIZE, LIMB=config.LIMB, SITE=config.SITE, STAGE_NAMES={k: v[0] for k, v in config.STAGE.items()}, STEPS=config.STEPS,
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
    ctx.update(acct=acct, nav=nav, toast=toast, jumps=JUMPS if config.SHOW_JUMPS else [],
               live_dogs=[j.dog for j in acct.active_jobs()] if acct else [],
               has_active=bool(acct and acct.active_jobs()),
               breeds=config.BREEDS, dogs_data={d.id: {k: v for k, v in vars(d).items() if not isinstance(v, list)} for d in acct.dogs} if acct else {})
    resp = templates.TemplateResponse(request, name, ctx)
    if request.cookies.get(TOAST):
        resp.delete_cookie(TOAST)
    return resp


# ── 로그인 전 ──
@app.get("/")
def landing(request: Request):
    acct = current(request)
    if acct:   # 서비스 소개는 로그인 전 화면. 로그인한 사람은 바로 홈으로
        return redirect("/home")
    return page(request, "landing.html")


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


# ── 홈: 분석 · 반려견 · 촬영 담당자 목록 ──
HOME_VIEWS = [("analyses", "분석"), ("dogs", "반려견"), ("staff", "촬영 담당자")]


@app.get("/home")
def home(request: Request, view: str = "analyses", q: str = "", dog: str = "", by: str = "", changed: str = "",
         stage: str = "", page_no: int = Query(1, alias="page"), modal: str = ""):
    """버튼으로 목록 하나(분석·반려견·촬영 담당자)만 띄운다. 반려견을 누르면 반려견 차트로 간다."""
    acct = current(request)
    if not acct:
        return need_login()
    if acct.dog(dog):   # 반려견은 차트에서 본다
        return redirect(f"/dogs/{dog}")
    view = "analyses" if by else (view if view in dict(HOME_VIEWS) else "analyses")
    hv = views.home_view(acct, view, q, "", by, bool(changed), stage, page_no)
    keep = {"view": view, "q": q, "by": by, "changed": changed, "stage": stage}
    qs = lambda **kw: "/home?" + urlencode({k: v for k, v in {**keep, **kw}.items() if v})  # noqa: E731
    return page(request, "home.html", acct, nav="home", hv=hv, view=view, views_=HOME_VIEWS, q=q, by=by,
                changed=changed, stage=stage, qs=qs, modal=modal, today=views.fmt_date(date.today().isoformat()))


CHART_TABS = [("summary", "차트 요약"), ("history", "히스토리"), ("vitals", "방문 · 바이탈"), ("notes", "동물 메모"),
              ("gait", "보행 측정")]


@app.get("/dogs/{dog_id}")
def dog_chart(request: Request, dog_id: str, tab: str = "summary", edit: str = ""):
    acct = current(request)
    if not acct:
        return need_login()
    cur = acct.dog(dog_id)
    if not cur:
        return redirect("/home", "반려견을 찾을 수 없어요")
    tab = tab if tab in dict(CHART_TABS) else "summary"
    latest = next((r for r in acct.results if r.dog == cur.id), None)
    live = {j.dog for j in acct.active_jobs()}
    return page(request, "dog.html", acct, nav="home", cur=cur, dd=views.dog_detail(acct, cur), tab=tab, tabs=CHART_TABS,
                row=views.patient_row(acct, cur, live), sm=views.chart_summary(acct, cur), notes=views.note_rows(cur, acct),
                panel=views.memo_panel(acct, cur),
                vt=views.vital_rows(cur), edit=edit, note_cats=config.NOTE_CAT, today_iso=date.today().isoformat(),
                latest=views.result_view(acct, latest, home=True)["rd"] if latest else None)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@app.post("/dogs/{dog_id}/notes")
def note_add(request: Request, dog_id: str, author: str = Form(""), cat: str = Form("경과"), text: str = Form(""),
             important: str = Form(""), note_id: str = Form(""), next_url: str = Form(""), rid: str = Form("")):
    """메모 쓰기·고치기. 공용 계정이라 작성자는 사람이 적는다. 고치면 이전 내용을 revs 에 남기고 지우지 않는다."""
    acct = current(request)
    if not acct:
        return need_login()
    d = acct.dog(dog_id)
    back = next_url if next_url.startswith(("/results/", "/dogs/")) else f"/dogs/{dog_id}?tab=notes"   # 쓴 화면으로 돌아간다
    if not d:
        return redirect("/home")
    author, text = author.strip(), text.strip()   # 작성자는 브라우저가 기억한 이름이 있으면 붙고, 없어도 남긴다
    if not text:
        return redirect(back, "내용을 적어 주세요")
    cat = cat if cat in config.NOTE_CAT else "경과"
    n = next((x for x in d.notes if x.id == note_id), None)
    if n:
        if n.text != text:
            n.revs.append((n.at, n.author, n.text))
            n.at, n.author, n.text = _now(), author, text
        return redirect(back, "메모를 고쳤어요. 이전 내용은 이력에 남아요")
    r = acct.result(rid)
    d.notes.insert(0, Note(new_id("note"), _now(), author, cat, text, bool(important), rid=r.id if r and r.dog == d.id else ""))
    return redirect(back, "메모를 남겼어요")


def _vital_from_form(day, kg, temp, hr, sbp, dbp, author) -> Optional[Vital]:
    vals = [x.strip() for x in (kg, temp, hr, sbp, dbp)]
    if not any(vals):
        return None
    return Vital(day or date.today().isoformat(), *vals, author.strip())


@app.post("/dogs/{dog_id}/vitals")
def vital_add(request: Request, dog_id: str, day: str = Form(""), kg: str = Form(""), temp: str = Form(""),
              hr: str = Form(""), sbp: str = Form(""), dbp: str = Form(""), author: str = Form("")):
    acct = current(request)
    if not acct:
        return need_login()
    d = acct.dog(dog_id)
    back = f"/dogs/{dog_id}?tab=vitals"
    if not d:
        return redirect("/home")
    if not author.strip():
        return redirect(back, "작성자를 적어 주세요")
    v = _vital_from_form(day, kg, temp, hr, sbp, dbp, author)
    if not v:
        return redirect(back, "값을 하나 이상 적어 주세요")
    d.vitals.insert(0, v)
    d.vitals.sort(key=lambda x: x.day, reverse=True)
    if v.kg:
        d.kg = v.kg
    return redirect(back, "바이탈을 기록했어요")


@app.post("/dogs/{dog_id}/history")
def history_add(request: Request, dog_id: str, day: str = Form(""), kind: str = Form("진단"), title: str = Form(""),
                site: str = Form(""), by: str = Form(""), stage: str = Form(""), author: str = Form("")):
    """진단·수술·재활 단계 기록. 단계(stage)를 고르면 반려견 단계도 바뀐다."""
    acct = current(request)
    if not acct:
        return need_login()
    d = acct.dog(dog_id)
    back = f"/dogs/{dog_id}?tab=history"
    if not d:
        return redirect("/home")
    if not (author.strip() and title.strip()):
        return redirect(back, "작성자와 내용을 적어 주세요")
    day = day or date.today().isoformat()
    kind = kind if kind in ("진단", "수술", "재활") else "진단"
    d.history.append(History(day, kind, title.strip(), site if site in config.SITE else "", by.strip(), author.strip()))
    d.history.sort(key=lambda h: h.day)
    if stage in config.STAGE and stage != d.stage:
        d.stage, d.stage_day = stage, day
    if kind == "재활" and not d.rehab:
        d.rehab = day
    return redirect(back, "히스토리에 남겼어요")


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
    if next_url.startswith("/upload") or next_url.startswith("/my"):
        return redirect(f"{next_url}{sep}dog={d.id}", f"{d.name} 등록을 마쳤어요")
    return redirect(f"/dogs/{d.id}", f"{d.name} 등록을 마쳤어요")


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
        return redirect(f"/dogs/{dog_id}", f"{r.date} 회차를 기준으로 정했어요")
    return redirect(f"/dogs/{dog_id}")


# ── 영상 업로드 · 분석 ──
@app.get("/upload")
def upload(request: Request, dog: str = "", demo: int = 0):
    acct = current(request)
    if not acct:
        return need_login()
    if not acct.dogs:
        return redirect("/home?modal=pet", "먼저 반려견을 등록해 주세요")
    sel = acct.dog(dog) or acct.dogs[0]
    order = [sel] + [d for d in acct.dogs if d.id != sel.id]   # 고른 반려견을 맨 위에
    dogs = [{"id": d.id, "init": d.name[0], "name": d.name, "no": d.no, "breed": d.breed or "견종 미입력", "kg": d.kg,
             **views.avatar(d.id == sel.id)} for d in order]
    return page(request, "upload.html", acct, nav="upload", dogs=dogs, sel=sel, demo=max(0, min(demo, 16)))


@app.post("/analyze")
def analyze(request: Request, dog: str = Form(...), weight: str = Form(""), demo_count: int = Form(0),
            author: str = Form(""), temp: str = Form(""), hr: str = Form(""), sbp: str = Form(""), dbp: str = Form(""),
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
    job.by = author.strip()
    v = _vital_from_form("", weight, temp, hr, sbp, dbp, author)   # 측정하면서 잰 바이탈은 차트에 바로 남긴다
    if v:
        d = acct.dog(dog)
        d.vitals.insert(0, v)
        d.kg = v.kg or d.kg
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
def result_detail(request: Request, rid: str, type: str = "g"):
    """회차 결과 = 보고서. 결과를 본 화면 그대로 PDF 로 내려받는다(실패한 회차는 다시 찍기 안내)."""
    acct = current(request)
    if not acct:
        return need_login()
    r = acct.result(rid)
    if not r:
        return redirect("/home", "회차를 찾을 수 없어요")
    v = views.result_view(acct, r)
    d = acct.dog(r.dog)
    side = {"panel": views.memo_panel(acct, d, r.id) if d else None, "note_cats": config.NOTE_CAT}
    if r.st == "fail":
        return page(request, "report.html", acct, rd=v["rd"], rp={}, kind="v", bm=None, segs=[], status="", **side)
    kind = type if type in ("g", "v") else "g"
    return page(request, "report.html", acct, rd=v["rd"], rp=v["rp"], kind=kind, bm=views.body_map(acct, r), **side,
                segs=views.seg([("g", "보호자용"), ("v", "수의사용")], kind),
                status=f"분석 모델 {r.model} · 템플릿 1.0")


@app.get("/results/{rid}/report")
def report(rid: str, type: str = "g"):
    """예전 보고서 주소는 회차 결과(= 보고서)로 보낸다."""
    return redirect(f"/results/{rid}?type={type}")


@app.get("/results/{rid}/3d")
def gait_3d(request: Request, rid: str):
    """보호자 설명용 3D 보기: 돌려 보고, 걷는 모습을 재생하고, 덜 쓰는 다리를 색으로 표시한다(동작은 일반 예시)."""
    acct = current(request)
    if not acct:
        return need_login()
    r = acct.result(rid)
    if not r or r.st == "fail":
        return redirect(f"/results/{rid}" if r else "/results", "3D 로 볼 수 없는 회차예요")
    d = acct.dog(r.dog)
    bm = views.body_map(acct, r)
    legs = {k: v for k, v in bm["legs"].items() if len(k) == 2}   # LF·RF·LH·RH (front·hind 는 한 쌍 요약)
    overall = {"sym": bm["sym"], "front": bm["legs"]["front"]["say"], "hind": bm["legs"]["hind"]["say"]}
    model = "assets/dog3d/" + ("husky.glb" if d and d.size == "L" else "shiba.glb")
    return page(request, "gait3d.html", acct, nav="results", rd=views.result_view(acct, r)["rd"], bm=bm, legs=legs,
                overall=overall, model_url=str(request.url_for("static", path=model)),
                # 측정 걸음: 시연용 한 걸음 곡선(tools/build_demo_clip.py, 공개 논문 + 합성). 회사 데이터는 쓰지 않는다
                gait_url=str(request.url_for("static", path="assets/dog3d/gait_demo.json")))


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
        return redirect(f"/dogs/{dog_id}", "유효한 회차가 2개 이상 있어야 비교할 수 있어요")
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
