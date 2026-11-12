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
| 10-29 | 비스듬한 통과 처리 방법별 KPI-01·02 (S15P31A404-102): 정규화 없음, v0, 비스듬한 통과만 기울기 보정, 비스듬한 통과 제외, 가로 늘리기 없이 거리만 보정(iso). 실제 26·72개, 합성 카메라 | `normalize/oblique_fix.py` | iso 만 KPI-01 을 줄임(실제 +7%·+4%, 합성 yaw +21%), v0 는 −14%·−7% 로 키움. KPI-02 는 모두 그대로. 정규화 v1 기본을 iso 로 바꿈(docs/normalize/oblique.md) |
| 10-22 | flip test 비교와 정답 부분 집합 재채점 | `run/flip_test.sh`, `make_gt_subsets.py`, `rescore_split.sh` | 위키 작업 기록 261022 flip test |
| 10-27~11-02 | 라벨러 맞추기 키트(제니 20장)와 기업 정답 비교, 6명 결과, 관절점 예시 그림 | `calib/make_kit.py`, `compare.py`, `pair.py`, `kpi.py`, `fig213.py` | 위키 05-보고 261102 라벨러 맞추기 6명 결과 |
| 10-27 | 의사 라벨 학습(뒷다리 비터비 적용, 미적용) | `pl/run_pl2.sh`, `prep_pl.py`, `make_queue4.py` | 제니 9.2~10.9°로 기각(위키 실험 결과 종합 10-27 저녁) |
| 10-29 | 탐지 간격 K와 fp16 스윕, 빈 구간 확인(probe), TTA 켠 구성 시간, 시드 재현성, 머리만 학습의 백본 변화 | `run/run_sweep_speed.sh`, `make_probe_models.py`, `patch_probe.py`, `run_probe_speed.sh`, `run_probe_server.sh`, `make_tta_models.py`, `run_tta_speed.sh`, `tta_check.py`, `run_seed_check.sh`, `seed_compare.py`, `backbone_check.py`, `eval_runs/box_motion.py`, `gap_sim.py` | 위키 05-보고 261029 AI 주간 실험 정리 |
| 11-02 | G3 백본 완전 고정(`_fz`) | `cv/run_fz.sh`, `run/backbone_check_fz.py` | 시트 E-589, 590 (6.71°에서 7.60°로 기각) |
| 11-02 | 오토라벨의 틀린 점을 빼거나 TTA 재예측, 정답으로 바꾼 학습(교정 상한) | `cv/run_orc.sh`, `oracle_tta.py`, `oracle_make.py`, `make_queue_orc.py` | 결과 위치 확인 필요 |
| 11-03 | 팀 라벨 93장 학습, 기준이 갈린 관절이나 사진 빼기 (S15P31A404-212) | `cv/run_212.sh`, `make_212.py` | 시트 E-765~E-782 |
| 11-03 | 가중치 5개와 추론 증강 7가지 선별, 뒷다리 바로잡기 강도 (기업 점검 후보) | `cv/screen/run_screen.sh`, `screen.py`, `tta_eval.py`, `lr_pass.py`, `queue_team.jsonl` | 시트 E-807~E-822, 기업 점검 4번 가중치(`wise_0.5.pth`)가 여기서 나옴 |
| 11-03 | 가벼운 TTA(t2) 구성의 처리 시간 | `run/make_t2_models.py`, `run_t2_speed.sh` | 시트 E-823~E-828 |
| 11-09 | 탐지기 상자 기준 TTA 비교(S15P31A404-216), 혼합 가중치 t0, t2, t4 비교와 영상 추론 시간(S15P31A404-297) | `eval_runs/detbox_tta.py`, `tta_compare.py`, `tta_video_timing.py` | Jira S15P31A404-216, 297 |
