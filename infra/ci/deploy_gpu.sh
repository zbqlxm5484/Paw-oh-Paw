#!/usr/bin/env bash
# GPU 서버 분석 API 배포 (Jira 239). 사용: bash infra/ci/deploy_gpu.sh <태그|develop>
# 인자가 develop 이면 릴리스 폴더명을 develop-<HEAD 커밋 SHA 8자>로 만든다(develop 머지 자동 배포용).
# 같은 커밋을 다시 돌리면 기존 폴더를 그대로 쓴다.
#
# GPU 서버의 gitlab-runner(shell executor, 태그 gpu-deploy)가 CI 의 deploy_gpu 잡에서 실행한다.
# 러너가 받아 둔 소스(CI_PROJECT_DIR)를 ~/service/releases/<태그>/ 에 복사하고,
# 의존성 설치 → current 링크 교체 → 재시작 → /health 확인 순으로 진행한다.
# 실패하면 이전 버전으로 링크와 프로세스를 되돌리고 비정상 종료한다.
#
# 기준 문서: plan&manual/manual/GPU서버_분석API_배포_가이드.md (4~11절)
# 모델 가중치(~/models/company-orig/)와 환경변수 파일(~/service/env)은 배포가 건드리지 않는다.
set -euo pipefail

TAG="${1:?사용: deploy_gpu.sh <태그|develop>}"

SERVICE_DIR="${SERVICE_DIR:-$HOME/service}"
VENV_DIR="${VENV_DIR:-$HOME/venv/creamoff}"
SRC_DIR="${CI_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

# develop 은 받아 둔 소스의 HEAD 커밋으로 폴더명을 정한다. 그 외는 v* 태그만 허용한다
if [[ "$TAG" == "develop" ]]; then
  SHA="$(git -C "$SRC_DIR" rev-parse HEAD | cut -c1-8)"
  [[ "$SHA" =~ ^[0-9a-f]{8}$ ]] || { echo "ERROR: 커밋 SHA를 읽지 못했다: $SHA" >&2; exit 2; }
  TAG="develop-$SHA"
fi
[[ "$TAG" =~ ^(v[0-9A-Za-z._-]+|develop-[0-9a-f]{8})$ ]] || { echo "ERROR: 허용하지 않는 배포 이름: $TAG" >&2; exit 2; }
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8010/health}"
HEALTH_TRIES="${HEALTH_TRIES:-30}"
TMUX_SESSION="analysis"

REL_DIR="$SERVICE_DIR/releases/$TAG"
CURRENT="$SERVICE_DIR/current"

log() { echo "[deploy_gpu] $*"; }

# 분석 API 프로세스를 내리고 start.sh 를 띄운다. tmux 가 있으면 tmux, 없으면 setsid nohup
restart_service() {
  tmux kill-session -t "$TMUX_SESSION" 2>/dev/null || true
  pkill -f "uvicorn main:app" 2>/dev/null || true
  sleep 1
  if command -v tmux >/dev/null 2>&1; then
    tmux new-session -d -s "$TMUX_SESSION" "$SERVICE_DIR/start.sh"
  else
    setsid nohup "$SERVICE_DIR/start.sh" >/dev/null 2>&1 &
  fi
}

# /health 가 {"status":"ok"} 를 줄 때까지 기다린다
wait_healthy() {
  local i body
  for ((i = 1; i <= HEALTH_TRIES; i++)); do
    body="$(curl -fsS --max-time 3 "$HEALTH_URL" 2>/dev/null || true)"
    if [[ "$body" == *'"status":"ok"'* || "$body" == *'"status": "ok"'* ]]; then
      log "health ok: $body"
      return 0
    fi
    sleep 2
  done
  return 1
}

rollback() {
  if [[ -n "${PREV:-}" && -d "$PREV" ]]; then
    log "롤백: $PREV"
    ln -sfn "$PREV" "$CURRENT"
    restart_service
    if wait_healthy; then
      log "이전 버전($PREV)으로 복구했다"
    else
      log "경고: 이전 버전도 health 확인에 실패했다. 서버에서 직접 확인이 필요하다"
    fi
  else
    log "되돌릴 이전 버전이 없다"
  fi
}

PREV="$(readlink "$CURRENT" 2>/dev/null || true)"
log "배포 이름=$TAG 현재=${PREV:-없음}"

[[ -x "$SERVICE_DIR/start.sh" ]] || { echo "ERROR: $SERVICE_DIR/start.sh 가 없다(가이드 8절)" >&2; exit 1; }
[[ -f "$SERVICE_DIR/env" ]] || { echo "ERROR: $SERVICE_DIR/env 가 없다(가이드 7절)" >&2; exit 1; }
[[ -x "$VENV_DIR/bin/python" ]] || { echo "ERROR: $VENV_DIR 가 없다" >&2; exit 1; }

# 1) 소스 복사. 이미 같은 태그 폴더가 있으면 지우지 않고 덮어쓰지 않는다(이전 버전 보존)
if [[ -d "$REL_DIR" ]]; then
  log "이미 있는 릴리스를 그대로 쓴다: $REL_DIR"
else
  mkdir -p "$REL_DIR"
  git -C "$SRC_DIR" archive HEAD | tar -x -C "$REL_DIR"
  log "소스 복사: $REL_DIR"
fi

# 2) 의존성 설치. torch·mmcv 등은 건드리지 않는 requirements 만 설치한다. pip 는 반드시 python -m pip
"$VENV_DIR/bin/python" -m pip install -q -r "$REL_DIR/analysis_api/requirements.txt"

# 3) 링크 교체 후 재시작, health 확인. 실패하면 이전 버전으로 복구
ln -sfn "$REL_DIR" "$CURRENT"
restart_service
if wait_healthy; then
  log "배포 완료: $TAG"
else
  log "ERROR: health 확인 실패. 로그: $SERVICE_DIR/logs/analysis.log"
  tail -n 20 "$SERVICE_DIR/logs/analysis.log" 2>/dev/null || true
  rollback
  exit 1
fi
