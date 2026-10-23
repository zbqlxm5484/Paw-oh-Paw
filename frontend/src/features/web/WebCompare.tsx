import { useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { useDog } from '../../api/dogs'
import { LIMB_LABEL, fmtMonthDay } from '../../api/labels'
import { useCompare, useTrends } from '../../api/results'
import { Icon } from '../../components/Icon'
import { COMPARE_INVALID_MSG, CompareRow, TREND_CODES, TrendChart } from '../results/ComparePage'
import '../results/results.css'

/** 웹 v2 경과 비교: 왼쪽 수치별 변화 목록, 오른쪽 추이 그래프. */
export function WebCompare() {
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

  let invalidMsg: string | null = null
  if (cmpQ.isError) {
    const e = cmpQ.error
    invalidMsg = e instanceof ApiError && e.code === 'COMPARE_INVALID' ? (COMPARE_INVALID_MSG[String(e.detail?.reason ?? '')] ?? e.message) : e instanceof Error ? e.message : '비교 자료를 불러오지 못했어요'
  }

  return (
    <main className="web-main" style={{ gap: 20, paddingTop: 24 }}>
      <button type="button" className="web-back" onClick={() => nav(`/?dog=${dogId}`)}>
        <Icon name="back" size={16} />홈
      </button>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <h1 className="web-h1">{dog?.name ?? ''} 경과 비교</h1>
        <span style={{ fontSize: 15, color: 'var(--sub)' }}>속보 · 같은 보행 유형, 같은 다리끼리만 비교해요</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <div className="seg" style={{ gridTemplateColumns: '1fr 1fr', width: 380, maxWidth: '100%' }}>
          <button type="button" className={mode === 'BASELINE' ? 'on' : ''} onClick={() => setMode('BASELINE')}>
            기준 회차 대비
          </button>
          <button type="button" className={mode === 'PREVIOUS' ? 'on' : ''} onClick={() => setMode('PREVIOUS')}>
            직전 회차 대비
          </button>
        </div>
        {cmp && (
          <div className="web-card tabular" style={{ flex: '1 1 360px', minWidth: 0, borderRadius: 14, padding: '12px 20px', display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <div>
              <span style={{ fontSize: 12.5, color: 'var(--sub)', fontWeight: 600 }}>{cmp.base.kind === 'PREVIOUS' ? '직전 회차' : '기준 회차'}</span>
              <b style={{ display: 'block', fontSize: 16 }}>
                {fmtMonthDay(cmp.base.measured_on)} · 모델 {cmp.base.model_version ?? '-'}
              </b>
            </div>
            <Icon name="arrow" size={22} style={{ color: 'var(--dim)' }} />
            <div>
              <span style={{ fontSize: 12.5, color: 'var(--sub)', fontWeight: 600 }}>{target ? '이 회차' : '최근 회차'}</span>
              <b style={{ display: 'block', fontSize: 16 }}>
                {fmtMonthDay(cmp.target.measured_on)} · 모델 {cmp.target.model_version ?? '-'}
              </b>
            </div>
          </div>
        )}
      </div>
      {invalidMsg && <div className="web-card" style={{ padding: '40px 32px', fontSize: 15, color: 'var(--sub)' }}>{invalidMsg}</div>}
      {cmp?.model_changed && (
        <div className="note-warn" style={{ fontSize: 14.5, padding: '14px 18px' }}>
          두 회차의 분석 방식이 달라요({cmp.base.model_version ?? '-'} → {cmp.target.model_version ?? '-'}). 수치는 보여 주지만 변화는 판단하지 않아요.
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 16, alignItems: 'start' }}>
        <div className="web-card" style={{ padding: '4px 22px' }}>
          {cmpQ.isPending && <div className="skeleton" style={{ margin: '12px 0' }} />}
          {items.map((it) => (
            <CompareRow key={`${it.gait_type}:${it.metric_code}:${it.limb}`} it={it} focus={!!dog?.focus_limb && dog.focus_limb === it.limb} />
          ))}
        </div>
        <div className="web-card" style={{ padding: '22px 24px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <b style={{ fontSize: 16 }}>회차별 추이</b>
            {trQ.data && (
              <div className="legend">
                {trQ.data.series.slice(0, 2).map((sr) => (
                  <span key={sr.limb}>
                    <i style={{ background: sr.limb === 'LF' || sr.limb === 'LH' ? 'var(--left)' : sr.limb === 'RF' || sr.limb === 'RH' ? 'var(--right)' : 'var(--pri)' }} />
                    {sr.limb === 'NONE' ? '전체' : LIMB_LABEL[sr.limb as keyof typeof LIMB_LABEL]}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {TREND_CODES.map(([c, label]) => (
              <button key={c} type="button" className={`filter sm${code === c ? ' on' : ''}`} onClick={() => setCode(c)}>
                {label}
              </button>
            ))}
          </div>
          {trQ.isPending && <div className="skeleton" style={{ height: 160 }} />}
          {trQ.data && <TrendChart t={trQ.data} />}
          <span style={{ fontSize: 13, color: 'var(--sub)' }}>{dog?.focus_limb ? `관심 다리(${LIMB_LABEL[dog.focus_limb]})를 맨 앞에 보여 드려요.` : '관심 다리를 정하면 그 다리를 맨 앞에 보여 드려요.'}</span>
        </div>
      </div>
      <span style={{ fontSize: 13, color: 'var(--dim2)' }}>증가·감소는 서버가 정한 오차 범위를 넘을 때만 표시해요. 변화의 의미는 수의사가 판단해요.</span>
    </main>
  )
}
