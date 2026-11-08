// 백엔드가 만든 보고서 PDF(GET /sessions/{id}/reports). 판본(보호자용 OWNER·수의사용 VET)마다 미리보기·내려받기·다시 만들기.
// 서버 회차가 아닌 결과(시연 데이터·가짜 서버 모드)나 보고서 API 를 못 쓰면 브라우저 인쇄(print)로 대신한다.
import { useEffect, useRef, useState } from 'react'
import { css } from '../../app/css'
import { ApiError, api, fileHref, type ReportOut } from '../../api/client'

const BTN = 'height:44px;padding:0 18px;border-radius:12px;background:#fff;border:1px solid #E2DCD3;display:flex;align-items:center;font-size:15px;font-weight:700'
const MAIN = 'height:44px;padding:0 18px;border-radius:12px;background:#D2601A;color:#fff;display:flex;align-items:center;font-size:15px;font-weight:700;cursor:pointer'
const POLL_MS = 3000 // 백엔드 명세: PENDING·GENERATING 인 판본이 있는 동안 3초마다

const busy = (r: ReportOut | undefined) => !r || r.status === 'PENDING' || r.status === 'GENERATING'

/** 브라우저 인쇄로 PDF 저장. 저장 대화상자의 파일 이름은 document.title 을 따르므로 인쇄 동안만 제목을 파일명으로 바꾼다 */
export function PrintPdf({ fileName }: { fileName?: string }) {
  const print = () => {
    if (!fileName) return window.print()
    const prev = document.title
    document.title = fileName
    window.addEventListener('afterprint', () => { document.title = prev }, { once: true })
    window.print()
  }
  return <div className="hv-orange" onClick={print} style={css(MAIN)}>PDF 내려받기</div>
}

export function ServerPdf({ sessionId, edition, fileName }: { sessionId: string; edition: 'OWNER' | 'VET'; fileName?: string }) {
  const [rep, setRep] = useState<ReportOut | undefined>()
  const [broken, setBroken] = useState(false) // 보고서 API 를 못 쓰면 인쇄로
  const [tick, setTick] = useState(0) // 다시 만들기 뒤 다시 읽기
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    let timer: number | undefined
    const load = async () => {
      try {
        const out = await api.sessionReports(sessionId)
        if (!alive.current) return
        const r = out.reports.find((x) => x.edition === edition)
        setRep(r)
        if (out.session_status !== 'DONE' || busy(r)) timer = window.setTimeout(load, POLL_MS)
        // 서명 주소는 만료가 있다. 화면을 오래 열어 두면 만료 조금 전에 새 주소를 받는다
        else if (r?.url_expires_at) timer = window.setTimeout(load, Math.max(POLL_MS, Date.parse(r.url_expires_at) - Date.now() - 30_000))
      } catch {
        if (alive.current) setBroken(true)
      }
    }
    load()
    return () => {
      alive.current = false
      if (timer) window.clearTimeout(timer)
    }
  }, [sessionId, edition, tick])

  const regenerate = async () => {
    if (!rep) return
    try {
      setRep(await api.regenerateReport(rep.id))
      setTick((n) => n + 1)
    } catch (e) {
      window.ppToast(e instanceof ApiError && e.code === 'REPORT_IN_PROGRESS' ? '보고서를 만들고 있습니다. 잠시만 기다려 주세요' : '지금은 다시 만들 수 없습니다. 잠시 후 다시 시도해 주세요')
    }
  }

  if (broken) return <PrintPdf fileName={fileName} />
  if (rep?.status === 'DONE' && rep.file_url && rep.download_url) {
    return (
      <>
        <a className="lk hv-border" href={fileHref(rep.file_url)} target="_blank" rel="noopener" style={css(BTN)}>PDF 미리보기</a>
        <a className="lk hv-orange" href={fileHref(rep.download_url)} download={fileName ? `${fileName}.pdf` : undefined} style={css(MAIN)}>PDF 내려받기</a>
      </>
    )
  }
  if (rep?.status === 'FAILED') {
    return (
      <>
        <span style={css('align-self:center;font-size:13.5px;color:#C2412D')}>{rep.fail_reason?.message || '보고서를 만들지 못했습니다'}</span>
        <div className="hv-orange" onClick={regenerate} style={css(MAIN)}>보고서 다시 만들기</div>
      </>
    )
  }
  return <div style={css(MAIN + ';opacity:.55;cursor:default')} title="서버에서 PDF 를 만들고 있습니다">PDF 만드는 중…</div>
}
