import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // 개발 서버에서 /api 를 백엔드로 넘긴다. 배포에서는 nginx가 같은 일을 한다(infra/docker/nginx.conf).
  const apiTarget = env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000'
  // 안드로이드(Capacitor) 번들에는 서비스 워커를 넣지 않는다. WebView 안에서는 설치·캐시가 뜻이 없고 서명 주소 갱신을 방해한다
  const native = env.VITE_NATIVE === '1'
  return {
    plugins: [
      react(),
      // 폰 홈 화면에 "앱"으로 설치되게 한다(screenPlan 11단계). API 응답은 캐시하지 않는다
      !native && VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['favicon.svg', 'icon.svg'],
        manifest: {
          name: 'Paw oh Paw',
          short_name: 'Paw oh Paw',
          description: '반려견 보행 분석 · 크림오프 팀 서비스',
          lang: 'ko',
          start_url: '/',
          display: 'standalone',
          orientation: 'portrait',
          background_color: '#FAF9F6',
          theme_color: '#FAF9F6',
          icons: [
            { src: '/icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
            { src: '/icon-maskable.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'maskable' },
          ],
        },
        workbox: {
          // 화면 파일만 미리 캐시. /api 는 네트워크만 쓴다(폴링·서명 주소가 캐시되면 안 된다)
          globPatterns: ['**/*.{js,css,html,svg,woff2}'],
          navigateFallbackDenylist: [/^\/api\//],
          runtimeCaching: [],
        },
        devOptions: { enabled: false },
      }),
    ].filter(Boolean),
    server: {
      port: 5173,
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
      },
    },
  }
})
