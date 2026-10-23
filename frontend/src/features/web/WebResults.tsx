import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useDogs } from '../../api/dogs'
import { SESSION_STATUS_LABEL, SESSION_STATUS_TONE, fmtMonthDay } from '../../api/labels'
import { useAllSessions } from '../../api/results'
import { Badge } from '../../components/ui'
import { DogStrip } from './DogStrip'

/** 웹 v2 분석 결과: 반려견 띠로 거르고 표로 본다. 기관 전체 목록 API 가 없어 반려견별 이력을 모은다. */
export function WebResults() {
  const nav = useNavigate()
  const dogsQ = useDogs({ size: 100 })
  const all = useAllSessions(dogsQ.data?.items)
  const [dogId, setDogId] = useState<string | null>(null)
  const dogs = dogsQ.data?.items ?? []

  const rows = useMemo(() => {
    const items = all.items.filter((s) => !dogId || s.dog.id === dogId)
    const byDog = new Map<string, typeof items>()
    for (const s of items) byDog.set(s.dog.id, [...(byDog.get(s.dog.id) ?? []), s])
    // 회차 번호: 반려견별로 오래된 것부터 1
    const no = new Map<string, number>()
    for (const [, list] of byDog) {
      const asc = [...list].sort((a, b) => a.measured_on.localeCompare(b.measured_on))
      asc.forEach((s, i) => no.set(s.id, i + 1))
    }
    return items.sort((a, b) => b.measured_on.localeCompare(a.measured_on)).map((s) => ({ ...s, no: no.get(s.id) ?? 0 }))
  }, [all.items, dogId])

  const cols = '1.1fr 1.4fr 1fr 1fr 1fr 1fr 40px'
  return (
    <main className="web-main" style={{ gap: 20 }}>
      <h1 className="web-h1" style={{ fontSize: 34 }}>
        분석 결과
      </h1>
      <DogStrip dogs={dogs} selectedId={dogId} onPick={setDogId} allOption />
      <div className="web-card web-table">
        <div className="tbl">
          <div className="thead" style={{ gridTemplateColumns: cols, borderTop: 0 }}>
            <span>반려견</span>
            <span>측정일 · 회차</span>
            <span>상태</span>
            <span>유효 통과</span>
            <span>모델</span>
            <span>체중</span>
            <span />
          </div>
          {(dogsQ.isPending || all.isPending) && <div className="skeleton" style={{ margin: 16 }} />}
          {rows.map((r) => (
            <button type="button" key={r.id} className="trow tabular" style={{ gridTemplateColumns: cols }} onClick={() => nav(r.status === 'DONE' ? `/sessions/${r.id}/result` : `/sessions/${r.id}`)}>
              <b>{r.dog.name}</b>
              <span style={{ color: 'var(--sub)' }}>
                {fmtMonthDay(r.measured_on)} · {r.no}회차
              </span>
              <span>
                <Badge tone={SESSION_STATUS_TONE[r.status]}>{SESSION_STATUS_LABEL[r.status]}</Badge>
              </span>
              <span>
                왼 {r.valid_passes.LEFT} · 오 {r.valid_passes.RIGHT}
              </span>
              <span>{r.model_version ?? '-'}</span>
              <span>{r.weight_kg ?? r.dog.weight_kg}kg</span>
              <span style={{ color: 'var(--dim)' }}>›</span>
            </button>
          ))}
          {!all.isPending && rows.length === 0 && (
            <div style={{ padding: '48px 24px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
              <b style={{ fontSize: 17 }}>아직 분석 결과가 없어요</b>
              <button type="button" className="web-btn pri" onClick={() => nav('/capture')}>
                영상 올리기
              </button>
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
