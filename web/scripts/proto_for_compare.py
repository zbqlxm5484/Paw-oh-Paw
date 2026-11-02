"""픽셀 비교용 웹 시제품(:8002). 회사 데이터(company_sample.json)를 빼고 띄워 web/src/mocks/fixture.json 과 같은 데이터가 되게 한다.

    python web/scripts/proto_for_compare.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "prototype"))

from proto_app import real  # noqa: E402

real.REAL_FILES = [real.ASSETS / "demo_sessions.json"]
real.sessions.cache_clear()

import uvicorn  # noqa: E402

from proto_app.main import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="warning")
