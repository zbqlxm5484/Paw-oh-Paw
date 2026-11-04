# 분석 결과 JSON v1

작성 조유진 · 11-02 · S15P31A404-178 · 견본 `analysis_api/samples/`

분석 API가 내는 결과 JSON과 관절점 파일의 형식이다. 팀 서비스(`backend/app/clients/analysis.py`, `backend/app/services/analysis_results.py`)와 기업 연동의 기준이다. 「분석 API 형식과 구현 계획」(10-21), 「분석 API 초안 검토 답변」(10-22)에서 정한 것을 v1로 확정한다.

## 0. 초안(v0.2)에서 바뀐 것

검토 답변 4절에서 "답 기다림"이던 항목을 이렇게 정했다.

| 항목 | v1 |
| --- | --- |
| 엎드리기 사유 | `SITTING`에 포함. `LYING`은 두지 않는다 (백엔드 명세 14.3) |
| `validity_reason` | 유효 판별 규칙 v1 4.2절대로 (`docs/engine/validityRules.md`, `engine/validity.py`) |
| `model.version` | `{분석 API 버전}/{각도 정의}/{가중치 해시 앞 8자}` (예: `0.4.0/v1/a4261a10`) |
| 수치 키 | 앞·뒷발 접미사 `_front`·`_hind`, `stifle_cycle_rom`, `paw_slope_median_*` 그대로 (견본·백엔드 fixtures와 같음) |
| 측정 구간 | 통과마다 `measure_start`·`measure_end` 추가 (첫 착지부터 마지막 이지, 기업 판별 기준 문서 1절) |
| 엔진 버전 | 최상위 `versions` 추가 (각도 정의·착지 검출·유효 판별 버전) |
| 판단 근거 | 통과마다 `checks` 추가 (진단용. 화면에는 쓰지 않는다) |
| 관절점 파일 | 프레임마다 `camera_side`. `frame`은 0부터, 원본을 처음부터 읽은 순서 |

**v1 안에서는 필드를 빼거나 뜻을 바꾸지 않는다.** 필드를 더하는 것은 v1 안에서 하고, 팀 서비스는 모르는 필드를 무시한다.

## 1. 결과 JSON (`GET /analyses/{id}/result`)

```json
{
  "id": "7c1f3a52-9d4e-4b8a-a2f1-0c6e5b9d1a77",
  "shot_id": "sample-shot-001",
  "status": "done",
  "model": {"name": "fs-v4", "version": "0.4.0/v1/a4261a10", "angle_def": "v1", "weights_sha256": "a4261a10..."},
  "versions": {"angle_def": "v1", "gait_events": "v1", "validity": "v1"},
  "input": {"filename": "shot.mp4", "codec": "h264", "fps": 59.94, "width": 1920, "height": 1080, "frames": 642},
  "validity": "partial",
  "validity_reason": null,
  "summary": {"passes": 3, "used": 2, "excluded": 1},
  "passes": [ ... 2절 ... ],
  "files": {"keypoints": "/analyses/7c1f3a52-.../files/keypoints"},
  "created_at": "2026-11-02T15:20:31+09:00"
}
```

| 필드 | 형식 | 뜻 | 근거 |
| --- | --- | --- | --- |
| `id` | 문자열 | 작업 ID. 형식을 해석하지 않는다 (지금은 UUID) | 검토 답변 Q2 |
| `shot_id` | 문자열·null | 등록할 때 `meta`로 받은 값을 그대로 | |
| `model.name`·`model.version` | 문자열 | 팀 서비스가 `shot.model_name`·`model_version`(각 50자)에 저장. 다르면 회차 비교에서 MODEL_CHANGED | PR-F07-05, REQ-OP-006 |
| `model.weights_sha256` | 문자열·null | 가중치 전체 해시. JSON 원본에만 남긴다. 분석 API에 가중치 해시(`ANALYSIS_WEIGHTS_SHA256`)를 넣지 않았으면 null이고, `model.version` 끝은 `unknown`이다 | |
| `versions` | 객체 | 엔진 부분별 정의 버전(`angle_def`, `gait_events`, `validity`, `gait_metrics`, `joint_rom`). 정의가 다른 결과끼리 비교하지 않기 위해. `gait_metrics`는 #183, `joint_rom`은 #184(11-04)에 더함 | |
| `input` | 객체 | 입력 영상 사양 | PR-F07-05 |
| `validity` | `valid`·`partial`·`invalid` | 촬영 판정 | F-03 |
| `validity_reason` | 사유 코드·null | 4절 | PR-F03-05 |
| `summary` | `{passes, used, excluded}` | 몇 번 측정, 몇 번 사용, 몇 번 제외 | REQ-VT-002 |
| `created_at` | ISO 8601 (+09:00) | | |

견본 모델로 만든 결과는 `model.name`이 `sample-pipeline`이다. 실제 결과와 섞이지 않는다.

## 2. 통과 (`passes[]`)

```json
{
  "index": 1, "start_frame": 40, "end_frame": 205,
  "heading": "right", "camera_side": "right", "gait": "trot",
  "valid": true, "reason_code": null, "reason": null,
  "measure_start": 52, "measure_end": 191,
  "metrics": { ... 3절 ... },
  "checks": {"speed_body_per_s": 7.4, "lateral_phase": 0.47, "side_view_ratio": 1.0, "inside_s": 0.8, "found": []}
}
```

| 필드 | 형식 | 뜻 |
| --- | --- | --- |
| `index` | 1부터 | 통과 번호 |
| `start_frame`·`end_frame` | 0부터, 끝 포함 | 통과 구간 |
| `heading` | `right`·`left` | 머리가 화면 어느 쪽을 향했나 |
| `camera_side` | `right`·`left` | 카메라 쪽 다리. 수치는 이쪽 다리만 (PR-F02-04) |
| `gait` | `walk`·`trot`·`pace`·`other`·null | 보행 유형. null은 아직 판별 못 함(이 경우 제외하지 않는다) |
| `valid` | 참·거짓 | 이 통과를 수치에 쓰나 |
| `reason_code`·`reason` | 사유 코드와 문장·null | 뺀 이유. 화면은 코드로, 보고서·로그는 문장으로 (PR-F03-04) |
| `measure_start`·`measure_end` | 프레임·null | 측정 구간(첫 착지부터 마지막 이지). 착지를 못 찾으면 null. 수치는 이 구간에서 낸다: 걸음 길이·입각기 비율은 착지 사이 주기라 구간 안이고, 보행 속도도 이 구간의 몸통 속도다. 가동 범위·각도 중앙값은 이 구간이 아니라 통과에서 몸 전체가 보인 프레임 전부로 잰다(재측정 차가 같거나 작고 모든 통과에서 값이 나옴, `docs/engine/jointRom.md` 4절). 관절점은 몸 전체가 화면 안에 보인 프레임만 쓴다 |
| `metrics` | 객체 | 3절. 제외된 통과와 수치 계산 전에는 `{}` |
| `checks` | 객체 | 판단 근거(속도, 같은 쪽 앞·뒷발 위상, 옆모습 비율, 몸 전체가 보인 시간, 걸린 사유 목록). **진단용이라 키가 바뀔 수 있다.** 화면·저장에 쓰지 않는다 |

## 3. 수치 (`passes[].metrics`)

값은 `{"value": 41.8, "unit": "deg"}`, 측정 불가는 `{"value": null, "reason": "LOW_CONFIDENCE"}`다. 0으로 내지 않는다(PR-F02-05). 다리는 그 통과의 `camera_side` 쪽이라 키에 `_l`·`_r`가 없다.

| 키 | 단위 | 뜻 |
| --- | --- | --- |
| `rom_shoulder`·`rom_elbow`·`rom_carpus`·`rom_hip`·`rom_stifle`·`rom_tarsus` | `deg` | 관절 가동 범위 (5에서 95 백분위 폭, 몸 전체가 보인 프레임 전부. `docs/engine/jointRom.md`) |
| `angle_median_<관절>` | `deg` | 위 6개 관절 각도의 중앙값 |
| `paw_slope_median_front`·`_hind` | `deg` | 발 경사 중앙값. **JSON 원본에만 남고 팀 서비스는 저장하지 않는다** (기업 세부명세서 6.2.1 회차 수치에 없음, MR !65 리뷰 11-02) |
| `paw_lift_front`·`_hind` | `pct_body` | 발 높이(최대 들림) |
| `paw_excursion_front`·`_hind` | `pct_body` | 발 움직임 범위 |
| `stride_length_front`·`_hind` | `pct_body` | 걸음 길이 |
| `stance_ratio_front`·`_hind` | `pct` | 입각기 비율 |
| `walk_speed` | `body_per_sec` | 보행 속도 |
| `gait_cycles` | `count` | 측정된 보행 주기 수 |
| `stifle_cycle_rom` | `{"values": [...], "unit": "deg"}` | 주기별 무릎 가동 범위. 회차 무릎 움직임 일관성(`stifle_cv`)은 팀 서비스가 이것으로 계산 |

- 몸통 길이는 T13과 장골능 사이 거리(명세서 용어 정의)다. 문헌 기준(어깨뼈 위끝과 고관절)과 비교할 때는 1.92를 곱한다
- 좌우 차이·대칭 지수와 회차 집계는 팀 서비스가 한다
- `NO_PASS_FOR_LIMB`는 회차 수준이라 팀 서비스가 붙인다. 분석 API는 `NOT_ENOUGH_CYCLES`, `LOW_CONFIDENCE`를 쓴다

## 4. 사유 코드

백엔드 명세(`backend/docs/backend-spec.md`) 14.3과 같다.

| 어디에 | 코드 |
| --- | --- |
| `validity_reason` | `NO_DOG`, `MAT_NOT_FOUND`, `NO_VALID_PASS`, 기업 무효 사유가 붙은 통과의 `reason_code`(아래), `FEW_VALID_PASSES`(`partial`일 때만) |
| `passes[].reason_code` | `NO_DOG`, `OCCLUDED`, `OVERLAP`, `NOT_SIDE_VIEW`, `PARTIAL_PASS`, `TOWARD_CAMERA`, `NORMALIZATION_LIMIT`, `TURNED`, `SITTING`, `STOPPED`, `RUNNING`, `GAIT_PACE`, `GAIT_OTHER` |
| `metrics.*.reason` | `NOT_ENOUGH_CYCLES`, `LOW_CONFIDENCE` |

기업 무효 사유(이 중 하나가 붙은 통과가 있으면 촬영 전체 `invalid`): `GAIT_PACE`, `RUNNING`, `TURNED`, `STOPPED`, `SITTING`, `PARTIAL_PASS`, `OVERLAP`.

분석 실패(`status: failed`)는 결과가 아니라 상태 조회의 `error.code`로 온다: `DECODE_FAILED`(영상을 읽지 못함), `POSE_UNAVAILABLE`(이 영상의 관절점을 얻지 못함), `INTERRUPTED`(분석 중에 분석 API가 다시 시작됨), `INTERNAL`. 실패는 다시 분석, 무효는 다시 촬영으로 안내한다.

## 5. 관절점 파일 (`GET /analyses/{id}/files/keypoints`)

```json
{
  "angle_def": "v1", "fps": 59.94, "width": 1920, "height": 1080, "keypoint_order": "PRD 6.5.3 (0-21)",
  "frames": [
    {"frame": 40, "camera_side": "right", "points": [[612, 402, 0.91], ...22개], "angles": {"shoulder_r": 152.3, "elbow_r": 131.0}},
    {"frame": 42, "camera_side": null, "points": null, "angles": null}
  ]
}
```

| 필드 | 뜻 |
| --- | --- |
| `frame` | **0부터, 원본을 처음부터 읽은 순서**(OpenCV `VideoCapture.read()`를 차례로 부른 번호. 기업 `video_kpi.py track`과 같음) |
| `camera_side` | 이 프레임의 카메라 쪽. 촬영 한 건에 방향이 다른 통과가 섞일 수 있어 프레임마다 둔다. 못 정하면 null |
| `points` | 22점 `[x, y, 확신도]`, 원본 영상 픽셀. 개가 없으면 null |
| `angles` | 카메라 쪽 다리의 굽힘 각도. 키는 `{관절}_l`·`{관절}_r` (`angle_def` v1, 0에서 360°). 진행 방향을 못 정한 프레임은 null, 반대쪽 다리는 키가 없다 |

결과 영상은 카메라 쪽 다리와 몸통만 그린다(PR-F01-04, 백엔드 `visible_points`).

## 6. 아직 비어 있는 것

| 항목 | 언제 |
| --- | --- |
| `gait` 실제 값 | 보행 유형 판별(박규원 #106 다음 단계) |
| `MAT_NOT_FOUND`, `OVERLAP` | 매트·사람 겹침 검출 방법 정해진 뒤 |
| `paw_slope_*`, `paw_lift_*`, `paw_excursion_*` | 스프린트 4 |
