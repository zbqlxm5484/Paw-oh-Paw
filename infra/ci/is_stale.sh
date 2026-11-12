#!/usr/bin/env bash
# develop 배포 job 이 더 새로운 커밋이 생긴 뒤에 뒤늦게 도는 경우를 걸러낸다.
# 순서가 뒤집혀 오래된 코드가 나중에 배포되면, 이미 올라간 DB 마이그레이션 번호를 코드가 못 찾아 실패한다(Jira 230).
# 종료코드: 0 = 오래된 커밋(배포 건너뜀), 1 = 최신 커밋이거나 판단 불가(배포 진행)
set -u

[ "${CI_COMMIT_BRANCH:-}" = develop ] || exit 1   # master 수동 배포 등은 검사하지 않는다

latest="$(git ls-remote origin refs/heads/develop 2>/dev/null | cut -f1)"
if [ -z "$latest" ]; then
  echo "[stale-check] develop 최신 커밋을 못 읽어 검사 없이 배포를 진행한다"
  exit 1
fi

if [ "$latest" != "${CI_COMMIT_SHA:-}" ]; then
  echo "[stale-check] 이 커밋(${CI_COMMIT_SHA:-?})보다 새 커밋($latest)이 develop 에 있다 → 배포를 건너뛴다(새 커밋 파이프라인이 배포한다)"
  exit 0
fi
exit 1
