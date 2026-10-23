import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useDogs } from '../../api/dogs'
import { SESSION_STATUS_LABEL, SESSION_STATUS_TONE, fmtMonthDay } from '../../api/labels'
import { useAllSessions } from '../../api/results'
import type { SessionStatus } from '../../api/types'
import { DogSkeleton } from '../../components/DogSkeleton'
import { Badge, Button, Card } from '../../components/ui'
import './results.css'

type Filter = 'ALL' | SessionStatus
const FILTERS: [Filter, string][] = [
  ['ALL', '전체'],
  ['DONE', '완료'],
  ['MEASURING', '측정 중'],
  ['FAILED', '실패'],
]

/**
 * 분석 결과 탭. 디자인 v5 `results`. 기관 전체 회차 API 가 없어 반려견별 이력을 모아 보여 준다(screenPlan 6절 #5).
 * 반려견이 많아지면 백엔드에 목록 API 를 요청한다.
 */
export function ResultsPage() {
  const nav = useNavigate()
  const dogsQ = useDogs({ size: 100 })
  const all = useAllSessions(dogsQ.data?.items)
  const [filter, setFilter] = useState<Filter>('ALL')

  const list = useMemo(() => {
    const items = all.items.filter((s) => filter === 'ALL' || (filter === 'MEASURING' ? s.status === 'MEASURING' || s.status === 'AGGREGATING' : s.status === filter))
    return items.sort((a, b) => b.measured_on.localeCompare(a.measured_on))
  }, [all.items, filter])

  const pending = dogsQ.isPending || all.isPending

  return (
    <div className="screen">
      <div className="topbar" style={{ padding: '0 20px' }}>
        <b style={{ fontSize: 20, letterSpacing: -0.4 }}>분석 결과</b>
      </div>
      <div className="filters">
        {FILTERS.map(([k, label]) => (
          <button key={k} type="button" className={`filter${filter === k ? ' on' : ''}`} onClick={() => setFilter(k)}>
            {label}
          </button>
        ))}
      </div>
      <div className="scroll with-tabs" style={{ padding: '0 20px 12px' }}>
        {pending && <div className="skeleton" />}
        {!pending && list.length === 0 && (
          <div style={{ padding: '48px 12px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, textAlign: 'center' }}>
            <b style={{ fontSize: 17 }}>{filter === 'ALL' ? '아직 분석 결과가 없어요' : '해당하는 회차가 없어요'}</b>
            <span style={{ fontSize: 14, color: 'var(--sub)', lineHeight: 1.6 }}>보행 영상을 찍으면 여기에 결과가 쌓여요.</span>
            <Button size="md" style={{ width: 'auto', padding: '0 18px', marginTop: 6 }} onClick={() => nav('/capture')}>
              보행 촬영하기
            </Button>
          </div>
        )}
        {list.length > 0 && (
          <Card style={{ padding: '0 16px' }}>
            {list.map((s) => {
              const valid = s.valid_passes.LEFT + s.valid_passes.RIGHT
              const sub = s.status === 'DONE' ? `유효 통과 ${valid} · 모델 ${s.model_version ?? '-'}` : s.status === 'FAILED' ? '쓸 수 있는 통과 없음' : `유효 통과 왼 ${s.valid_passes.LEFT} · 오 ${s.valid_passes.RIGHT}`
              const to = s.status === 'DONE' ? `/sessions/${s.id}/result` : `/sessions/${s.id}`
              return (
                <button type="button" key={s.id} className="res-item" onClick={() => nav(to)}>
                  <div className="res-thumb">
                    <DogSkeleton />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 15, fontWeight: 700 }}>{s.dog.name}</div>
                    <div className="small muted tabular" style={{ marginTop: 2 }}>
                      {fmtMonthDay(s.measured_on)} · 체중 {s.weight_kg ?? s.dog.weight_kg}kg
                    </div>
                  </div>
                  <div className="res-right">
                    <Badge tone={SESSION_STATUS_TONE[s.status]}>{SESSION_STATUS_LABEL[s.status]}</Badge>
                    <span className="small muted tabular">{sub}</span>
                  </div>
                </button>
              )
            })}
          </Card>
        )}
      </div>
    </div>
  )
}
