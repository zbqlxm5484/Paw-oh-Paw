import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// 병원용 결과 조회 웹(D-06). 화면은 prototype/ 의 웹을 그대로 옮긴 것이다.
// 개발 서버에서 /api 를 백엔드로 넘긴다(배포에서는 nginx). --mode mock 이면 브라우저 안 가짜 서버(MSW)가 모든 API 를 받는다.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000'
  return {
    plugins: [react()],
    server: { port: 5174, proxy: { '/api': { target: apiTarget, changeOrigin: true } } },
    preview: { port: 5174 },
  }
})
