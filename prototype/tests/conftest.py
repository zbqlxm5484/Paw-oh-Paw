import sys
from pathlib import Path

import pytest

# 저장소 루트에서 pytest를 돌려도 prototype/ 안의 proto_app을 찾게 한다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 프로토타입 의존성이 없는 환경에서는 건너뛴다.
for mod in ("fastapi", "jinja2", "multipart", "httpx"):
    pytest.importorskip(mod)
