#!/bin/sh
# reproduce 잡 본체 (.gitlab-ci.yml). 기업 검수 절차(새 venv → 설치 → 실행)를 서비스마다 따로 재현한다.
# 서비스마다 requirements가 따로 있고 버전이 달라서(backend/analysis_api/prototype), 한 venv에 겹쳐 깔면 뒤에 깐 핀이 앞의 핀을 덮어쓴다.
# 설치나 pip check, 테스트가 하나라도 실패하면 잡이 실패한다.
set -e

# check 이름 요구파일 [테스트를 돌릴 폴더]
check() {
  name=$1
  req=$2
  testdir=$3
  if [ ! -f "$req" ]; then
    echo "== $name: $req 없음, 건너뜀"
    return 0
  fi
  echo "== $name: $req"
  venv="/tmp/venv-$name"
  python -m venv "$venv"
  "$venv/bin/pip" install -q -r "$req"
  "$venv/bin/pip" check
  if [ -n "$testdir" ]; then
    (cd "$testdir" && "$venv/bin/python" -m pytest -q -p no:cacheprovider)
  fi
}

check root requirements-dev.txt .
# backend 테스트는 postgres가 필요해 여기서 돌리지 않는다(매뉴얼 2-10 backend-test 잡). 설치와 pip check만 본다
check backend backend/requirements.txt
check analysis_api analysis_api/requirements-dev.txt analysis_api
check prototype prototype/requirements-dev.txt prototype
