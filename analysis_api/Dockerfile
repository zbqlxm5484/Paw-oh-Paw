# 분석 API (FastAPI). 빌드 컨텍스트는 저장소 루트다: docker build -f analysis_api/Dockerfile -t analysis-api .
# engine/ 을 함께 넣어야 pipeline.py 가 import 할 수 있다(저장소 루트의 engine 패키지를 쓴다)
FROM python:3.11-slim
WORKDIR /app
COPY analysis_api/requirements.txt ./analysis_api/
RUN pip install --no-cache-dir -r analysis_api/requirements.txt
COPY engine/ ./engine/
COPY analysis_api/ ./analysis_api/
# 올린 영상 저장 위치. 컨테이너를 다시 만들어도 남기려면 볼륨을 붙인다
ENV ANALYSIS_STORAGE_DIR=/data/analysis_api
RUN useradd --system --no-create-home app && mkdir -p /data/analysis_api && chown -R app /data
USER app
WORKDIR /app/analysis_api
EXPOSE 8010
# /health 는 인증 없이 열려 있다(README)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/health')"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
