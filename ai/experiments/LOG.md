# 실험 목록

한 줄에 실험 하나. 새 실험을 하면 맨 아래에 더합니다. 실험 번호(E-)는 팀 실험 기록 시트, 해석은 노션 세부 사항의 그날 "실험 정리" 페이지에 있습니다. 경로·환경 변수는 `README.md`.

| 날짜 | 실험 | 스크립트 | 결과 |
| --- | --- | --- | --- |
| 10-19 | 좌표 정규화 v0: KPI-02 화면 위치 효과가 카메라 기하인지 개의 변화인지 가르기, 매트 평면 투영 | `normalize/crosscam.py`, `dirflip.py`, `kpi02_null.py`, `kpi02_speed.py`, `plane_norm.py`, `detect.py`, `by_dog.py`, `smooth_test.py` | 노션 10-19 실험 정리 |
| 10-20 | 라벨 맞추기 20장(pilot20): 후보 뽑기 → 개마다 4장 → CVAT 태스크 → 일치도 | `labels/pilot_candidates.py`, `pilot_select.py`, `select_pilot.py`, `build_pilot20.py`, `assign.py`, `pilot_fetch.py`, `pilot_agreement.py`, `pilot_to_coco.py` | 노션 10-20 |
| 10-20 | CVAT 오토라벨 selftest 다름 진단 | `labels/selftest_detail.py` | 노션 10-20 |
| 10-20~22 | fs-v4 이어 학습 시험: BN 고정 필요, 학습 5종 | `finetune/train.py`, `ft_creamoff.py`, `to46.py`, `split_wowwow.py`, `curve.sh` | `docs/training/poseFinetune.md` |
| 10-20 | 라벨링 1차 묶음 촬영 고르기 | `labels/select_batch1.py`, `pick_sessions.py` | 노션 10-20 |
| 10-22 | 추론 증강·후처리: flip·배율·회전, 좌우 바로잡기, 앞뒤 프레임 평활, 가장자리 헛상자 거르기 (E-008~E-045) | `eval_runs/multiscale_tta.py`, `rotate_tta.py`, `lr_fix.py`, `lr_fix_track.py`, `lr_fix_time.py`, `temporal_smooth.py`, `track_to_preds.py`, `edge_filter.py`, `tta_speed.py`, `make_sheet_1022.py`, `make_sheet_pm_1022.py`, `make_sheet_eve_1022.py`, `make_sheet_fill_1022.py`, `make_sheet_speed_1022.py` | 시트 E-008~E-045, 노션 10-22 |
| 10-20~22 | 작은 탐지기 증류용 데이터, 후보 영상 오토라벨, 가짜 라벨 | `labels/det_teacher.py`, `det_teacher2.py`, `pool_infer.py`, `pseudo_label.py` | 노션 10-20·10-22 |
| 10-23 | 탐지 간격·fp16 처리 성능, GPU 메모리, 영상 상자 채점, 영상 KPI (E-034~E-074) | `eval_runs/det_stride.py`, `kpi_variant.py`, `perf_mem.py`, `run_perf_1023.sh`, `run_kpi_1023.sh`, `run_vbox_1023.sh`, `run_all_1023b.sh`, `run_speed_1023b.sh`, `make_sheet_1023.py`, `make_sheet_perf_1023.py`, `make_sheet_speed_1023.py` | 시트 E-034~E-074, 노션 10-23 |
| 10-26 | 와우와우 기준 차이 보정: 50장 직접 라벨 → 관절별 평균 차이 → 학습셋 옮기기 → 누수 확인 | `labels/select50.py`, `offset_analyze.py`, `score50.py`, `apply_offset.py`, `offset_fold.py`, `fold_score.py`, `perjoint_gt.py`, `finetune/offset.sh`, `offset_fold.sh`, `eval_runs/run_offset_1026.sh` | 기업 정답에서 악화(14.86° → 19.57°), 노션 10-26 |
| 10-26 | 시험 라벨 학습: 76장·96장, 어깨뼈 위끝 되돌림·빼기, 최소 수정판, 오토라벨 대조군 | `finetune/pilot.sh`, `pilot96.sh`, `pilotmin.sh`, `runs.sh`, `runs2.sh`, `eval_runs/run_pilot_1026.sh`, `run_pilot96_1026.sh`, `run_pilotmin_1026.sh`, `run_runs_1026.sh`, `run_runs2_1026.sh`, `labels/perjoint_pilot.py`, `perjoint_p96.py`, `scapula_sheet.py` | 시트 E-075~E-103, 노션 10-26 |
| 10-26 | 기업 라벨러 vs 팀 라벨러 고친 방식, 시험 라벨 검수 태스크 | `labels/edit_style.py`, `review_task.py`, `build_review100.py` | 노션 10-26 |
| 10-26 | 기업 정답 반쪽 학습 → 다른 반쪽 채점(촬영 단위 분할), 묶음 하나 뺀 학습 | `eval_runs/run_cv_1026.sh` (학습은 `finetune/runs.sh`) | 반쪽 기준선 7.57°/8.21° → 6.95~7.05°/7.34~7.38° (시드 3개씩) |
| 10-26 | 이어 학습 처리 성능 | `eval_runs/run_perf_1026.sh`, `make_sheet_1026.py`, `make_sheet_perf_1026.py` | 시트 E-075~E-103 |
| 10-26 | 비스듬 보행 판별, 카메라 오차 합성 확인 그림 | `normalize/oblique_sheet.py`, `synth_sheet.py` (본체는 `ai/normalize/oblique.py`, `synth_camera.py`) | `docs/normalize/` |
| 10-28 | 기업 정답(260820, 제니 한 마리)·와우와우가 오토라벨에서 관절을 어느 방향으로 옮겼나: 통계, 겹쳐 보기, 나란히 보기 | `labels/direction_stats.py`, `gt_overlays.py`, `gt_side_by_side.py`, `ww_overlays.py`, `ww_compare.py` | 무릎은 반대 방향(기업 머리 쪽, 와우와우 꼬리 쪽), 기업은 몸통 점을 0~5%만 고침 |
| 10-28 | 와우와우 30장을 기업 방식으로 다시 라벨링할 표본 (CVAT 태스크 18) | `labels/select30.py` | 라벨링 중 |
