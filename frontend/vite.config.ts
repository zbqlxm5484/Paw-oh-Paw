import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // 개발 서버에서 /api 를 백엔드로 넘긴다. 배포에서는 nginx가 같은 일을 한다(infra/docker/nginx.conf).
  const apiTarget = env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000'
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
      },
    },
  }
})
