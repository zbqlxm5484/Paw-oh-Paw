# 얼굴 검출 모델 (결과 영상 얼굴 가리기, 명세 7절, Jira 150·137)

| 파일 | 출처 | 라이선스 | 크기 | SHA-256 |
| --- | --- | --- | --- | --- |
| `face_detection_full_range.onnx` | Google MediaPipe BlazeFace(full range) `face_detection_full_range.tflite`를 tf2onnx로 바꾼 것(아래) | Apache-2.0 (`LICENSE`, Copyright The MediaPipe Authors) | 2,076,812 B | `fc54cf55821790712d0b91bcaa562cdb34e9c1e440e49b7561fc6e69744b5cd8` |

- 원본: https://storage.googleapis.com/mediapipe-assets/face_detection_full_range.tflite (2026-10-30 내려받음, 1,083,786 B, SHA-256 `3698b18f063835bc609069ef052228fbe86d9c9a6dc8dcb7c7c2d69aed2b181b`). 모델 카드: https://storage.googleapis.com/mediapipe-assets/MediaPipe%20BlazeFace%20Model%20Card%20(Full%20Range).pdf — "LICENSED UNDER Apache License, Version 2.0", 학습 데이터는 "consented images of people using a mobile AR application captured with smartphone cameras"(구글 자체, 10만 장 이상). 공개 비상업 데이터셋을 쓰지 않아 세부명세서 7.1(사전학습 가중치의 학습 데이터 조건)에 걸릴 것이 없다.
- 변환(Apache-2.0 4조 b에 따라 바꾼 파일임을 밝힌다): Python 3.11, tensorflow 2.21.0, tf2onnx 1.17.0, onnx 1.23.2. `python -m tf2onnx.convert --tflite face_detection_full_range.tflite --output face_detection_full_range.onnx --opset 13 --inputs-as-nchw input`. 가중치는 그대로이고 입력을 NCHW로 받는 Transpose만 더해진다. OpenCV 5.0 DNN 출력이 TensorFlow Lite 출력과 1e-4 안에서 같은 것을 확인했다.
- 입력 192x192 RGB, [-1, 1] 정규화, 비율 유지(letterbox). 출력은 앵커 2304개(stride 4, 48x48 격자)마다 상자 16값(중심 x·y, 너비·높이, 눈·코·입·귀 6점)과 점수 1값(logit). 해석은 MediaPipe `face_detection_full_range.pbtxt`(x/y/w/h_scale 192, min_score_thresh 0.6)와 같고 코드는 `app/video/render.py`의 `FaceDetector`다. 멀리 있는 작은 얼굴을 잡으려고 프레임을 겹치는 타일(1080p면 4x3)로 나눠 넣는다.
- 확인(2026-10-30): 회사 프레임 20장(1080p, 사람 얼굴 24개, 57~143px)에서 4x3 타일로 진짜 얼굴의 점수 최저 0.657·중앙값 0.852. 점수 0.5로 24/24, 오탐 1(같은 사람의 턱 아래 상자). 0.6은 24/24·오탐 0이지만 여유가 0.06뿐이라 0.5를 쓴다(0.4는 오탐 5, 개 위 1). 개 얼굴은 잡지 않음, 1스레드 약 90ms(0.6)~120ms(0.5)/프레임, 검출은 0.05초 간격.
- 루트 `.gitignore`의 `*.onnx` 규칙(학습 가중치 제외용)에 이 폴더만 예외를 두었다. 백엔드가 쓰는 라이브러리 파일이라 저장소에 함께 둔다.
- 뺀 후보: Ultralytics YOLO 계열(AGPL), YuNet(모델은 MIT지만 학습 데이터 WIDER FACE가 cc by-nc-nd 표기), InsightFace(가중치 비상업 연구 전용), Haar(pip OpenCV 5 휠에 없고 학습 데이터 불명). 조사 전체는 `docs/report/faceDetectorLicense.md`(S15P31A404-137), D-11 반영은 QA(김지윤)가 한다.
