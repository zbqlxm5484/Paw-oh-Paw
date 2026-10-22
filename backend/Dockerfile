# Python 3.11 + requirements.txt 버전 고정 (PR-C-07)
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
EXPOSE 8000
# 진입점은 backend/app/main.py → app.main. nginx 뒤라 X-Forwarded-* 를 믿는다. 접근 로그는 앱 미들웨어가 대신 남긴다(backend/README)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips=*"]
