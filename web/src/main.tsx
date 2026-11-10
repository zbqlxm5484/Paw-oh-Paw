import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './store/actions_backend' // 백엔드에 있는 기능은 먼저 백엔드로(가짜 서버 모드에서는 등록 안 함)
import './store/actions_impl' // 폼 처리 함수 등록(시제품 main.py 의 POST 주소)
import { setLogin } from './app/session'
import { MOCK, limitToDog, restore } from './store/backend'
import { api, tokenStore } from './api/client'
import { startPolling } from './store/sessions_backend'
import { current } from './app/session'

// 서버 PDF(285): 워커의 headless Chrome 이 인쇄 화면을 인쇄 토큰과 함께 연다(/print/reports/:rid?token=…).
// 그 토큰으로 로그인한 것처럼 기관 자료를 읽어, 보고서 화면과 같은 종이(ReportPaper)를 그린다. 토큰은 5분짜리(읽기 전용)
// 인쇄 화면은 그 회차의 반려견 하나만 읽고(limitToDog), 분석 작업 폴링은 하지 않는다
const printRid = /\/print\/reports\/([^/?#]+)/.exec(location.pathname)?.[1] ?? null
const printToken = new URLSearchParams(location.search).get('token')
const printing = !MOCK && !!printToken && !!printRid
if (printing) tokenStore.set(printToken!, new Date(Date.now() + 5 * 60_000).toISOString())
const ready: Promise<unknown> = printing
  ? api.session(printRid!).then((s) => limitToDog(s.dog_id)).catch(() => undefined)
  : Promise.resolve()

// 백엔드 모드: 저장된 토큰이 살아 있으면 로그인 상태와 반려견 목록을 먼저 읽는다
// 가짜 서버 모드: 백엔드에만 있는 API(보고서 내용 285)를 시연 데이터로 흉내 내는 처리 함수를 먼저 등록한다
const start = MOCK ? import('./mocks/reportContent').then(() => null) : ready.then(() => restore())
start.then((sid) => {
  if (sid) setLogin(sid)
  if (!MOCK && !printing) startPolling(current)   // 백엔드 분석 작업이 끝났는지 서버를 읽는다
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
})
