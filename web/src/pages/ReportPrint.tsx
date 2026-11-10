// 인쇄 전용 보고서 화면 /print/reports/:rid?edition=OWNER|VET[&token=…] (type=g|v 도 받음) (S15P31A404-285)
// 서버가 headless Chrome(Gotenberg)으로 이 주소를 열어 PDF 로 인쇄한다. 메뉴·버튼·오른쪽 칸 없이 보고서 종이만 그린다.
// 다 그리면 window.__REPORT_READY__ = true 와 <body data-report-ready="1"> 로 인쇄해도 된다고 알린다(Gotenberg waitForExpression).
//
// 내용: 서버 보고서 내용 API(GET /sessions/{id}/report-content)를 먼저 부르고, 받으면 그 글·숫자로만 그린다(ServerReportPaper).
// - 주소에 token 이 있으면(서버 워커) 로그인 없이 그 인쇄 토큰으로 부른다. 없으면 지금 로그인 상태로 부른다.
// - 404·409 SESSION_NOT_DONE·그 밖의 실패 → 이 화면이 계산하는 종이(ReportPaper)로 대신한다(로그인 상태일 때만 가능).
// - 409 REPORT_CHECK_FAILED → 종이 없이 안내만(서버는 이 경우 PDF 를 만들지 않는다). 준비 완료도 알리지 않는다.
// - 수의사용 뒷무릎 곡선은 같은 토큰으로 GET /sessions/{id} → /shots/{id}/angles 를 읽어 실제 각도로만 그린다(views/gaitClip.ts).
//   못 만들면 그 칸을 빼고, 곡선(또는 못 만든다는 결과)을 기다린 뒤 준비 완료를 알린다.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { api, ApiError, type ReportContentOut, type ReportEdition } from '../api/client'
import { css } from '../app/css'
import { usePage, useTitle } from '../app/page'
import { resultOf } from '../store/db'
import { MOCK } from '../store/backend'
import { body_map, result_view } from '../views/views'
import { ReportPaper } from './Report'
import { ServerReportPaper } from './parts/ServerReportPaper'
import { cardGait, kneeChartView, loadKneeCurve, type KneeChartView } from '../views/reportContent'

declare global {
  interface Window {
    __REPORT_READY__?: boolean
  }
}

function markReady() {
  window.__REPORT_READY__ = true
  document.body.dataset.reportReady = '1'
}

/** 내용 API 결과: undefined = 기다리는 중 */
type Content = { ok: true; c: ReportContentOut } | { ok: false; code: string }

const CHECK_FAILED = 'REPORT_CHECK_FAILED'

/** 회차·판본·토큰이 바뀌면 내용 API 를 다시 부른다. enabled=false 면 부르지 않고 바로 실패(대신 그리기)로 */
function useReportContent(rid: string, edition: ReportEdition, token: string | null, enabled: boolean): Content | undefined {
  const key = `${rid}|${edition}|${token ?? ''}|${enabled}`
  const [state, setState] = useState<{ key: string; v: Content | undefined }>({ key: '', v: undefined })
  useEffect(() => {
    if (!enabled) return
    let alive = true
    api.reportContent(rid, edition, token)
      .then((c) => alive && setState({ key, v: { ok: true, c } }))
      .catch((e) => alive && setState({ key, v: { ok: false, code: e instanceof ApiError ? e.code : 'NETWORK' } }))
    return () => {
      alive = false
    }
  }, [key, rid, edition, token, enabled])
  if (!enabled) return { ok: false, code: 'SKIPPED' }
  return state.key === key ? state.v : undefined
}

function CheckFailed() {
  return (
    <main className="print-main" data-report-error={CHECK_FAILED} style={css('max-width:920px;margin:0 auto;padding:24px')}>
      <p style={css('font-size:15px;color:#5B6472')}>검사에 걸려 보고서를 만들지 않았습니다.</p>
    </main>
  )
}

/** 수의사용 뒷무릎 곡선: 이 회차의 실제 각도로(같은 Bearer 토큰). undefined = 기다리는 중, null = 못 만듦(칸을 뺀다) */
function useKnee(c: ReportContentOut, token: string | null): KneeChartView | null | undefined {
  const want = c.edition === 'VET'
  const prefer = cardGait(c)?.gait_type ?? null
  const key = `${c.session_id}|${prefer}|${token ?? ''}|${want}`
  const [state, setState] = useState<{ key: string; v: KneeChartView | null }>({ key: '', v: null })
  useEffect(() => {
    if (!want) return
    let alive = true
    loadKneeCurve({ session: (id) => api.session(id, token), angles: (id) => api.angles(id, token) }, c.session_id, prefer)
      .then((k) => alive && setState({ key, v: k ? kneeChartView(k) : null }))
    return () => {
      alive = false
    }
  }, [key, want, c.session_id, prefer, token])
  if (!want) return null
  return state.key === key ? state.v : undefined
}

function ServerPage({ c, token }: { c: ReportContentOut; token: string | null }) {
  useTitle(`${c.sentences.title} (${c.sentences.edition_label})`)
  const knee = useKnee(c, token)
  // 서버 내용은 받은 그대로 그린다. 수의사용은 무릎 곡선(또는 못 만든다는 결과)을 기다린 뒤 준비 완료
  useEffect(() => {
    if (knee !== undefined) markReady()
  }, [c, knee])
  if (knee === undefined) return null
  return (
    <main className="print-main print-only" style={css('max-width:920px;margin:0 auto;padding:24px 0;background:#fff')}>
      <ServerReportPaper c={c} knee={knee} />
    </main>
  )
}

export default function ReportPrint() {
  const { rid = '' } = useParams()
  const [query] = useSearchParams()
  // 판본: 서버 워커는 edition=OWNER|VET 로 부른다(백엔드 명세와 같은 이름). 화면 주소처럼 type=g|v 도 받는다
  const edition = (query.get('edition') || '').toUpperCase()
  const type = edition === 'VET' || (!edition && query.get('type') === 'v') ? 'v' : 'g'
  const token = query.get('token')

  // 회차·판본이 바뀌면 그리기 전에 '준비 안 됨'으로 되돌린다. 효과(useEffect)로 하면 자식(VetSections)이 먼저 준비 완료를 알린 뒤에 덮어써 버린다
  const shown = useRef('')
  if (shown.current !== rid + type) {
    shown.current = rid + type
    window.__REPORT_READY__ = false
    delete document.body.dataset.reportReady
  }
  return token ? <TokenPrint rid={rid} type={type} token={token} /> : <LoginPrint rid={rid} type={type} />
}

/** 인쇄 토큰만으로(로그인 없이): 서버 내용으로만 그릴 수 있다 */
function TokenPrint({ rid, type, token }: { rid: string; type: string; token: string }) {
  const content = useReportContent(rid, type === 'v' ? 'VET' : 'OWNER', token, true)
  useTitle('분석 결과')
  if (!content) return null
  if (content.ok) return <ServerPage c={content.c} token={token} />
  if (content.code === CHECK_FAILED) return <CheckFailed />
  // 로그인 없이 화면 계산 종이는 그릴 수 없다 → 안내만(준비 완료를 알리지 않아 서버 워커는 실패로 본다)
  return (
    <main className="print-main" data-report-error={content.code} style={css('max-width:920px;margin:0 auto;padding:24px')}>
      <p style={css('font-size:15px;color:#5B6472')}>보고서 내용을 불러오지 못했습니다.</p>
    </main>
  )
}

/** 로그인 상태: 서버 내용이 있으면 그것으로, 없으면 이 화면이 계산한 종이로 */
function LoginPrint({ rid, type }: { rid: string; type: string }) {
  const { acct } = usePage({ login: true })
  const r = acct ? resultOf(acct, rid) : undefined
  const v = acct && r ? result_view(acct, r) : null
  const fail = !r || r.st === 'fail'
  const bm = acct && r && !fail ? body_map(acct, r) : null
  const kind = fail ? 'v' : type
  const fromServer = !MOCK && (r?.src ?? '').startsWith('backend:')
  // 서버 회차(또는 가짜 서버)일 때만 내용 API 를 부른다. 시연 데이터 회차는 서버에 없다
  const content = useReportContent(rid,kind === 'v' ? 'VET' : 'OWNER', null, !!r && !fail && (fromServer || MOCK))
  const useServer = content?.ok === true
  useTitle(useServer ? `${content.c.sentences.title} (${content.c.sentences.edition_label})` : v ? `${v.rd.name} 분석 결과 (${kind === 'v' ? '수의사용' : '보호자용'})` : '분석 결과')
  const onReady = useCallback(() => markReady(), [])
  const fallback = content !== undefined && !content.ok && content.code !== CHECK_FAILED

  // 대신 그리는 종이: 보호자용은 비교 API 를 기다릴 게 없어서 그리자마자 준비 완료. 수의사용은 VetSections 가 비교 값을 받은 뒤 onReady 를 부른다
  useEffect(() => {
    if (fallback && bm && kind === 'g') markReady()
  }, [fallback, bm, kind])
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
  if (content === undefined) return null
  if (content.ok) return <ServerPage c={content.c} token={null} />
  if (content.code === CHECK_FAILED) return <CheckFailed />
  return (
    <main className="print-main print-only" data-report-source="local" style={css('max-width:920px;margin:0 auto;padding:24px 0;background:#fff')}>
      <ReportPaper acct={acct} r={r} rd={v.rd} rp={v.rp} bm={bm} kind={kind} fromServer={fromServer} onReady={onReady} />
    </main>
  )
}
