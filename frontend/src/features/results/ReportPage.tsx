import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { EDITION_LABEL, REPORT_STATUS_LABEL, fileUrl, fmtMonthDay } from '../../api/labels'
import { useRegenerateReport, useReports } from '../../api/results'
import { useSession } from '../../api/sessions'
import type { Edition } from '../../api/types'
import { useToast } from '../../app/toast'
import { Button, Empty, TopBar } from '../../components/ui'
import './results.css'

/**
 * S6 보고서. 디자인 v5 `report`. 본문은 서버가 만든 PDF 를 그대로 보여 주고(PR-F09-05), 화면은 판본 전환·상태·내려받기만 한다.
 * 3초 폴링은 useReports 가 한다. 주소가 만료되면(403) 다시 조회해 새 주소를 받는다.
 */
export function ReportPage() {
  const { sessionId } = useParams()
  const nav = useNavigate()
  const toast = useToast()
  const sessQ = useSession(sessionId)
  const repQ = useReports(sessionId)
  const regen = useRegenerateReport(sessionId ?? '')
  const [edition, setEdition] = useState<Edition>('OWNER')
  // 미리보기는 주소를 받아 와서 보여 준다. <iframe src> 에 바로 넣으면 403(만료)을 알 수 없어서다
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [previewErr, setPreviewErr] = useState<string | null>(null)

  const s = sessQ.data
  const reports = repQ.data?.reports ?? []
  const cur = reports.find((r) => r.edition === edition)
  const url = fileUrl(cur?.file_url)
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(t)
  }, [])
  const expired = cur?.url_expires_at ? Date.parse(cur.url_expires_at) <= now : false

  useEffect(() => {
    if (!url || expired) {
      setBlobUrl(null)
      return
    }
    let alive = true
    let objUrl: string | null = null
    setPreviewErr(null)
    fetch(url)
      .then(async (r) => {
        if (!r.ok) {
          if (r.status === 403) repQ.refetch()
          throw new Error(r.status === 403 ? '주소가 만료돼 새로 받아요' : '미리보기를 불러오지 못했어요')
        }
        const blob = await r.blob()
        objUrl = URL.createObjectURL(blob)
        if (alive) setBlobUrl(objUrl)
      })
      .catch((e: unknown) => {
        if (alive) setPreviewErr(e instanceof Error ? e.message : '미리보기를 불러오지 못했어요')
      })
    return () => {
      alive = false
      if (objUrl) URL.revokeObjectURL(objUrl)
    }
    // repQ 는 refetch 만 쓴다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, expired])

  async function doRegen() {
    if (!cur) return
    try {
      await regen.mutateAsync(cur.id)
      toast(`${EDITION_LABEL[edition]} 보고서를 다시 만들어요`)
    } catch (err) {
      toast(err instanceof Error ? err.message : '다시 만들지 못했어요')
    }
  }

  function download() {
    const d = fileUrl(cur?.download_url)
    if (!d) return toast('보고서가 아직 준비되지 않았어요')
    if (expired) {
      repQ.refetch()
      return toast('주소가 만료돼 새로 받아요. 잠시 후 다시 눌러 주세요')
    }
    const a = document.createElement('a')
    a.href = d
    a.rel = 'noopener'
    a.target = '_blank'
    a.click()
  }

  const statusTone = cur?.status === 'DONE' ? 'var(--ok)' : cur?.status === 'FAILED' ? 'var(--bad)' : 'var(--warn)'
  const statusText = !repQ.data
    ? '불러오는 중'
    : repQ.data.session_status !== 'DONE'
      ? '회차 집계가 끝나면 보고서를 만들어요'
      : !cur
        ? '보고서를 만들 차례예요'
        : cur.status === 'DONE'
          ? `${REPORT_STATUS_LABEL.DONE} · ${new Date(cur.updated_at).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}${cur.generation_ms ? ` · ${(cur.generation_ms / 1000).toFixed(1)}초` : ''}`
          : cur.status === 'FAILED'
            ? (cur.fail_reason?.message ?? '보고서를 만들지 못했습니다.')
            : `${REPORT_STATUS_LABEL[cur.status]}… 3초마다 확인해요`

  return (
    <div className="screen report-screen">
      <TopBar title="보고서" onBack={() => nav(`/sessions/${sessionId}/result`)} />
      <div style={{ flex: 'none', padding: '0 20px 12px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div className="seg" style={{ gridTemplateColumns: '1fr 1fr', background: '#E2D9CC' }}>
          {(['OWNER', 'VET'] as Edition[]).map((e) => (
            <button key={e} type="button" className={edition === e ? 'on' : ''} onClick={() => setEdition(e)}>
              {EDITION_LABEL[e]}
            </button>
          ))}
        </div>
        <div className="report-status tabular">
          <i style={{ background: statusTone }} />
          {statusText}
          {s && (
            <span style={{ marginLeft: 'auto' }}>
              {s.dog.name} · {fmtMonthDay(s.measured_on)}
            </span>
          )}
        </div>
      </div>
      <div className="scroll" style={{ padding: '0 20px 24px' }}>
        {repQ.isError && <Empty>{repQ.error instanceof ApiError ? repQ.error.message : '보고서 상태를 불러오지 못했어요'}</Empty>}
        {!repQ.isError && (
          <div className="report-paper">
            {url && !expired && blobUrl ? (
              <iframe key={blobUrl} src={blobUrl} title={`${EDITION_LABEL[edition]} 보고서 미리보기`} />
            ) : url && !expired && !previewErr ? (
              <div className="skeleton" style={{ height: 560, borderRadius: 6 }} />
            ) : (
              <div style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 10, color: 'var(--sub)', fontSize: 14, lineHeight: 1.6 }}>
                <b style={{ color: 'var(--ink)', fontSize: 16 }}>{EDITION_LABEL[edition]} 보고서</b>
                {previewErr ? (
                  <span>{previewErr}</span>
                ) : expired ? (
                  <>
                    <span>미리보기 주소가 만료됐어요.</span>
                    <Button size="md" variant="secondary" style={{ width: 'auto', padding: '0 16px' }} onClick={() => repQ.refetch()}>
                      새 주소 받기
                    </Button>
                  </>
                ) : cur?.status === 'FAILED' ? (
                  <span>{cur.fail_reason?.message ?? '보고서를 만들지 못했습니다.'} 아래 ‘다시 만들기’로 다시 시도할 수 있어요.</span>
                ) : (
                  <span>{repQ.data?.session_status === 'DONE' ? '보고서를 만드는 중이에요. 보통 20초 안에 끝나요.' : '회차 집계가 끝나면 보호자용·수의사용 보고서를 자동으로 만들어요.'}</span>
                )}
              </div>
            )}
          </div>
        )}
        <p className="small" style={{ color: 'var(--dim)', marginTop: 10, lineHeight: 1.5 }}>
          보행 평가 보조 자료이며 진단을 대신하지 않습니다. 보호자에게는 담당자가 내려받아 전달해요.
        </p>
      </div>
      <div className="sticky-footer" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <Button variant="secondary" onClick={doRegen} disabled={!cur || cur.status === 'GENERATING' || cur.status === 'PENDING' || regen.isPending}>
          다시 만들기
        </Button>
        <Button onClick={download} dim={!cur || cur.status !== 'DONE'}>
          PDF 내려받기
        </Button>
      </div>
    </div>
  )
}
