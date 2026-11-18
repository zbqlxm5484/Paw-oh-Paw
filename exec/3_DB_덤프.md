# 3. DB 덤프

| 항목 | 값 |
| --- | --- |
| DB | PostgreSQL 17 |
| 덤프 파일 | `exec/creamoff_dump.sql` (약 1.4MB, 평문 SQL) |
| 뜬 곳 | 운영 DB (compose 프로젝트 `creamoff`) |
| 뜬 때 | 2026-11-18 14:20 |
| 마이그레이션 | `0023` |
| 들어 있는 것 | 표 15개의 구조와 값. 기관 8, 계정 13, 반려견 17, 회차 88, 촬영 1,067, 보고서 174 |

## 덤프 뜨기

팀 서버에서 돌린다.

```bash
docker exec creamoff-postgres-1 sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges' > creamoff_dump.sql
```

## 복원하기

빈 DB에 넣는다. postgres 컨테이너만 먼저 띄운 뒤 돌린다.

```bash
docker compose -p creamoff -f compose.yaml up -d --wait postgres
docker exec -i creamoff-postgres-1 sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' < exec/creamoff_dump.sql
bash infra/ci/deploy.sh
```

- 덤프에는 `alembic_version` 표가 들어 있다. `deploy.sh`가 그 뒤의 마이그레이션만 이어서 적용한다.
- 덤프에는 DB의 값만 있다. 영상, 결과 영상, 보고서 PDF는 Docker 볼륨 `api-data`에 따로 있어서, 덤프만 복원하면 그 파일을 여는 자리가 비어 보인다.
- 덤프 없이 시작해도 된다. `deploy.sh`가 빈 DB에 표를 만든다. 그 뒤 관리자 계정을 만들고(1.3) 시연 데이터를 넣는다.
