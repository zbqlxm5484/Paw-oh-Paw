# 분석 API 견본 응답

팀 서비스가 분석 API 없이 Mock으로 개발할 때 쓰는 견본이다. 값은 지어낸 것이고, 형식만 실제와 같다.
형식 근거: 「분석 API 형식과 구현 계획」(10-21), 「분석 API 초안 검토 답변」(10-22)

| 파일 | 어떤 응답 | 상황 |
| --- | --- | --- |
| `result_partial.json` | `GET /analyses/{id}/result` | 통과 3번 중 2번 사용, 1번 제외(`PARTIAL_PASS`). 2번 통과의 뒷발 들림은 측정 불가 |
| `result_invalid.json` | `GET /analyses/{id}/result` | 영상에 개가 없어 무효(`NO_DOG`). 분석은 완료(`done`) |
| `status_failed.json` | `GET /analyses/{id}` | 영상을 읽지 못해 분석 실패(`DECODE_FAILED`) |
| `keypoints.json` | `GET /analyses/{id}/files/keypoints` | 3프레임만 줄인 관절점 파일. 마지막 프레임은 개 없음 |

## 읽는 법

- 실패(`failed`)는 다시 분석, 무효(`invalid`)는 다시 촬영으로 안내한다
- `metrics` 키에는 `_l`·`_r`가 없다. 어느 쪽 다리인지는 그 통과의 `camera_side`로 정해진다
- 측정 불가 수치는 0이 아니라 `{"value": null, "reason": "..."}`로 온다
- 제외된 통과와 보행 수치 계산 전 단계(10-31 이전)에서는 `metrics`가 `{}`로 온다
- 관절점 파일은 프레임마다 `camera_side`를 둔다. 촬영 한 건에 방향이 다른 통과가 섞일 수 있어서다
- 프레임 번호를 시각으로 바꿀 때는 파일의 `fps`를 쓴다 (60, 59.94, 30이 섞여 있다)

## 아직 확정되지 않은 것

검토 답변 4절의 "답 기다림" 항목이 정해지면 견본도 고친다.

- 엎드리기 사유 코드 (`SITTING`에 포함 또는 `LYING` 추가)
- `validity_reason` 규칙, `model.version`의 가중치 해시
- 앞·뒷발 접미사(`_front`·`_hind`), `stifle_cycle_rom`, 발 경사(`paw_slope_median_*`)
