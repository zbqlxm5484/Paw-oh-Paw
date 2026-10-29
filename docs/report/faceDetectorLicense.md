# 얼굴 검출 모델 라이선스 조사 (S15P31A404-137)

작성 조영운 · 2026-10-29 조사, 10-30 모델 교체 · 라이선스 검토서(D-11) 반영용

- 무엇을: 결과 영상에서 사람 얼굴을 가리는 데 쓰는 얼굴 검출 모델과, 결과 영상을 만드는 ffmpeg·코덱, 백엔드 라이브러리의 라이선스를 세부명세서 7.1절 기준으로 조사했다.
- 어디에 반영: 라이선스 검토서(D-11) 본체는 QA(김지윤, S15P31A404-41·139)가 관리한다. 이 문서의 7절 표를 그대로 옮기면 된다. 코드 쪽 기록은 백엔드 명세 7절(결과 영상 만들기)과 `backend/app/video/models/README.md`다.
- 확인 날짜: 외부 자료는 2026-10-29·30에 확인했다(9절 출처).
- **결정(2026-10-30, 조영운)**: 팀 서비스(백엔드·프론트)는 기본적으로 기업 납품 대상이 아니다(회사에 자체 서비스가 있어 우리 서비스는 필요 없다고 했다). 다만 회사가 프론트를 마음에 들어 하면 백엔드까지 가져갈 수 있으므로, **애초에 7.1에 걸릴 것이 없는 모델로 바꾼다.** 처음 고른 YuNet을 **Google MediaPipe BlazeFace로 교체**했고(S15P31A404-150), 11-03 멘토링에는 보고만 한다(10절).

## 0. 결론

- **쓰는 모델**: Google MediaPipe **BlazeFace(full range)**. 모델 카드에 라이선스 **Apache-2.0**, 학습 데이터는 "구글이 동의를 받아 스마트폰으로 찍은 자체 이미지 10만 장 이상"이라고 적혀 있다. 공개 비상업 데이터셋을 쓰지 않았으니 7.1의 "사전학습 가중치: 학습 데이터 조건까지 확인한다"에 걸릴 것이 없다. 조사한 후보 중 학습 데이터까지 깨끗한 사전학습 모델은 이것 하나였다(3절).
- **실행 방식**: tflite 원본을 tf2onnx로 한 번 바꿔 ONNX 파일(2.1MB)을 코드와 같이 두고 OpenCV DNN으로 돌린다. 패키지 추가도, Dockerfile 변경도 없다. 변환 명령·SHA-256·검증은 4절과 `backend/app/video/models/README.md`.
- **검증(10-30)**: 회사 프레임 20장(1080p, 사람 얼굴 24개, 57~143px)에서 4x3 타일·점수 0.6으로 **사람 얼굴 24/24, 오탐 0, 개 얼굴은 잡지 않음**, 1스레드 약 100ms/프레임. OpenCV DNN 출력이 TensorFlow Lite 출력과 1e-4 안에서 같다.
- **처음 골랐던 YuNet을 뺀 이유**: 모델 파일은 MIT지만 WIDER FACE로 학습했고(저작자의 학습 저장소가 명시), WIDER FACE 홈페이지의 License 항목은 "Creative Common License (cc by-nc-nd)", 곧 비상업 조건이다. 학습 라벨(labelv2)은 InsightFace SCRFD에서 왔고 InsightFace는 "학습 데이터와 그 데이터로 학습한 모델은 비상업 연구 목적만"이라고 적는다. 7.1 "비상업 조건 데이터로 학습한 가중치는 쓸 수 없다"를 글자대로 적용하면 납품물에는 기업 승인 없이 쓸 수 없다. 공개 얼굴 검출기는 대부분 WIDER FACE 계열이라 같은 문제가 있다.
- **ffmpeg·코덱**: ffmpeg는 별도 실행 파일을 프로세스로 부르므로 GPL이 백엔드 소스 공개 의무를 만들지 않는다. 배포 이미지(Debian 13)의 ffmpeg 패키지는 GPL v2+다. 도커 이미지를 기업에 전달하게 되면 GPL 바이너리를 배포하는 것이 되므로, PR-C-07대로 ffmpeg는 requirements.txt 밖 전제로 실행·배포 가이드에 적고 운영자가 OS 패키지로 설치하는 쪽을 권한다. H.264 특허는 저작권 라이선스와 별개 문제라 8절 확인 목록에 두었다.
- **백엔드 라이브러리**: 전부 MIT·BSD·Apache·PSF 계열이다(6절). 약한 카피레프트가 둘 있다. OpenCV 휠에 동봉된 FFmpeg(LGPL-2.1)와 httpx가 끌고 오는 certifi(MPL-2.0)인데, 둘 다 고치지 않고 그대로 쓰므로 우리 소스 공개 의무는 생기지 않는다. 기록용으로 D-11에 적는다.

## 1. 기준

세부명세서(크림오프_세부명세서.pdf) 7절·7.1절·10.1절에서 그대로 옮겼다.

| 항목 | 내용 |
| --- | --- |
| 7.1 머리말 | 제품은 상업 배포되므로, 학습·추론·보고서 생성에 쓰는 모든 구성요소는 상업 이용이 허용되어야 한다 |
| 7.1 학습 데이터 | 데이터로 학습한 모델의 상업 배포가 허용되어야 한다. AI-Hub 71878을 포함해 사용한 데이터의 이용 조건을 라이선스 검토서(D-11)에 적는다 |
| 7.1 사전학습 가중치 | 상업 이용이 허용되어야 하며, 그 가중치를 학습한 데이터의 조건까지 확인한다. **비상업 조건 데이터로 학습한 가중치는 쓸 수 없다** |
| 7.1 라이브러리·프레임워크 | 상업 배포가 허용되어야 한다. 납품물의 소스 공개 의무를 만드는 라이선스는 쓸 수 없다 |
| 7.1 기업 제공 자료 | 자체 촬영 자료는 본 프로젝트에만 쓴다(PR-C-02) |
| 7.1 증빙 | 구성요소별 라이선스 원문과 상업 이용 근거 조항을 라이선스 검토서(D-11)로 제출하고, 사용 전 기업 승인을 받는다. **조건이 불명확한 구성요소는 쓸 수 없는 것으로 본다** |
| PR-C-02 보안 | 제공 자료를 과제 목적 외에 쓰지 않고, 영상·사진·식별 정보를 외부로 전송하지 않으며, 종료 시 파기한다 |
| PR-C-03 보안 | 산출물에 사람 얼굴을 노출하지 않고, 외부 자료에서 질환견은 익명으로 표기한다. 목표 노출 0건(REQ-CM-003·005) |
| PR-C-04 라이선스 | 7.1절의 라이선스 요구사항을 충족한다. 목표 KPI-32 |
| PR-C-07 환경 재현 | 납품 코드는 Python 3.11 .venv에 requirements.txt로 설치하면 같은 환경이 되어야 한다. requirements.txt 밖의 전제는 실행·배포 가이드에 적는다 |
| 10.1 포트폴리오 활용 | 영상·사진·식별 정보를 공개하지 않고, 사람 얼굴을 노출하지 않으며, 질환견은 익명으로 표기한다. 공개 전 기업이 확인한다 |

읽는 법: 얼굴 가리기 자체는 PR-C-03·10.1이 요구하는 일이다. 그 일에 쓰는 모델이 7.1의 "사전학습 가중치" 줄에 걸린다. 7.1 머리말은 "학습·추론·보고서 생성에 쓰는 구성요소"를 말하지만, 증빙 줄은 구성요소를 가리지 않고 "조건이 불명확하면 못 쓴다"고 하므로 납품물이라면 넓게 읽어야 한다. 팀 서비스는 기본적으로 납품 대상이 아니지만 회사가 가져갈 수 있어, 글자대로 적용해도 걸릴 것이 없는 모델을 골랐다(10-30).

## 2. 이 구성요소가 하는 일

- 자리: 백엔드 워커의 결과 영상 만들기(백엔드 명세 7절, `backend/app/video/render.py`). 분석 API가 돌려준 관절점으로 골격을 그리기 전에, 프레임마다 사람 얼굴을 찾아 모자이크와 흐림으로 가린다.
- 데이터 흐름: 원본 영상은 분석에 그대로 쓰고, 얼굴 가리기는 사람이 보는 결과 영상에만 적용한다. 검출한 얼굴 위치는 저장하지 않고 로그에도 개수만 남긴다. 외부로 보내는 것은 없다(PR-C-02).
- 학습·추론·보고서와의 관계: 반려견 보행 분석(학습·추론)이나 보고서 수치 생성에는 관여하지 않는다. 결과 영상은 F-09 "분석 상태·결과 조회"(추가 범위) 화면의 재생용이다.
- 교체 지점: `FaceDetector` 클래스 하나와 `render_video(..., detect_faces=None)` 인자. YuNet → BlazeFace 교체도 이 클래스와 모델 파일만 바뀌었고 가리기·유지·골격·인코딩 코드는 그대로였다.

## 3. 후보 비교

판정 기호: ○ 7.1 통과, △ 기업 승인 필요(조건이 불명확하거나 비상업 데이터로 학습), ✕ 불가.

| # | 후보 | 코드·라이브러리 | 가중치(모델 파일) | 학습 데이터 | 7.1 판정 | 비고 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **MediaPipe BlazeFace** (full range), **채택** | MediaPipe Apache-2.0. 실행은 OpenCV DNN(Apache-2.0) | 모델 카드 "LICENSED UNDER Apache License, Version 2.0" | 구글 자체 데이터. "trained and evaluated on consented images of people using a mobile AR application captured with smartphone cameras", full range는 10만 장 이상 | **○** | 입력 192px라 프레임을 겹치는 타일(1080p는 4x3)로 나눠 넣는다. 회사 프레임 20장에서 사람 얼굴 24/24, 오탐 0, 약 100ms/프레임. tflite → ONNX 변환 한 번, 추가 패키지 없음 |
| 2 | YuNet (OpenCV `FaceDetectorYN`), 처음 골랐다가 뺌 | OpenCV Apache-2.0. opencv_zoo 저장소 Apache-2.0 | 모델 폴더 LICENSE MIT(Shiqi Yu). "All files in this directory are licensed under MIT License" | **WIDER FACE**(홈페이지 License: cc by-nc-nd) + SCRFD 라벨(InsightFace, 비상업 연구 전용 표기) | 라이선스 ○ / 학습 데이터 **△** | 10×10px 작은 얼굴까지 잡고 폭 640에서 약 50ms, 추가 설치 없음. 회사 프레임에서 원본 해상도로는 개 머리를 얼굴로 잡은 프레임이 하나 있었다 |
| 3 | OpenCV Haar·LBP cascade | OpenCV 저장소 Apache-2.0(xml 머리말은 Intel 라이선스, BSD형) | 저장소 xml | 미공개(2000년대 Intel 내부 데이터) | △(조건 불명확) | OpenCV 5.0 본체 휠에 `CascadeClassifier`가 없다(확인함). contrib 패키지가 더 필요. 옆얼굴·작은 얼굴에 약하다 |
| 4 | InsightFace RetinaFace·SCRFD | 코드 MIT | 비상업 연구 전용 명시 | 비상업 연구 전용 명시 | ✕ | "models trained with these data are available for non-commercial research purposes only" |
| 5 | Ultralytics YOLO(-face 변형) | **AGPL-3.0**(유료 Enterprise 라이선스 별도) | AGPL-3.0 | WIDER FACE | ✕ | 소스 공개 의무를 만든다. 백엔드 명세 7절에서 이미 제외 |
| 6 | dlib HOG · CNN(mmod) 얼굴 검출기 | Boost Software License | 모델 파일은 퍼블릭 도메인 선언 | CNN 모델은 저작자가 ImageNet·AFLW·Pascal VOC·VGG·**WIDER**·FaceScrub에서 모은 이미지로 만들었다고 밝힘. HOG는 미확인 | ✕(CNN) / △(HOG) | C++ 빌드(CMake·컴파일러) 필요. 정확도는 1·2보다 낮다 |
| 7 | CenterFace, MTCNN(facenet-pytorch) 등 | MIT 코드 | 저장소 MIT | WIDER FACE·CelebA 계열(논문 기준) | △~✕ | 2와 같은 문제에 성능·유지보수 이점이 없다 |
| 8 | 클라우드 얼굴 API(AWS Rekognition, Azure Face 등) | 약관 | 해당 없음 | 해당 없음 | ✕ | 영상·사진을 외부로 보낼 수 없다(PR-C-02) |
| 9 | 모델 없음: 관절점 상자 밖 흐림 | 우리 코드만 | 없음 | 없음 | ○ | 프레임마다 신뢰도 0.3 이상 관절점의 상자에 여백을 주고 그 밖을 전부 흐린다. 개는 선명하고 사람은 몸 전체가 흐려진다. 사람이 개와 겹치는 프레임(안아 올리기 등)은 얼굴이 상자 안에 들 수 있어 완전하지 않다. 1이 안 됐을 때의 대안으로 남겨 둔다 |

후보를 고른 기준: 백엔드 명세 7절(라이선스를 먼저 본다, YOLO 계열 AGPL 제외), 세부명세서 7.1(학습 데이터 조건까지), 추가 설치 없이 python:3.11-slim에서 돌 것, 1080p 영상에서 보호자·직원의 작은 얼굴을 잡을 것, 프레임당 100ms 안팎.

## 4. 고른 모델 상세 (MediaPipe BlazeFace full range)

| 항목 | 내용 |
| --- | --- |
| 파일 | `backend/app/video/models/face_detection_full_range.onnx`, 2,076,812바이트, SHA-256 `fc54cf55821790712d0b91bcaa562cdb34e9c1e440e49b7561fc6e69744b5cd8` |
| 원본 | https://storage.googleapis.com/mediapipe-assets/face_detection_full_range.tflite (2026-10-30 내려받음, 1,083,786바이트, SHA-256 `3698b18f063835bc609069ef052228fbe86d9c9a6dc8dcb7c7c2d69aed2b181b`). MediaPipe 저장소 `mediapipe/modules/face_detection/face_detection_full_range.pbtxt`가 쓰는 모델 |
| 라이선스 원문 | 모델 카드 "LICENSED UNDER Apache License, Version 2.0"(2021-01-19). MediaPipe 저장소 LICENSE(Apache-2.0)를 `backend/app/video/models/LICENSE`로 두고, 바꾼 파일임을 밝히는 문구(Apache-2.0 4조 b)를 앞에 붙였다 |
| 상업 이용 근거 조항 | Apache-2.0 2조(저작권 사용 허가: reproduce, prepare Derivative Works, publicly display, sublicense, distribute)·3조(특허 사용 허가). 조건은 라이선스 사본·고지 동봉과 수정 표시이며 LICENSE·README로 지켰다 |
| 학습 데이터 | 모델 카드: "This model was trained and evaluated on consented images of people using a mobile AR application captured with smartphone cameras in various 'in the wild' conditions", "The dataset consists of 100+K images". 공개 비상업 데이터셋이 아니라 7.1 사전학습 가중치 줄에 걸릴 것이 없다 |
| 변환 | Python 3.11, tensorflow 2.21.0, tf2onnx 1.17.0, onnx 1.23.2. `python -m tf2onnx.convert --tflite face_detection_full_range.tflite --output face_detection_full_range.onnx --opset 13 --inputs-as-nchw input`. 가중치는 그대로이고 입력을 NCHW로 받는 Transpose만 더해진다. sparse 판(`face_detection_full_range_sparse.tflite`)은 tf2onnx가 변환하지 못해 쓰지 않았다 |
| 실행 | opencv-python-headless 5.0.0.93의 `cv2.dnn.readNetFromONNX`. 입력 192x192 RGB, [-1, 1] 정규화, 비율 유지(letterbox, MediaPipe ImageToTensor와 같음). 출력은 앵커 2304개(stride 4, 48x48 격자)마다 상자 16값과 점수 1값. 해석은 `face_detection_full_range.pbtxt`(x/y/w/h_scale 192, min_score_thresh 0.6)와 같다. 코드 `app/video/render.py`의 `FaceDetector` |
| 타일 | 폭 1920 이하로 줄인 프레임을 480x360쯤의 타일(1080p는 4x3, 사방 20% 겹침)로 나눠 타일마다 넣고 NMS(0.3)로 합친다. 모델 입력이 작아 프레임을 통째로 넣으면 60px 얼굴이 몇 px로 줄어 놓치기 때문이다 |
| 확인한 품질(10-30) | 회사 프레임 20장(1920x1080, 직원 1~3명, 사람 얼굴 24개, 57~143px). 기준은 YuNet 원본 해상도 검출을 사람이 확인한 것. 4x3 타일·0.6: 사람 얼굴 24/24, 오탐 0, 개 얼굴 안 잡음, 약 100ms/프레임(1스레드, 65~184ms). 3x2·0.5: 23/24(팔로 이마를 짚어 반쯤 가린 59px 얼굴 1개 놓침), 0 오탐, 약 50ms. 2x2: 22/24(화면 가장자리 얼굴 놓침). 프레임 통째로: 20/24에 오탐 8. short range 모델은 6x4 타일에서야 24/25였고 오탐이 많아 탈락. OpenCV DNN 출력과 TensorFlow Lite 출력의 최대 차이 1e-4 |
| 비용 | YuNet(폭 640, 약 50ms)의 두 배. 30fps 10초 영상이면 렌더 시간이 15초에서 30초로 늘고, 워커가 뒤에서 하므로 화면에는 영향 없다 |

### 4.1 처음 골랐던 YuNet (기록)

| 항목 | 내용 |
| --- | --- |
| 파일 | opencv_zoo `models/face_detection_yunet/face_detection_yunet_2023mar.onnx`, 232,589바이트, SHA-256 `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`(2026-10-29 내려받음, 150 초안에 동봉했다가 10-30 교체) |
| 라이선스 | 폴더 LICENSE MIT(Copyright 2020 Shiqi Yu). 저장소 전체는 Apache-2.0이고 "모델별 라이선스를 따로 보라" |
| 학습 데이터 | 저작자의 학습 저장소 libfacedetection.train(BSD-3-Clause): "YuNet face detection training on WIDER Face", "The labelv2 annotations come from SCRFD". WIDER FACE 홈페이지 License: "Creative Common License (cc by-nc-nd)". SCRFD는 InsightFace 소속이고 그 README는 학습 데이터와 그것으로 학습한 모델을 비상업 연구 전용으로 적는다 |
| 논문 | Wu, Peng, Yu, "YuNet: A Tiny Millisecond-level Face Detector", Machine Intelligence Research 20(5), 2023 |
| 판단 | 모델 파일의 MIT는 상업 이용을 허용하지만, 7.1은 학습 데이터 조건까지 보라고 하고 "조건이 불명확하면 못 쓴다"고 하므로 납품물에는 기업 승인이 필요하다. 법적으로는 회색 지대이고 실제 위험은 낮지만 회사 규칙이 먼저다. 팀 서비스가 납품될 가능성이 낮아도 0은 아니라서 교체했다 |

## 5. 결과 영상 인코딩: ffmpeg와 코덱

### 5.1 쓰는 방법

- 백엔드는 ffmpeg·ffprobe를 **별도 실행 파일**로 부른다(설정 `FFMPEG_PATH`·`FFPROBE_PATH`, 백엔드 명세 16절). 업로드 검사(13.1)는 `ffprobe -show_streams -show_format`, 결과 영상 저장은 ffmpeg에 프레임을 표준 입력으로 넘겨 `-c:v libx264 -pix_fmt yuv420p -movflags +faststart`로 MP4를 만든다. 링크하지 않고 프로세스로 부르므로 백엔드 코드는 ffmpeg의 파생물이 아니고, GPL이 백엔드 소스 공개 의무를 만들지 않는다. 실행 파일 경로만 바꾸면 다른 빌드로 바뀐다.
- 원본 프레임 읽기는 OpenCV `VideoCapture`가 한다. 이것은 휠에 동봉된 FFmpeg 라이브러리(LGPL 빌드, avcodec 61.19.100)를 쓴다(5.4).

### 5.2 배포 이미지의 ffmpeg

| 항목 | 확인한 것 |
| --- | --- |
| 바탕 이미지 | `python:3.11-slim` = Debian 13(trixie). docker-library 공식 목록에서 `3.11-slim`이 `3.11/slim-trixie`의 별칭 |
| 패키지 | Debian trixie `ffmpeg 7:7.1.5-0+deb13u1`(Dockerfile이 `apt-get install ffmpeg`) |
| 빌드 옵션 | debian/rules: `--enable-gpl`, `--enable-libx264`, `--enable-libx265`, `--enable-libvpx`, `--enable-libaom`. `--enable-nonfree` 없음, libopenh264 없음. `--enable-version3`는 별도 flavor(libavcodec-extra)에만 |
| 바이너리 라이선스 | debian/copyright: "For building the default Debian packages some of the GPL licensed files are used, so the resulting binaries are licensed under GPL v2+". libavcodec-extra flavor는 GPL v3+. non-free 조합은 하지 않는다 |
| libx264 | GPL(v2). VideoLAN이 상업 라이선스를 따로 판다(x264licensing@videolan.org) |
| 개발 PC | Gyan.FFmpeg 9.0.2 full build(`--enable-gpl --enable-version3`, GPL-3+). 개발용이라 납품과 무관 |

### 5.3 의무와 권고

- 우리 코드: 의무 없음(5.1).
- 배포: 기업에 도커 이미지를 전달하면 Debian ffmpeg(GPL v2+) 바이너리를 **배포**하는 것이라 GPL 3조의 소스 제공 의무가 따른다. 고치지 않은 Debian 패키지이므로 Debian 소스 패키지가 해당 소스지만, 가장 깔끔한 길은 **ffmpeg를 납품물에 넣지 않는 것**이다. PR-C-07이 requirements.txt 밖의 전제를 실행·배포 가이드에 적으라고 하므로 "ffmpeg 7.x를 OS 패키지로 설치"를 가이드에 적고 운영자가 설치하게 한다. 그러면 우리는 GPL 소프트웨어를 배포하지 않는다. Dockerfile은 Infra(허정원) 파일이라 팀 결정 뒤 그쪽에서 바꾼다.
- H.264/AVC 특허: 저작권 라이선스와 별개 문제다. x264는 특허 사용권을 주지 않고, AVC 특허 풀(Via LA)이 있다. 팀 서비스처럼 내부 열람용 소량 영상은 문제 삼는 일이 드물지만, 기업이 결과 영상을 상업 서비스로 내보내는 규모가 되면 기업 법무가 볼 항목이다. 입력 영상이 이미 H.264·H.265(PR-F07-01)라 디코딩 쪽도 같은 성격이다.
- 로열티 없는 대안: VP9(libvpx, BSD)·AV1(libaom BSD-2, SVT-AV1 BSD). Debian ffmpeg에 들어 있어 `render.py`의 인코더 인자만 바꾸면 된다. 다만 iOS Safari 재생 지원을 먼저 확인해야 한다. openh264(BSD-2)는 Cisco가 배포하는 바이너리에만 특허비를 Cisco가 부담하고 Debian ffmpeg에는 없으니 대안이 못 된다.

### 5.4 OpenCV 휠에 동봉된 FFmpeg

- `opencv-python-headless` 휠은 FFmpeg를 LGPL-2.1 빌드로 동봉한다(휠의 `LICENSE-3RD-PARTY.txt`: "FFmpeg is redistributed within all opencv-python packages", 이어서 LGPL 2.1 원문). GPL 구성요소는 없다.
- LGPL은 라이브러리를 고치지 않고 공유 라이브러리로 쓰는 프로그램에 소스 공개를 요구하지 않는다. 라이브러리 자체의 원문·소스 접근만 요구하고 휠이 원문을 담고 있다. 7.1 "소스 공개 의무를 만드는 라이선스"에 해당하지 않는다.
- 다만 백엔드 명세 11.6이 psycopg(LGPL)를 검토 부담 때문에 뺀 것과 같은 결이므로 D-11에 "LGPL 동봉, 수정 없음"으로 적어 둔다. AI 파트의 `opencv-python`도 같은 휠 구조다.

## 6. 백엔드 라이브러리 표

2026-10-29 `.venv`에 설치된 배포본의 메타데이터(License-Expression·Classifier)로 확인했다. 백엔드 명세 11.1 표의 "모두 상업 이용이 되는 라이선스"를 패키지 단위로 다시 확인한 것이다. AI·프론트·Infra 파트의 구성요소는 각 담당이 D-11에 올린다. 변환 도구(tensorflow, tf2onnx)는 개발 PC에서 한 번 쓴 것이라 납품물·requirements.txt에 없다.

### 6.1 직접 의존 (requirements.txt)

| 패키지 | 버전 | 라이선스 | 쓰임 |
| --- | --- | --- | --- |
| fastapi | 0.146.0 | MIT | 웹 프레임워크 |
| starlette | 1.9.0 | BSD-3-Clause | FastAPI 바탕 |
| uvicorn | 0.54.0 | BSD-3-Clause | 서버 |
| pydantic | 2.14.1 | MIT | 검증 |
| pydantic-settings | 2.16.1 | MIT | 설정 |
| python-multipart | 0.0.32 | Apache-2.0 | 업로드 |
| httpx | 0.28.1 | BSD-3-Clause | 분석 API 호출 |
| PyYAML | 6.0.3 | MIT | 설정·문구 파일 |
| tzdata | 2026.5 | Apache-2.0 | 시간대 |
| SQLAlchemy | 2.1.5 | MIT | ORM |
| pg8000 | 1.31.5 | BSD-3-Clause | PostgreSQL 드라이버(psycopg는 LGPL이라 제외, 명세 11.6) |
| alembic | 1.20.0 | MIT | DB 변경 이력 |
| bcrypt | 5.0.0 | Apache-2.0 | 비밀번호 |
| PyJWT | 2.15.1 | MIT | 토큰 |
| opencv-python-headless | 5.0.0.93 | 휠 포장 MIT, OpenCV Apache-2.0, 동봉 FFmpeg LGPL-2.1(5.4), 그 밖의 동봉 라이브러리(libwebp·libpng·libjpeg-turbo·OpenJPEG·protobuf·flatbuffers 등)는 BSD·Apache·ISC 계열. 원문은 휠의 `LICENSE-3RD-PARTY.txt` | 프레임 읽기·그리기·얼굴 검출(DNN) |
| pytest | 9.1.1 | MIT | 테스트에서만 |

### 6.2 함께 설치되는 것

| 패키지 | 버전 | 라이선스 | 누가 쓰나 |
| --- | --- | --- | --- |
| pydantic_core | 2.50.1 | MIT | pydantic |
| annotated-types, typing-inspection, annotated-doc | 0.8.0, 0.4.4, 0.0.5 | MIT | pydantic, fastapi |
| typing_extensions | 4.16.0 | PSF-2.0 | 여러 곳 |
| opentelemetry-api | 1.45.1 | Apache-2.0 | fastapi |
| anyio | 4.15.1 | MIT | starlette, httpx |
| idna | 3.20 | BSD-3-Clause | anyio, httpx |
| h11 | 0.16.0 | MIT | uvicorn, httpcore |
| click | 8.5.0 | BSD-3-Clause | uvicorn |
| httpcore | 1.0.9 | BSD-3-Clause | httpx |
| certifi | 2026.10.19 | **MPL-2.0**(파일 단위 약한 카피레프트. 고치지 않고 쓰므로 의무 없음) | httpx, httpcore |
| python-dotenv | 1.2.4 | BSD-3-Clause | pydantic-settings |
| Mako | 1.4.3 | MIT | alembic |
| MarkupSafe | 3.0.4 | BSD-3-Clause | Mako |
| scramp | 1.4.17 | MIT-0 | pg8000 |
| asn1crypto | 1.5.1 | MIT | scramp |
| python-dateutil | 2.9.0.post0 | BSD-3-Clause 또는 Apache-2.0(이중) | pg8000 |
| six | 1.17.0 | MIT | python-dateutil |
| numpy | 2.4.6 | BSD-3-Clause(일부 0BSD·MIT·Zlib·CC0) | opencv |
| colorama | 0.4.6 | BSD-3-Clause | pytest(Windows만) |
| pluggy, iniconfig | 1.7.0, 2.3.1 | MIT | pytest |
| packaging | 26.3 | Apache-2.0 또는 BSD-2-Clause | pytest |
| Pygments | 2.21.0 | BSD-2-Clause | pytest |

### 6.3 예정 (백엔드 명세 11.1, 아직 설치 안 함)

| 패키지 | 버전 | 라이선스 | 쓰임 |
| --- | --- | --- | --- |
| Jinja2 | 3.1 | BSD-3-Clause | 보고서 템플릿 |
| matplotlib | 3.11 | matplotlib 라이선스(PSF 계열) | 보고서 차트 |
| WeasyPrint | 70 | BSD-3-Clause | PDF. 시스템 라이브러리(Pango·Cairo, LGPL) 필요 → 설치 때 다시 본다 |
| boto3 | 1.43 | Apache-2.0 | S3(선택) |
| moto | 5.2 | Apache-2.0 | 테스트에서만 |

### 6.4 시스템

| 구성요소 | 버전 | 라이선스 | 비고 |
| --- | --- | --- | --- |
| Python | 3.11 | PSF-2.0 | PR-C-07 |
| PostgreSQL | 17 | PostgreSQL License(BSD형) | 팀 서버 compose |
| Debian(바탕 이미지) | 13 trixie | 패키지별(DFSG) | python:3.11-slim |
| ffmpeg·ffprobe | 7.1.5(Debian) | GPL-2+ (5.2) | 실행 파일, 링크 안 함 |

## 7. D-11에 올릴 행

검토서 표에 그대로 옮길 수 있게 줄였다. "원문"은 저장소 안 경로나 배포본 위치다.

| 구성요소 | 버전 | 라이선스 | 원문 | 상업 이용 근거 | 학습 데이터 조건 | 상태 |
| --- | --- | --- | --- | --- | --- | --- |
| MediaPipe BlazeFace 얼굴 검출 모델 (`face_detection_full_range.onnx`, tflite → ONNX 변환) | MediaPipe 2021-01-19판, 원본 SHA-256 `3698b18f…181b`, 변환본 `fc54cf55…5cd8` | Apache-2.0 (The MediaPipe Authors) | `backend/app/video/models/LICENSE`, 모델 카드 PDF | Apache-2.0 2조·3조. 사본·고지·수정 표시 동봉 | 구글 자체 동의 데이터(모델 카드). 공개 비상업 데이터셋 아님 | 기록. 7.1 통과 |
| (뺌) YuNet 얼굴 검출 모델 | opencv_zoo 2023-03판 | MIT (Shiqi Yu) | opencv_zoo 폴더 LICENSE | MIT | **WIDER FACE(cc by-nc-nd 표기) + SCRFD 라벨(비상업 연구 전용 표기)** | 10-29 초안에 썼다가 10-30 교체. 납품물에는 7.1 사전학습 가중치 줄에 걸림 |
| OpenCV (`opencv-python-headless`) | 5.0.0.93 | Apache-2.0(OpenCV), MIT(휠), LGPL-2.1(동봉 FFmpeg, 수정 없음) | 휠 `LICENSE.txt`, `LICENSE-3RD-PARTY.txt` | Apache-2.0 4조 배포 허용. LGPL은 라이브러리 수정 없이 사용 | 해당 없음 | 기록 |
| ffmpeg·ffprobe (실행 파일) | Debian 7:7.1.5-0+deb13u1 | GPL-2+ (libx264 포함 빌드) | Debian `ffmpeg` 패키지 copyright | 프로세스로만 호출, 링크 없음. 납품물에 넣지 않고 운영자가 설치(권고) | 해당 없음 | 기록. 배포 방식 결정 필요(8절) |
| 백엔드 Python 라이브러리 15종(6.1)과 함께 설치되는 23종(6.2) | 표 참조 | MIT·BSD·Apache·PSF, certifi만 MPL-2.0 | 각 배포본의 LICENSE·메타데이터 | 모두 상업 이용 허용, 소스 공개 의무 없음 | 해당 없음 | 기록 |
| PostgreSQL | 17 | PostgreSQL License | postgresql.org/about/licence | 무제한 사용·배포 | 해당 없음 | 기록 |

## 8. 확인 필요 목록

1. **얼굴 검출 모델의 학습 데이터 조건.** 해결(10-30): YuNet(WIDER FACE 비상업 표기)을 BlazeFace(Apache-2.0, 구글 동의 데이터)로 바꿔 7.1에 걸릴 것이 없어졌다. D-11에는 두 모델을 모두 기록한다(7절). 담당 조영운, 완료.
2. **팀 서비스(백엔드·프론트)가 납품물 범위인지.** 답(10-30 조영운): 기본은 아니다(회사에 자체 서비스가 있음). 다만 회사가 프론트를 마음에 들어 하면 백엔드까지 가져갈 수 있다. 그래서 가져가도 문제가 없는 모델로 바꿨고, 11-03 멘토링에는 보고만 한다(10절).
3. **ffmpeg 배포 방식.** 도커 이미지를 기업에 전달할지, 운영자가 OS 패키지로 설치할지. 후자를 권한다(5.3). 회사가 팀 서비스를 가져갈 때만 의미가 있다. 담당: 허정원·팀장.
4. **H.264 특허.** 기업이 결과 영상을 상업 서비스로 내보낼 때의 문제라 기업 법무 몫이다. 필요하면 VP9·AV1로 바꿀 수 있다(5.3).
5. **OpenCV 휠의 LGPL FFmpeg.** 의무는 없지만 D-11에 "수정 없이 동봉"으로 적는다. AI 파트 `opencv-python`도 같다.
6. **certifi(MPL-2.0).** 기록만.
7. **WeasyPrint의 시스템 라이브러리**(Pango·Cairo, LGPL). 보고서 작업 단위를 시작할 때 다시 본다.

## 9. 출처 (2026-10-29·30 확인)

- 세부명세서: `크림오프_세부명세서.pdf` 7절(PR-C-02·03·04·07), 7.1절, 9절, 10.1절.
- MediaPipe BlazeFace 모델 카드: https://storage.googleapis.com/mediapipe-assets/MediaPipe%20BlazeFace%20Model%20Card%20(Full%20Range).pdf, 같은 경로의 (Short%20Range).pdf. 모델 안내: https://developers.google.com/edge/mediapipe/solutions/vision/face_detector. 모델 파일: https://storage.googleapis.com/mediapipe-assets/face_detection_full_range.tflite. 그래프 설정(앵커·점수 해석·전처리): MediaPipe 저장소 `mediapipe/modules/face_detection/face_detection_full_range.pbtxt`, `face_detection.pbtxt`. 저장소 LICENSE: https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE
- 변환 도구: tf2onnx https://github.com/onnx/tensorflow-onnx (Apache-2.0), 개발 PC에서만 사용.
- opencv_zoo YuNet: https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet (README·LICENSE), 저장소 README의 라이선스 문장.
- YuNet 학습: https://github.com/ShiqiYu/libfacedetection.train (README "training on WIDER Face", "labelv2 annotations come from SCRFD").
- WIDER FACE: http://shuoyang1213.me/WIDERFACE/ (License: Creative Common License (cc by-nc-nd)).
- InsightFace: https://github.com/deepinsight/insightface (README License 절).
- Ultralytics 라이선스: https://github.com/ultralytics/ultralytics/blob/main/LICENSE (AGPL-3.0).
- dlib 모델: https://github.com/davisking/dlib-models (README).
- Debian ffmpeg: https://tracker.debian.org/pkg/ffmpeg, https://sources.debian.org/src/ffmpeg/trixie/debian/copyright/, https://sources.debian.org/src/ffmpeg/trixie/debian/rules/
- python 이미지 태그: https://github.com/docker-library/official-images/blob/master/library/python (`3.11-slim` → `3.11/slim-trixie`).
- x264: https://www.videolan.org/developers/x264.html
- OpenCV 휠: `.venv/Lib/site-packages/opencv_python_headless-5.0.0.93.dist-info/LICENSE.txt`, `LICENSE-3RD-PARTY.txt`, `cv2.getBuildInformation()`.
- Python 패키지 라이선스: 각 배포본 `METADATA`의 License-Expression·Classifier(`importlib.metadata`로 읽음).
- 검증 자료(저장소에 넣지 않음): 회사 프레임 20장(`calib_kit_1027`, 사람 얼굴이 찍힌 자료), 시험 스크립트와 결과 그림은 조영운 PC의 세션 임시 폴더.

## 10. 11-03 멘토링 보고 내용

질문이 아니라 보고다. 회사 답을 기다릴 것은 없다.

```text
[보고] 결과 영상 얼굴 가리기 모델의 라이선스

- 팀 서비스는 결과 영상을 만들 때 영상에 찍힌 보호자·직원의 얼굴을 자동으로 가립니다(REQ-CM-003, PR-C-03).
- 얼굴 검출 모델은 처음에 OpenCV YuNet(모델 파일 MIT)을 썼는데, 학습 데이터 WIDER FACE가 비상업(CC BY-NC-ND)
  표기이고 라벨도 비상업 연구 전용으로 배포된 것이라, 세부명세서 7.1 "비상업 조건 데이터로 학습한 가중치는 쓸 수 없다"에
  걸릴 수 있어 Google MediaPipe BlazeFace(Apache-2.0, 구글이 동의를 받아 모은 자체 데이터로 학습)로 바꿨습니다.
- 얼굴 위치는 저장하거나 전달하지 않고 가려진 영상만 남습니다. 분석 모델·분석 API·보고서 모듈과는 무관합니다.
- 팀 서비스를 가져가시는 경우, 결과 영상 인코딩에 쓰는 ffmpeg(GPL)는 저희 배포 이미지에 넣지 않고 운영 담당자가
  OS 패키지로 설치하는 방식을 권합니다. 가져가지 않으시면 해당 사항이 없습니다.
```

보고 뒤 회사가 달리 요청하면 백엔드 명세 10절 Q24의 답 칸과 이 문서 0절에 적는다.
