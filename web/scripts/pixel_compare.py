"""웹 시제품(prototype, :8002 = proto_for_compare.py)과 React 웹(web, :5174 --mode mock)을 같은 화면끼리 찍어 픽셀을 견준다.

    python web/scripts/pixel_compare.py [--out <폴더>] [주소 ...]

- 두 서버가 같은 날 같은 시연 데이터(prototype/tools/export_web_fixture.py)를 써야 한다.
- 로그인은 양쪽 다 로그인 화면의 "시연용 예시 기관으로 둘러보기"를 누른다.
- 화면마다 전체 페이지 스크린샷 2장과 차이 그림(다른 픽셀을 빨갛게)을 남기고, 다른 픽셀 수·비율을 출력한다.
- 3D 화면은 WebGL 그림이 매번 달라 캔버스를 가리고 견준다.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

PROTO, WEB = "http://127.0.0.1:8002", "http://localhost:5174"   # 8002 = web/scripts/proto_for_compare.py(회사 데이터 뺀 시제품)
ROUTES = ["/", "/about", "/login", "/signup", "/forgot", "/reset-password?token=x", "/expired?demo=1", "/admin?demo=1",
          "@login", "/home", "/home?view=analyses", "/home?view=dogs", "/home?view=staff", "/home?view=dogs&changed=1",
          "/dogs/d1", "/dogs/d1?tab=progress", "/dogs/d1?tab=dx", "/dogs/d4", "/dogs/d2", "/upload", "/results", "/results/r1",
          "/results/r1?type=v", "/results/r2", "/results/r3", "/results/r1/3d", "/compare/d1", "/my", "/account"]
MASK_JS = "document.querySelectorAll('canvas').forEach(c => c.style.visibility = 'hidden')"
FREEZE_CSS = "*, *::before, *::after { transition: none !important; animation: none !important; caret-color: transparent !important; }"


def shoot(page, base, route, out):
    page.goto(base + route)
    page.wait_for_load_state("networkidle")
    page.add_style_tag(content=FREEZE_CSS)
    page.evaluate(MASK_JS)
    page.evaluate("document.getElementById('toast') && (document.getElementById('toast').style.display = 'none')")
    page.wait_for_timeout(400)
    page.screenshot(path=str(out), full_page=True)


def diff(a, b, out):
    A, B = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if A.size != B.size:
        w, h = max(A.width, B.width), max(A.height, B.height)
        A2, B2 = Image.new("RGB", (w, h), "white"), Image.new("RGB", (w, h), "white")
        A2.paste(A), B2.paste(B)
        A, B = A2, B2
    d = ImageChops.difference(A, B).convert("L").point(lambda v: 255 if v > 0 else 0)
    n = sum(1 for v in d.getdata() if v)
    over = A.copy()
    over.paste((230, 30, 30), mask=d)
    over.save(out)
    return n, A.width * A.height


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="web/scripts/pixel_out")
    ap.add_argument("routes", nargs="*")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    routes = a.routes or ROUTES
    rows = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--font-render-hinting=none"])
        pages = {k: b.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1).new_page() for k in ("proto", "web")}
        for r in routes:
            if r == "@login":
                for k, base in (("proto", PROTO), ("web", WEB)):
                    pg = pages[k]
                    pg.goto(base + "/login")
                    pg.click("text=시연용 예시 기관으로 둘러보기")
                    pg.wait_for_load_state("networkidle")
                continue
            name = r.strip("/").replace("/", "_").replace("?", "__").replace("&", "_").replace("=", "-") or "root"
            fa, fb, fd = out / f"{name}.proto.png", out / f"{name}.web.png", out / f"{name}.diff.png"
            try:
                shoot(pages["proto"], PROTO, r, fa)
                shoot(pages["web"], WEB, r, fb)
                n, tot = diff(fa, fb, fd)
                sa, sb = Image.open(fa).size, Image.open(fb).size
                rows.append((r, n, tot, sa, sb))
                print(f"{'OK ' if n == 0 else 'DIFF'} {r:32s} {n:>9d} px ({n / tot * 100:6.3f}%)  proto {sa} web {sb}", flush=True)
            except Exception as e:  # 한 화면이 실패해도 나머지는 견준다
                print(f"ERR  {r:32s} {e}", flush=True)
        b.close()
    bad = [r for r in rows if r[1]]
    print(f"\n{len(rows) - len(bad)}/{len(rows)} 화면 픽셀 동일")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
