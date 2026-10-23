import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { GAIT_LABEL, PAIR_LABEL, SESSION_STATUS_LABEL, SESSION_STATUS_TONE, SIZE_LABEL, fmtMetric, fmtMonthDay, metricLabel } from '../../api/labels'
import { useSessionResult } from '../../api/results'
import { useSession } from '../../api/sessions'
import type { GaitType } from '../../api/types'
import { Icon } from '../../components/Icon'
import { Badge } from '../../components/ui'
import { RankRow, WholeBody, rowsOf } from '../results/SessionResultPage'
import '../results/results.css'

/** 웹 v2 회차 결과: 넓은 폭에 KPI 3개, 다리 비교 요약 + 통과 집계, 지표 표 2단. 값은 폰 화면과 같은 API. */
export function WebDetail() {
  const { sessionId } = useParams()
  const nav = useNavigate()
  const sessQ = useSession(sessionId)
  const resQ = useSessionResult(sessQ.data?.status === 'DONE' ? sessionId : undefined)
  const [gait, setGait] = useState<GaitType | null>(null)
  const s = sessQ.data
  const res = resQ.data
  const gaits = res?.gaits ?? []
  const cur = gait && gaits.some((g) => g.gait_type === gait) ? gait : (gaits.find((g) => g.gait_type === 'TROT') ?? gaits[0])?.gait_type ?? null
  const G = gaits.find((g) => g.gait_type === cur)
  const rows = useMemo(() => (G ? rowsOf(G) : []), [G])

  if (s && s.status !== 'DONE') {
    nav(`/sessions/${s.id}`, { replace: true })
    return null
  }
  const top = G?.limb_compare.find((c) => c.comparable)
  const stifle = G?.limb_compare.find((c) => c.metric_code === 'rom_stifle')
  const stride = G?.limb_compare.find((c) => c.metric_code === 'stride_length' && c.pair === 'HIND') ?? G?.limb_compare.find((c) => c.metric_code === 'stride_length')

  return (
    <main className="web-main" style={{ gap: 20, paddingTop: 24 }}>
      <button type="button" className="web-back" onClick={() => nav('/results')}>
        <Icon name="back" size={16} />
        분석 결과
      </button>
      {sessQ.isError && <div className="web-card" style={{ padding: 24 }}>{sessQ.error instanceof ApiError ? sessQ.error.message : '회차를 불러오지 못했어요'}</div>}
      {s && (
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <h1 className="web-h1">{s.dog.name} · 회차 결과</h1>
            <div className="tabular" style={{ fontSize: 15, color: 'var(--sub)', marginTop: 4 }}>
              {fmtMonthDay(s.measured_on)} · 체중 {s.weight_kg ?? s.dog.weight_kg}kg · {SIZE_LABEL[s.size_class]} · {s.dog.breed}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <Badge tone={SESSION_STATUS_TONE[s.status]}>{SESSION_STATUS_LABEL[s.status]}</Badge>
            <button type="button" className="web-btn" onClick={() => nav(`/dogs/${s.dog_id}/compare?target=${s.id}`)}>
              경과 비교
            </button>
            <button type="button" className="web-btn" onClick={() => nav(`/sessions/${s.id}/shots`)}>
              촬영별 결과
            </button>
            <button type="button" className="web-btn pri" onClick={() => nav(`/sessions/${s.id}/report`)}>
              <Icon name="doc" size={18} />
              보고서 보기
            </button>
          </div>
        </div>
      )}
      {resQ.isPending && s && <div className="skeleton" style={{ height: 220 }} />}
      {resQ.isError && <div className="web-card" style={{ padding: 24 }}>{resQ.error instanceof ApiError ? resQ.error.message : '회차 수치를 불러오지 못했어요'}</div>}
      {res && G && (
        <>
          {res.notices.map((n) => (
            <div key={n.code} className="note-warn" style={{ fontSize: 14.5, padding: '14px 18px' }}>
              {n.message}
            </div>
          ))}
          <div className="web-kpis">
            <div className="web-kpi">
              <div className="k">좌우 차이 지수</div>
              <div className="v tabular">
                {top?.symmetry_index != null ? top.symmetry_index.toFixed(1) : '—'}
                <small>%</small>
              </div>
              <div className="d">{top ? `${PAIR_LABEL[top.pair]} ${metricLabel(top.metric_code)} · 낮을수록 대칭` : '비교 불가'}</div>
            </div>
            <div className="web-kpi">
              <div className="k">뒷무릎 가동 범위 왼 / 오</div>
              <div className="v tabular">
                {stifle?.left != null ? stifle.left.toFixed(0) : '—'}
                <span style={{ color: 'var(--dim)', fontWeight: 500 }}> / </span>
                {stifle?.right != null ? stifle.right.toFixed(0) : '—'}
                <small>°</small>
              </div>
              <div className="d">{stifle?.comparable ? `차이 ${fmtMetric(Math.abs(stifle.diff!), 'deg')}` : (stifle?.reason?.message ?? '측정 불가')}</div>
            </div>
            <div className="web-kpi">
              <div className="k">걸음 길이 왼 / 오 (몸통 대비)</div>
              <div className="v tabular">
                {stride?.left != null ? stride.left.toFixed(0) : '—'}
                <span style={{ color: 'var(--dim)', fontWeight: 500 }}> / </span>
                {stride?.right != null ? stride.right.toFixed(0) : '—'}
                <small>%</small>
              </div>
              <div className="d">{stride?.comparable ? `차이 ${fmtMetric(Math.abs(stride.diff!), 'pct_body')}p` : '비교 불가'}</div>
            </div>
          </div>

          <div className="web-grid-2">
            <div className="dark-card" style={{ borderRadius: 18, padding: 24 }}>
              <span className="eyebrow">다리 비교 요약 · {GAIT_LABEL[G.gait_type]}</span>
              {top ? (
                <>
                  <b className="title" style={{ fontSize: 21 }}>
                    {PAIR_LABEL[top.pair]} {metricLabel(top.metric_code)}에서 좌우 차이가 가장 커요
                  </b>
                  <span className="sub tabular" style={{ fontSize: 14 }}>
                    왼 {fmtMetric(top.left, top.unit)} · 오 {fmtMetric(top.right, top.unit)} · 차이 {fmtMetric(Math.abs(top.diff!), top.unit)}
                    {top.symmetry_index != null ? ` · 좌우 차이 지수 ${top.symmetry_index.toFixed(1)}%` : ''}
                  </span>
                </>
              ) : (
                <b className="title">양쪽을 모두 잰 수치가 없어 좌우를 비교하지 못했어요</b>
              )}
              <hr />
              {G.limb_compare.slice(top ? 1 : 0, top ? 5 : 4).map((c) => (
                <RankRow key={`${c.pair}:${c.metric_code}`} c={c} />
              ))}
              {G.limb_compare
                .filter((c) => !c.comparable)
                .slice(0, 2)
                .map((c) => (
                  <RankRow key={`na:${c.pair}:${c.metric_code}`} c={c} />
                ))}
              <span className="foot">진단이 아닌 좌우 차이 비교예요. 차이가 큰 다리만 알려 드려요.</span>
            </div>
            <div className="web-card" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
              <b style={{ fontSize: 16 }}>통과 집계</b>
              <div className="counts tabular" style={{ gap: 12 }}>
                {[
                  ['측정한 통과', res.pass_counts.measured],
                  ['사용', res.pass_counts.used],
                  ['제외', res.pass_counts.excluded],
                ].map(([k, v]) => (
                  <div key={k}>
                    <div className="k">{k}</div>
                    <div className="v" style={{ fontSize: 30, fontWeight: 800 }}>
                      {v}
                    </div>
                  </div>
                ))}
              </div>
              {res.exclude_summary.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <span style={{ fontSize: 13, color: 'var(--sub)', fontWeight: 600 }}>제외 사유</span>
                  <div className="chips">
                    {res.exclude_summary.map((e) => (
                      <span key={e.code} className="chip tabular" style={{ height: 30 }}>
                        {e.message.replace(/\..*$/, '')} {e.count}회
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <span style={{ fontSize: 13, color: 'var(--dim2)', marginTop: 'auto' }}>
                촬영 {res.shot_counts.total}건 · 실패 {res.shot_counts.failed} · 무효 {res.shot_counts.invalid} · 분석 모델 {res.model_name ?? '-'} {res.model_version ?? ''}
              </span>
            </div>
          </div>

          {gaits.length > 1 && (
            <div className="seg" style={{ gridTemplateColumns: `repeat(${gaits.length}, 1fr)`, width: 360, maxWidth: '100%' }}>
              {gaits.map((g) => (
                <button key={g.gait_type} type="button" className={g.gait_type === G.gait_type ? 'on' : ''} onClick={() => setGait(g.gait_type)}>
                  {GAIT_LABEL[g.gait_type]}
                </button>
              ))}
            </div>
          )}

          <div className="web-grid-2">
            {(['HIND', 'FORE'] as const).map((pair) => {
              const list = rows.filter((r) => r.pair === pair)
              if (!list.length) return null
              return (
                <div className="table" key={pair} style={{ borderRadius: 18 }}>
                  <div className="thead" style={{ fontSize: 13 }}>
                    <span style={{ padding: '13px 0 13px 20px' }}>{PAIR_LABEL[pair]} 지표</span>
                    <span style={{ padding: '13px 6px' }}>왼쪽</span>
                    <span style={{ padding: '13px 6px' }}>오른쪽</span>
                    <span style={{ padding: '13px 6px' }}>차이</span>
                  </div>
                  {list.map((r) => {
                    const l = r.left
                    const rr = r.right
                    if (l?.measurable && rr?.measurable)
                      return (
                        <div className="tr tabular" key={r.code} style={{ fontSize: 15 }}>
                          <span style={{ padding: '11px 0 11px 20px' }}>{metricLabel(r.code)}</span>
                          <span>{fmtMetric(l.value, l.unit)}</span>
                          <span>{fmtMetric(rr.value, rr.unit)}</span>
                          <span>{fmtMetric(Math.abs(l.value! - rr.value!), l.unit)}</span>
                        </div>
                      )
                    const reason = (!l?.measurable ? l?.unmeasurable_reason : rr?.unmeasurable_reason)?.message ?? '한쪽 다리를 재지 못했어요'
                    const side = !l?.measurable && !rr?.measurable ? '' : !l?.measurable ? '왼쪽 ' : '오른쪽 '
                    return (
                      <div className="tr na" key={r.code} style={{ fontSize: 15 }}>
                        <span style={{ padding: '11px 0 11px 20px' }}>{metricLabel(r.code)}</span>
                        <span style={{ fontSize: 13.5 }}>
                          {side}측정 불가 · {reason}
                        </span>
                      </div>
                    )
                  })}
                  <div className="tfoot">거리 수치는 몸통 길이 대비 %예요.</div>
                </div>
              )
            })}
          </div>
          <WholeBody G={G} />
          <span style={{ fontSize: 12.5, color: 'var(--sub)' }}>보행 평가 보조 자료이며 진단을 대신하지 않습니다.</span>
        </>
      )}
    </main>
  )
}
