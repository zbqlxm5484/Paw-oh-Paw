# 팀 서버 배포 점검 기록 (2026-11-04)

티켓 S15P31A404-199(중간 검수 백엔드 배포 점검)의 기록이다. 백엔드 담당(조영운)이 develop의 배포 파일과 팀 서버 응답을 읽고 적었다. 서버와 배포 파일은 손대지 않았다. 배포·인프라는 허정원 담당이라 아래 "고칠 것"은 허정원의 배포 티켓으로 넘겼다(조유진 MR !92 리뷰, 11-04).

## 확인한 방법

- 팀 서버에 HTTP로 `/api/v1/health`와 `/web/`를 불러 응답을 본다(읽기만).
- develop의 `compose.yaml`, `backend/Dockerfile`, `infra/ci/deploy.sh`를 읽는다.

## 확인한 것

| 항목 | 결과 |
| --- | --- |
| `/api/v1/health` (HTTP) | 200 `{"status":"ok","db":"ok","storage":"ok","version":"1.0.0"}` |
| `/web/` (HTTP) | 200 |
| HTTPS | 연결 실패. 티켓 224(HTTPS 접속 추가)에서 다룬다 |
| `compose.yaml` 서비스 | nginx, api-blue·api-green, web-blue·web-green, postgres, redis. **워커 서비스가 없다** |
| `backend/Dockerfile` | ffmpeg만 설치한다. Pango와 한글 글꼴이 없다 |
| `infra/ci/deploy.sh` | 새 색에서 `alembic upgrade head`만 돌린다. 첫 관리자 seed 단계는 없다(배포 서버에는 허정원이 `python -m scripts.seed`로 ADMIN 둘을 만들어 두었다) |
| 파일 볼륨 | 두 색(blue·green)이 `api-data:/data/files` 볼륨을 같이 본다 |

## 뜻

- 워커가 없어 서버에서는 업로드까지만 된다. 분석 제출·회차 집계·결과 영상·보고서는 돌지 않는다.
- WeasyPrint가 쓰는 Pango(`libpango-1.0-0`, `libpangoft2-1.0-0`)와 한글 글꼴(`fonts-nanum`)이 이미지에 없어, 워커를 띄워도 보고서 PDF가 만들어지지 않는다.
- 두 색이 같은 볼륨을 보므로 파기 API·스크립트가 지우는 파일은 두 색 모두에서 사라진다. 파기를 어느 색에서 돌려도 결과가 같다.

## 고칠 것 (허정원 배포 티켓으로 넘김)

1. compose에 워커 서비스를 **한 대** 넣는다. blue·green 두 벌이 아니다. 워커는 한 대를 전제로 만든 부분이 있다(명세 12.4 잠금, 보고서 워커의 `_release_orphans`).
2. `backend/Dockerfile`에 Pango와 한글 글꼴을 넣는다.
3. 과제 종료 때 서버에서 돌릴 전체 파기 명령을 정한다. api 이미지로 돌리면 `.env`의 `DATABASE_URL`·`STORAGE_ROOT`를 그대로 쓴다.

   ```bash
   docker compose … run --rm --no-deps api-<색> python -m scripts.purge --all            # 지울 양만 센다
   docker compose … run --rm --no-deps api-<색> python -m scripts.purge --all --execute  # 확인 문구를 묻고 지운다
   ```

분석 API도 워커 1개와 `/data/analysis_api` 볼륨 조건이 있어 같은 티켓에 묶는다(조유진).

## 이번에 못 한 것

- 193의 서버 렌더 시간 재측정, 189의 기업 분석 API 주소 전환: 서버에 워커가 없고 기업 GPU 서버 접근도 없어 하지 못했다.
- KPI-29(두 판본 20초)의 서버 측정: 워커가 생긴 뒤 `python -m scripts.report_samples <폴더> --pool`로 다시 잰다(로컬 측정은 `docs/report/reportTiming.md`, 티켓 200).
- 분석 API 저장소의 사본 파기: 팀 서비스 파기 뒤에도 분석 API 쪽 작업 폴더와 기록이 남는다. 분석 API에 지우는 기능이 생긴 뒤 팀 서비스 파기에서 부르는 일은 다음 티켓이다(조유진 리뷰).
