# Python 3.11 + requirements.txt 버전 고정 (PR-C-07)
FROM python:3.11-slim
WORKDIR /app
COPY fastapi/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY fastapi/ ./
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
