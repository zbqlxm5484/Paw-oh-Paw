# 화면 이미지: 모바일 앱 화면(frontend/)은 / 에, 병원용 결과 조회 웹(web/)은 /web/ 에 둔다.
# compose 의 web-blue·web-green 이 이 파일로 빌드한다. 리버스 프록시(infra/docker/nginx.conf)는 / 전체를 이 컨테이너로 넘긴다.

# 앱 빌드
FROM node:22-alpine AS app
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 웹 빌드. 정적 파일·라우터 주소가 /web/ 아래가 되도록 VITE_BASE 를 준다.
# 시연용 예시 기관(src/mocks/fixture.json, AI-Hub 회차만)이 화면에 같이 들어가 백엔드 없이도 둘러볼 수 있다
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
ENV VITE_BASE=/web/
RUN npm run build

# 실행: nginx 로 정적 파일 서빙
FROM nginx:stable-alpine
COPY --from=app /app/dist /usr/share/nginx/html
COPY --from=web /web/dist /usr/share/nginx/html/web
# React 라우터 경로를 새로고침해도 각자 index.html 로 떨어지게 한다.
# absolute_redirect off: /web → /web/ 301 을 상대 주소로 보낸다(앞단 https·포트가 바뀌지 않게, MR !79 리뷰)
RUN printf 'server {\n    listen 80;\n    root /usr/share/nginx/html;\n    absolute_redirect off;\n    location = /web { return 301 /web/; }\n    location /web/ {\n        try_files $uri /web/index.html;\n    }\n    location / {\n        try_files $uri /index.html;\n    }\n}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
