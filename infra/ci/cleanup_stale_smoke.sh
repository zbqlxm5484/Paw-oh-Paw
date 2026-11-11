#!/usr/bin/env bash
# 이전 smoke 가 중간에 죽어 after_script(down)가 안 돌았을 때 남은 ci-<파이프라인ID> compose 프로젝트를 정리한다.
# 남은 nginx 가 호스트 포트를 잡고 있으면 이후 smoke 가 전부 "port is already allocated" 로 실패하기 때문이다.
# 지금 도는 다른 smoke 를 건드리지 않게, 가장 오래된 컨테이너가 STALE_MIN(기본 30분)보다 오래된 프로젝트만 지운다.
set -uo pipefail

STALE_MIN="${STALE_MIN:-30}"
now="$(date +%s)"

docker ps -a --format '{{.ID}}' --filter 'label=com.docker.compose.project' | while read -r cid; do
  proj="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$cid")"
  [[ "$proj" =~ ^ci-[0-9]+$ ]] || continue
  created="$(docker inspect -f '{{.Created}}' "$cid")"
  age=$(( (now - $(date -d "$created" +%s)) / 60 ))
  [ "$age" -ge "$STALE_MIN" ] && echo "$proj"
done | sort -u | while read -r proj; do
  echo "[cleanup] 남은 smoke 프로젝트 정리: $proj"
  COMPOSE_PROFILES=bluegreen docker compose -p "$proj" -f compose.yaml -f infra/ci/compose.ci.yaml down -v --remove-orphans || true
done
exit 0
