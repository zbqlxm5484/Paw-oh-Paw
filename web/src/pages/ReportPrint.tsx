// 인쇄 전용 보고서 화면 /print/reports/:rid?edition=OWNER|VET (type=g|v 도 받음) (S15P31A404-285)
// 서버가 headless Chrome(Gotenberg)으로 이 주소를 열어 PDF 로 인쇄한다. 메뉴·버튼·오른쪽 칸 없이 보고서 종이만 그린다.
// 다 그리면 window.__REPORT_READY__ = true 와 <body data-report-ready="1"> 로 인쇄해도 된다고 알린다(Gotenberg waitForExpression).
// 지금은 로그인한 상태의 회차 결과로 그린다. 인쇄 토큰·서버 보고서 문장 API 가 생기면 그 값으로 바꾼다.
import { useCallback, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
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
  const { acct, query } = usePage({ login: true })
  // 판본: 서버 워커는 edition=OWNER|VET 로 부른다(백엔드 명세와 같은 이름). 화면 주소처럼 type=g|v 도 받는다
  const edition = (query.get('edition') || '').toUpperCase()
  const type = edition === 'VET' || (!edition && query.get('type') === 'v') ? 'v' : 'g'
  const r = acct ? resultOf(acct, rid) : undefined
  const v = acct && r ? result_view(acct, r) : null
  const fail = !r || r.st === 'fail'
  const bm = acct && r && !fail ? body_map(acct, r) : null
  const kind = fail ? 'v' : type
  useTitle(v ? `${v.rd.name} 분석 결과 (${kind === 'v' ? '수의사용' : '보호자용'})` : '분석 결과')
  const fromServer = !MOCK && (r?.src ?? '').startsWith('backend:')
  const onReady = useCallback(() => markReady(), [])

  // 회차·판본이 바뀌면 그리기 전에 '준비 안 됨'으로 되돌린다. 효과(useEffect)로 하면 자식(VetSections)이 먼저 준비 완료를 알린 뒤에 덮어써 버린다
  const shown = useRef('')
  if (shown.current !== rid + type) {
    shown.current = rid + type
    window.__REPORT_READY__ = false
    delete document.body.dataset.reportReady
  }
  // 보호자용은 비교 API 를 기다릴 게 없어서 그리자마자 준비 완료. 수의사용은 VetSections 가 비교 값을 받은 뒤 onReady 를 부른다
  useEffect(() => {
    if (bm && kind === 'g') markReady()
  }, [bm, kind])
  // 분석 실패 회차는 그릴 보고서가 없다 → 실패 안내만 그리고 준비 완료(서버는 이 회차의 PDF 를 만들지 않는다)
  useEffect(() => {
    if (acct && r && fail) markReady()
  }, [acct, r, fail])

  if (!acct || !r || !v) return null
  if (fail || !bm)
    return (
      <main className="print-main" style={css('max-width:920px;margin:0 auto;padding:24px')}>
        <b style={css('font-size:20px')}>{v.rd.name} · {v.rd.when}</b>
        <p style={css('font-size:15px;color:#5B6472')}>이 회차는 분석하지 못해 보고서가 없습니다.</p>
      </main>
    )
  return (
    <main className="print-main print-only" style={css('max-width:920px;margin:0 auto;padding:24px 0;background:#fff')}>
      <ReportPaper acct={acct} r={r} rd={v.rd} rp={v.rp} bm={bm} kind={kind} fromServer={fromServer} onReady={onReady} />
    </main>
  )
}
