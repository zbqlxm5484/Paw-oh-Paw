#!/usr/bin/env bash
# 무중단(blue-green) 배포. 쉬고 있는 색을 새 코드로 띄워 헬스체크를 통과하면 nginx 를 전환하고 이전 색을 내린다.
# 실패하면 이전 색이 그대로 서비스 중이라 자동 원복(새 색만 정리)된다.
# 환경변수: COMPOSE_PROJECT(기본 creamoff), COMPOSE_EXTRA(예: "-f infra/ci/compose.ci.yaml"), PUBLIC_URL(기본 http://127.0.0.1:8080)
set -euo pipefail

P="${COMPOSE_PROJECT:-creamoff}"
PUBLIC_URL="${PUBLIC_URL:-http://127.0.0.1:8080}"
# shellcheck disable=SC2206
C=(docker compose -p "$P" -f compose.yaml ${COMPOSE_EXTRA:-})

log() { echo "[deploy] $*"; }

write_active() {   # $1=blue|green → nginx 볼륨의 active.conf 갱신
  printf 'upstream api_backend { server api-%s:8000; }\nupstream web_backend { server web-%s:80; }\n' "$1" "$1" \
    | "${C[@]}" exec -T nginx sh -c 'cat > /etc/nginx/upstream/active.conf'
}

# 1. 인프라(postgres·redis·gotenberg·nginx) 준비. nginx 컨테이너만 만들어 두고 active.conf 가 없으면 blue 로 초기화
"${C[@]}" up -d --wait postgres redis gotenberg
"${C[@]}" up --no-start nginx
NGINX_CID="$("${C[@]}" ps -aq nginx)"
docker run --rm --volumes-from "$NGINX_CID" --entrypoint sh nginx:stable-alpine -c \
  '[ -f /etc/nginx/upstream/active.conf ] || printf "upstream api_backend { server api-blue:8000; }\nupstream web_backend { server web-blue:80; }\n" > /etc/nginx/upstream/active.conf'

# 2. 지금 서비스 중인 색 → 새로 띄울 색(첫 배포면 active=blue 로 보고 green 을 띄운다)
ACTIVE="$(docker run --rm --volumes-from "$NGINX_CID" --entrypoint sh nginx:stable-alpine -c 'cat /etc/nginx/upstream/active.conf' | sed -n 's/.*api-\(blue\|green\).*/\1/p' | head -1)"
ACTIVE="${ACTIVE:-blue}"
if [ "$ACTIVE" = blue ]; then NEW=green; else NEW=blue; fi
log "active=$ACTIVE new=$NEW"

# 첫 배포(nginx 가 아직 안 떠 있음)면 active 색이 없으므로 새 색이 곧 첫 서비스 색
FIRST=0
if [ -z "$("${C[@]}" ps -q nginx)" ]; then FIRST=1; NEW=blue; ACTIVE=none; log "first deploy → new=blue"; fi

# 3. 새 색 빌드 → DB 마이그레이션 → 기동(헬스체크 통과까지 대기). 여기서 실패하면 새 색만 내리고 끝낸다(이전 색은 그대로 서비스 중)
trap 'rc=$?; [ $rc -ne 0 ] && { log "실패(rc=$rc) → 새 색($NEW) 정리"; "${C[@]}" stop "api-$NEW" "web-$NEW" || true; }' EXIT
"${C[@]}" build "api-$NEW" "web-$NEW"
"${C[@]}" run --rm --no-deps "api-$NEW" alembic upgrade head
"${C[@]}" up -d --no-deps --wait --wait-timeout 120 "api-$NEW" "web-$NEW"

# 4. 전환
if [ "$FIRST" = 1 ]; then
  docker run --rm --volumes-from "$NGINX_CID" --entrypoint sh nginx:stable-alpine -c \
    "printf 'upstream api_backend { server api-blue:8000; }\nupstream web_backend { server web-blue:80; }\n' > /etc/nginx/upstream/active.conf"
  "${C[@]}" up -d nginx
else
  write_active "$NEW"
  if ! "${C[@]}" exec -T nginx nginx -t || ! "${C[@]}" exec -T nginx nginx -s reload; then
    log "nginx 전환 실패 → 원복"; write_active "$ACTIVE"; "${C[@]}" stop "api-$NEW" "web-$NEW"; exit 1
  fi
fi

trap - EXIT   # 이후 단계는 아래에서 직접 원복을 처리한다
# 5. 공개 주소로 최종 확인. 실패하면 이전 색으로 되돌리고 새 색을 내린다
ok=0
for _ in $(seq 1 15); do
  if curl -fsS "$PUBLIC_URL/api/v1/health" >/dev/null && curl -fsS "$PUBLIC_URL/" >/dev/null; then ok=1; break; fi
  sleep 2
done
if [ "$ok" != 1 ]; then
  log "전환 후 확인 실패 → 이전 색($ACTIVE)으로 원복"
  if [ "$ACTIVE" != none ]; then write_active "$ACTIVE"; "${C[@]}" exec -T nginx nginx -s reload; fi
  "${C[@]}" logs --tail=50 "api-$NEW" || true
  "${C[@]}" stop "api-$NEW" "web-$NEW"
  exit 1
fi

# 5-1. worker 재생성. 한 대만 두므로 blue/green 없이 api 전환·확인이 끝난 뒤 새 코드로 갈아 끼운다.
# 멈춘 사이 촬영 상태는 DB에 있어 재기동하면 하던 일이 이어진다. 기동 직후 죽어 있으면 배포 실패로 본다(api 는 이미 전환됨)
"${C[@]}" build worker
"${C[@]}" up -d --no-deps worker
sleep 5
WCID="$("${C[@]}" ps -q --status running worker)"
# restart: unless-stopped 라 죽고 다시 뜨는 반복(크래시 루프)이면 running 으로 보일 수 있어 재시작 횟수도 본다
if [ -z "$WCID" ] || [ "$(docker inspect -f '{{.RestartCount}}' "$WCID")" != 0 ]; then
  log "worker 기동 실패"; "${C[@]}" logs --tail=50 worker || true; exit 1
fi

# 6. 이전 색 정리. 진행 중인 요청이 끝날 때까지 기다린 뒤 내린다(컨테이너·이미지는 남겨 둬 빠른 원복 가능)
if [ "$ACTIVE" != none ]; then
  "${C[@]}" stop -t 130 "api-$ACTIVE" "web-$ACTIVE"
fi
# 구버전 compose 의 옛 서비스(api, frontend)가 남아 있으면 정리(최초 전환 때만 해당)
"${C[@]}" up -d --no-recreate --remove-orphans nginx >/dev/null
docker image prune -f >/dev/null
log "done. active=$NEW"
