"""분석 API 테스트 공통 설정.

- 테스트 클라이언트 하나를 세션 동안 열어 둔다. 열지 않고 쓰면 요청마다 이벤트 루프를 새로 만들고, Windows에서는 루프마다
  내부 소켓 한 쌍(socketpair)을 연다. 이것이 짧은 시간에 수백 번 일어나면 보안 프로그램 등 때문에 가끔
  WinError 10014로 실패한다(테스트마다 무작위로). 한 번 열어 두면 루프를 한 번만 만든다
- 저장소를 임시 폴더로 둔다. 클라이언트를 열 때 서버 시작 처리(끊긴 작업 정리)가 돌므로, 실제 data/analysis_api를
  건드리지 않게 한다. 테스트마다는 각 파일의 fixture가 다시 임시 폴더로 바꾼다
"""
import os
import tempfile

os.environ["ANALYSIS_STORAGE_DIR"] = tempfile.mkdtemp(prefix="analysis_api_test_")
os.environ.pop("ANALYSIS_DOCS_ENABLED", None)   # 개발 PC에 켜져 있어도 테스트는 배포 기본(닫힘)으로 돈다

import main  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(main.app)


@pytest.fixture(scope="session", autouse=True)
def _open_client():
    with client:
        yield
