import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './store/actions_backend' // 백엔드에 있는 기능은 먼저 백엔드로(가짜 서버 모드에서는 등록 안 함)
import './store/actions_impl' // 폼 처리 함수 등록(시제품 main.py 의 POST 주소)
import { setLogin } from './app/session'
import { MOCK, restore } from './store/backend'
import { startPolling } from './store/sessions_backend'
import { current } from './app/session'

// 백엔드 모드: 저장된 토큰이 살아 있으면 로그인 상태와 반려견 목록을 먼저 읽는다
const start = MOCK ? Promise.resolve(null) : restore()
start.then((sid) => {
  if (sid) setLogin(sid)
  if (!MOCK) startPolling(current)   // 백엔드 분석 작업이 끝났는지 서버를 읽는다
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
})
