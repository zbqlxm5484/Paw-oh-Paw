// 앱 보고서·회차 결과의 '측정 품질' 칸에 붙는 측정 신뢰도와 남은 촬영 수(QA 11-11, 285). 로직은 ./quality.ts(웹과 같은 코드)
import type { SessionResultOut } from '../../api/types'
import { measureQuality, sidesText } from './quality'

/** 보고서 수치와 같은 보행 묶음(속보 우선, 없으면 수치가 있는 첫 묶음)의 다리별 쓴 걸음 수(n_passes 최댓값) */
export function passesByLimb(result: SessionResultOut | null | undefined): Record<string, number> | null {
  const g = result?.gaits.find((x) => x.gait_type === 'TROT' && x.metrics.length) ?? result?.gaits.find((x) => x.metrics.length)
  if (!g) return null
  const np: Record<string, number> = {}
  for (const m of g.metrics) if (m.limb !== 'NONE' && typeof m.n_passes === 'number') np[m.limb] = Math.max(np[m.limb] ?? 0, m.n_passes)
  return Object.keys(np).length ? np : null
}

export function AppQualityLine({ result, kind }: { result: SessionResultOut | null | undefined; kind: 'g' | 'v' }) {
  const q = measureQuality(passesByLimb(result))
  if (!q) return null
  return (
    <span style={{ flexBasis: '100%', display: 'flex', flexDirection: 'column', gap: '3px', color: '#3A4250' }}>
      <span>다리 쪽별 쓴 걸음 <b style={{ fontVariantNumeric: 'tabular-nums' }}>{sidesText(q)}</b></span>
      {q.hint ? <span style={{ color: '#A8481A' }}>{q.hint}</span> : null}
      {kind === 'v' && q.judgeNote ? <span style={{ color: '#5B6472' }}>{q.judgeNote}</span> : null}
    </span>
  )
}
