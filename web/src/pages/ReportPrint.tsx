// 인쇄 전용 보고서 화면 /print/reports/:rid?edition=OWNER|VET[&token=…] (type=g|v 도 받음) (S15P31A404-285)
// 서버가 headless Chrome(Gotenberg)으로 이 주소를 열어 PDF 로 만든다. 웹·앱의 PDF 는 모두 이 파일이다.
// 보고서 화면(/results/:rid)과 똑같은 종이(ReportPaper)를 같은 데이터로 그린다. 메뉴·버튼·오른쪽 칸만 없다.
// - 주소에 token 이 있으면(서버 워커) main.tsx 가 그 인쇄 토큰으로 로그인한 상태를 만든다. 없으면 지금 로그인 상태로 그린다.
// - 다 그리면 window.__REPORT_READY__ = true 와 <body data-report-ready="1"> 로 인쇄해도 된다고 알린다(Gotenberg waitForExpression).
//   보호자용은 그리자마자, 수의사용은 VetSections 가 비교 값·무릎 곡선을 받은 뒤(onReady).
// - 종이 폭은 보고서 화면과 같은 892px 로 고정하고, 쪽 크기(@page)도 그 폭에 맞춘다(app.css). 그래서 화면과 같은 줄바꿈으로 찍힌다.
import { useCallback, useEffect, useRef } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { css } from '../app/css'
import { usePage, useTitle } from '../app/page'
import { resultOf } from '../store/db'
import { MOCK } from '../store/backend'
import { body_map, result_view } from '../views/views'
import { ReportPaper } from './Report'

declare global {
  interface Window {
    __REPORT_READY__?: boolean
  }
}

function markReady() {
  window.__REPORT_READY__ = true
  document.body.dataset.reportReady = '1'
}

export default function ReportPrint() {
  const { rid = '' } = useParams()
  const [query] = useSearchParams()
  // 판본: 서버 워커는 edition=OWNER|VET 로 부른다(백엔드 명세와 같은 이름). 화면 주소처럼 type=g|v 도 받는다
  const edition = (query.get('edition') || '').toUpperCase()
  const type = edition === 'VET' || (!edition && query.get('type') === 'v') ? 'v' : 'g'

  // 회차·판본이 바뀌면 그리기 전에 '준비 안 됨'으로 되돌린다. 효과(useEffect)로 하면 자식(VetSections)이 먼저 준비 완료를 알린 뒤에 덮어써 버린다
  const shown = useRef('')
  if (shown.current !== rid + type) {
    shown.current = rid + type
    window.__REPORT_READY__ = false
    delete document.body.dataset.reportReady
  }

  const { acct } = usePage({ login: true })
  const r = acct ? resultOf(acct, rid) : undefined
  const v = acct && r ? result_view(acct, r) : null
  const fail = !r || r.st === 'fail'
  const bm = acct && r && !fail ? body_map(acct, r) : null
  const kind = fail ? 'v' : type
  const fromServer = !MOCK && (r?.src ?? '').startsWith('backend:')
  useTitle(v ? `${v.rd.name} 분석 결과 (${kind === 'v' ? '수의사용' : '보호자용'})` : '분석 결과')
  const onReady = useCallback(() => markReady(), [])

  // 보호자용은 기다릴 것이 없어 그리자마자 준비 완료. 수의사용은 VetSections 가 onReady 를 부른다
  useEffect(() => {
    if (bm && kind === 'g') markReady()
  }, [bm, kind])
  // 분석 실패 회차는 그릴 보고서가 없다 → 실패 안내만 그리고 준비 완료
  useEffect(() => {
    if (acct && r && fail) markReady()
  }, [acct, r, fail])

  if (!acct || !r || !v) return null
  if (fail || !bm)
    return (
      <main className="print-main print-only" style={css('width:892px;margin:0 auto;padding:24px 0')}>
        <b style={css('font-size:18px')}>{v.rd.name}, {v.rd.when}</b>
        <p style={css('font-size:15px;color:#5B6472')}>이 회차는 분석하지 못해 보고서가 없습니다.</p>
      </main>
    )
  return (
    <main className="print-main print-only" data-report-source="screen" style={css('width:892px;margin:0 auto;padding:0;background:#fff')}>
      <ReportPaper acct={acct} r={r} rd={v.rd} rp={v.rp} bm={bm} kind={kind} fromServer={fromServer} onReady={onReady} />
    </main>
  )
}
