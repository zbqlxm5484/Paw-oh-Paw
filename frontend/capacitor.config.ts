import type { CapacitorConfig } from '@capacitor/cli'

/**
 * Capacitor 설정(안드로이드 포장). 같은 React 빌드(dist/)를 WebView 에 넣는다.
 * 앱 안에서는 상대 주소 /api/v1 이 서버를 가리키지 않으므로, 빌드할 때 VITE_API_BASE 로 서버 주소를 넣어야 한다(npm run build:android).
 * 백엔드 CORS_ORIGINS 에 https://localhost (Capacitor Android 기본 origin)를 더해 달라고 해야 한다.
 */
const config: CapacitorConfig = {
  appId: 'kr.creamoff.pawohpaw',
  appName: 'Paw oh Paw',
  webDir: 'dist',
  android: {
    // 결과 영상·PDF 서명 주소와 http 개발 서버를 WebView 가 막지 않게
    allowMixedContent: true,
  },
  server: {
    // 로컬 개발 서버 연결은 .env.android 의 CAP_SERVER_URL 로 (아래 주석 참고). 기본은 번들된 dist 를 쓴다
    androidScheme: 'https',
  },
}

export default config
