# 빌드: React 정적 파일 생성
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 실행: nginx로 정적 파일 서빙 (리버스 프록시가 frontend:80 으로 넘김)
FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# React 라우터 경로를 새로고침해도 index.html 로 떨어지게 한다
RUN printf 'server {\n    listen 80;\n    root /usr/share/nginx/html;\n    location / {\n        try_files $uri /index.html;\n    }\n}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
