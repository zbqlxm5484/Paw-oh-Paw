import { useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { useDog } from '../../api/dogs'
import { JUDGEMENT_LABEL, LIMB_LABEL, PAIR_LABEL, fmtMetric, fmtMonthDay, metricLabel } from '../../api/labels'
import { useCompare, useTrends } from '../../api/results'
import type { CompareItem, MetricLimb, TrendsOut } from '../../api/types'
import { Icon } from '../../components/Icon'
import { Card, Empty, TopBar } from '../../components/ui'
import './results.css'

export const TREND_CODES: [string, string][] = [
  ['rom_stifle', '무릎 가동'],
  ['rom_hip', '고관절 가동'],
  ['stride_length', '걸음 길이'],
  ['stance_ratio', '입각기'],
  ['paw_lift', '발 높이'],
]

export const COMPARE_INVALID_MSG: Record<string, string> = {
  NO_DONE_SESSION: '완료된 회차가 없어요. 측정을 끝내면 비교할 수 있어요.',
  SAME_SESSION: '비교하려면 완료된 회차가 2개 이상 필요해요.',
  NO_PREVIOUS: '이 회차 앞에 완료된 회차가 없어요.',
  NOT_DONE: '지정한 회차가 아직 완료되지 않았어요.',
}

/** S8 경과 비교·추이. 디자인 v5 `compare`. 판정은 서버의 judgement 만 쓰고 "좋아짐·나빠짐"은 쓰지 않는다. */
export function ComparePage() {
  const { dogId } = useParams()
  const [sp] = useSearchParams()
  const nav = useNavigate()
  const dogQ = useDog(dogId)
  const [mode, setMode] = useState<'BASELINE' | 'PREVIOUS'>('BASELINE')
  const [code, setCode] = useState('rom_stifle')
  const target = sp.get('target') ?? undefined
  const cmpQ = useCompare(dogId, { target, base: mode, gait_type: 'TROT' })
  const trQ = useTrends(dogId, { metric_code: code, gait_type: 'TROT' })

  const dog = dogQ.data
  const cmp = cmpQ.data
  const items = useMemo(() => cmp?.items ?? [], [cmp])
  const limbs = useMemo(() => {
    const seen = new Set<MetricLimb>()
    for (const it of items) seen.add(it.limb)
    return [...seen]
  }, [items])

  let invalidMsg: string | null = null
  if (cmpQ.isError) {
    const e = cmpQ.error
    if (e instanceof ApiError && e.code === 'COMPARE_INVALID') invalidMsg = COMPARE_INVALID_MSG[String(e.detail?.reason ?? '')] ?? e.message
    else invalidMsg = e instanceof Error ? e.message : '비교 자료를 불러오지 못했어요'
  }

  return (
    <div className="screen">
      <TopBar title={`${dog?.name ?? ''} 경과 비교`} onBack={() => nav(`/dogs/${dogId}`)} />
      <div className="scroll screen-body" style={{ gap: 12, paddingTop: 4 }}>
        <div className="seg" style={{ gridTemplateColumns: '1fr 1fr' }}>
          <button type="button" className={mode === 'BASELINE' ? 'on' : ''} onClick={() => setMode('BASELINE')}>
            기준 회차 대비
          </button>
          <button type="button" className={mode === 'PREVIOUS' ? 'on' : ''} onClick={() => setMode('PREVIOUS')}>
            직전 회차 대비
          </button>
        </div>

        {cmpQ.isPending && <div className="skeleton" style={{ height: 80 }} />}
        {invalidMsg && <Empty>{invalidMsg}</Empty>}

        {cmp && (
          <>
            <div className="cmp-head tabular">
              <div style={{ minWidth: 0 }}>
                <div className="k">{cmp.base.kind === 'PREVIOUS' ? '직전 회차' : cmp.base.kind === 'BASELINE' ? '기준 회차' : '비교 회차'}</div>
                <b>{fmtMonthDay(cmp.base.measured_on)}</b>
                <div className="small muted">모델 {cmp.base.model_version ?? '-'}</div>
              </div>
              <Icon name="arrow" size={20} style={{ color: 'var(--dim)' }} />
              <div style={{ minWidth: 0, textAlign: 'right' }}>
                <div className="k">{target ? '이 회차' : '최근 회차'}</div>
                <b>{fmtMonthDay(cmp.target.measured_on)}</b>
                <div className="small muted">모델 {cmp.target.model_version ?? '-'}</div>
              </div>
            </div>
            <span className="small muted" style={{ padding: '0 2px', fontSize: 13 }}>
              속보 · 같은 보행 유형, 같은 다리끼리만 비교해요
            </span>
            {cmp.model_changed && (
              <div className="note-warn">
                두 회차의 분석 방식이 달라요({cmp.base.model_version ?? '-'} → {cmp.target.model_version ?? '-'}). 수치는 보여 주지만 변화는 판단하지 않아요.
              </div>
            )}

            <Card style={{ padding: '0 16px' }}>
              {items.map((it) => (
                <CompareRow key={`${it.gait_type}:${it.metric_code}:${it.limb}`} it={it} focus={!!dog?.focus_limb && dog.focus_limb === it.limb} />
              ))}
            </Card>
            <span className="small" style={{ color: 'var(--dim2)', lineHeight: 1.5, padding: '0 2px' }}>
              증가·감소는 서버가 정한 오차 범위를 넘을 때만 표시해요. 기준이 정해지기 전에는 ‘판단 보류’로 와요. 변화의 의미는 수의사가 판단해요.
            </span>
          </>
        )}

        <Card style={{ padding: '16px 18px 14px', display: 'flex', flexDirection: 'column', gap: 12, marginTop: 4 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <b style={{ fontSize: 15 }}>회차별 추이</b>
            {trQ.data && trQ.data.series.length > 0 && (
              <div className="legend">
                {trQ.data.series.map((sr) => (
                  <span key={sr.limb}>
                    <i style={{ background: lineColor(sr.limb) }} />
                    {sr.limb === 'NONE' ? '전체' : LIMB_LABEL[sr.limb as keyof typeof LIMB_LABEL]}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="filters" style={{ padding: 0, margin: '0 -2px' }}>
            {TREND_CODES.map(([c, label]) => (
              <button key={c} type="button" className={`filter sm${code === c ? ' on' : ''}`} onClick={() => setCode(c)}>
                {label}
              </button>
            ))}
          </div>
          {trQ.isPending && <div className="skeleton" style={{ height: 120 }} />}
          {trQ.isError && <span className="small muted">{trQ.error instanceof ApiError ? trQ.error.message : '추이를 불러오지 못했어요'}</span>}
          {trQ.data && <TrendChart t={trQ.data} />}
          <span className="small muted">
            {dog?.focus_limb ? `관심 다리(${LIMB_LABEL[dog.focus_limb]})를 맨 앞에 보여 드려요.` : '관심 다리를 정하면 그 다리를 맨 앞에 보여 드려요.'} 측정 불가인 회차는 점을 비웠어요.
          </span>
        </Card>

        {limbs.length === 0 && !cmpQ.isPending && !invalidMsg && <Empty>비교할 수치가 없어요</Empty>}
      </div>
    </div>
  )
}

export function CompareRow({ it, focus }: { it: CompareItem; focus: boolean }) {
  const limbText = it.limb === 'NONE' ? '전체' : LIMB_LABEL[it.limb as keyof typeof LIMB_LABEL] + (focus ? ' · 관심 다리' : '')
  const moved = it.judgement === 'INCREASE' || it.judgement === 'DECREASE'
  const j =
    it.judgement === 'INCREASE'
      ? `▲ 증가 ${fmtMetric(it.diff == null ? null : Math.abs(it.diff), it.unit)}`
      : it.judgement === 'DECREASE'
        ? `▼ 감소 ${fmtMetric(it.diff == null ? null : Math.abs(it.diff), it.unit)}`
        : it.judgement === 'UNKNOWN' && it.diff != null
          ? `${it.diff > 0 ? '+' : ''}${fmtMetric(it.diff, it.unit)} · ${JUDGEMENT_LABEL.UNKNOWN}`
          : JUDGEMENT_LABEL[it.judgement]
  return (
    <div className="cmp-row">
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <span className="n">{metricLabel(it.metric_code)}</span>
          <span className={`limb${focus ? ' focus' : ''}`}>{limbText}</span>
        </div>
        <div className="vals tabular">
          {it.judgement === 'NOT_COMPARABLE' ? (it.note?.message ?? '한쪽 회차에서 측정 불가') : `${fmtMetric(it.base_value, it.unit)} → ${fmtMetric(it.target_value, it.unit)}`}
          {it.judgement !== 'NOT_COMPARABLE' && it.note && it.note.code !== 'RANGE_NOT_SET' && it.note.code !== 'MODEL_CHANGED' ? ` · ${it.note.message}` : ''}
        </div>
      </div>
      <span className={`judge${moved ? ' move' : ''}${it.judgement === 'NOT_COMPARABLE' ? ' na' : ''} tabular`} title={it.note?.message ?? ''}>
        {j}
      </span>
    </div>
  )
}

function lineColor(limb: MetricLimb): string {
  if (limb === 'LF' || limb === 'LH') return 'var(--left)'
  if (limb === 'RF' || limb === 'RH') return 'var(--right)'
  return 'var(--pri)'
}

/** 추이 선 그래프. 측정 불가(value null)에서 선을 끊고 점을 비운다. 모델이 바뀐 지점은 세로 점선. */
export function TrendChart({ t }: { t: TrendsOut }) {
  const dates = useMemo(() => {
    const set = new Map<string, string>()
    for (const sr of t.series) for (const p of sr.points) set.set(p.session_id, p.measured_on)
    return [...set.entries()].sort((a, b) => a[1].localeCompare(b[1]))
  }, [t])
  if (dates.length < 2) return <span className="small muted">완료 회차가 2개 이상이면 추이를 그려요.</span>
  const vals = t.series.flatMap((sr) => sr.points.map((p) => p.value)).filter((v): v is number => v != null)
  if (!vals.length) return <span className="small muted">이 수치는 아직 잰 회차가 없어요.</span>
  const mn = Math.floor(Math.min(...vals)) - 2
  const mx = Math.ceil(Math.max(...vals)) + 2
  const X = (i: number) => 20 + (i / (dates.length - 1)) * 280
  const Y = (v: number) => 130 - ((v - mn) / Math.max(1, mx - mn)) * 110
  const idx = (sid: string) => dates.findIndex((d) => d[0] === sid)
  // 모델이 바뀐 지점
  const modelBreaks: number[] = []
  const first = t.series[0]?.points ?? []
  for (let i = 1; i < first.length; i++) if (first[i].model_version !== first[i - 1].model_version) modelBreaks.push(idx(first[i].session_id))
  // 다리별로 앞다리·뒷다리 중 한 쌍만 그리면 복잡하지 않다: 앞 2개 series 만
  const shown = t.series.slice(0, 2)
  return (
    <>
      <svg viewBox="0 0 320 150" className="chart" aria-hidden="true" style={{ marginTop: 0 }}>
        <g stroke="#ECE8E2" strokeDasharray="3 4">
          <line x1="20" y1="20" x2="300" y2="20" />
          <line x1="20" y1="75" x2="300" y2="75" />
          <line x1="20" y1="130" x2="300" y2="130" />
        </g>
        <g fontSize="10" fill="#A0A7B2">
          <text x="304" y="24">{mx}</text>
          <text x="304" y="134">{mn}</text>
        </g>
        {modelBreaks.map((i) => (
          <line key={i} x1={X(i) - 0.5} y1="14" x2={X(i) - 0.5} y2="136" stroke="#C9C4BC" strokeDasharray="2 3" />
        ))}
        {shown.map((sr, si) => {
          let d = ''
          let pen = false
          for (const p of sr.points) {
            const i = idx(p.session_id)
            if (p.value == null || i < 0) {
              pen = false
              continue
            }
            d += `${pen ? 'L' : 'M'}${X(i).toFixed(1)},${Y(p.value).toFixed(1)} `
            pen = true
          }
          return (
            <g key={sr.limb}>
              <path d={d} fill="none" stroke={lineColor(sr.limb)} strokeWidth="2.4" strokeLinejoin="round" strokeDasharray={si === 1 ? '5 4' : undefined} />
              {sr.points.map((p) =>
                p.value == null ? null : <circle key={p.session_id} cx={X(idx(p.session_id))} cy={Y(p.value)} r="4" fill="#fff" stroke={lineColor(sr.limb)} strokeWidth="2" />,
              )}
            </g>
          )
        })}
      </svg>
      <div className="chart-x tabular" style={{ paddingLeft: 2, paddingRight: 2, fontSize: 11.5 }}>
        {dates.map(([sid, d]) => (
          <span key={sid}>{d.slice(5).replace('-', '.')}</span>
        ))}
      </div>
      {t.lr_diff.length > 0 && t.lr_diff[0].points.length > 0 && (
        <span className="small muted tabular">
          {PAIR_LABEL[t.lr_diff[0].pair]} 좌우 차이: {t.lr_diff[0].points.map((p) => `${fmtMonthDay(p.measured_on)} ${p.diff > 0 ? '+' : ''}${fmtMetric(p.diff, t.unit)}`).join(' · ')}
        </span>
      )}
      {modelBreaks.length > 0 && <span className="small muted">세로 점선 뒤부터는 분석 방식이 바뀌었어요.</span>}
    </>
  )
}
