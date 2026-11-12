# Python 3.11 + requirements.txt 버전 고정 (PR-C-07)
FROM python:3.11-slim
WORKDIR /app
# ffmpeg(ffprobe 포함): 업로드 영상 검사와 결과 영상 인코딩. pip이 아니라 OS 패키지라 requirements.txt 밖에 둔다
# libpango-1.0-0·libpangoft2-1.0-0: WeasyPrint가 PDF 보고서를 그릴 때 쓴다. fonts-nanum: 보고서·차트의 한글 글꼴(NanumGothic)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libpango-1.0-0 libpangoft2-1.0-0 fonts-nanum \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
EXPOSE 8000
# 진입점은 backend/app/main.py → app.main. nginx 뒤라 X-Forwarded-* 를 믿는다. 접근 로그는 앱 미들웨어가 대신 남긴다(backend/README)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips=*"]
