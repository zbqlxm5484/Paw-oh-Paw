// 측정 신뢰도와 남은 촬영 수(QA 11-11, 285). 로직은 views/quality.ts
import { css } from '../../app/css'
import type { Result } from '../../store/types'
import { MIN_PASSES, measureQuality, sidesText } from '../../views/quality'

/** 보고서 종이의 '측정 품질' 칸에 붙는 줄: 다리 쪽별 쓴 걸음과 다음 측정 안내. 수의사용은 판단하지 않은 이유까지 */
export function QualityLine({ r, kind }: { r: Result; kind: string }) {
  const q = measureQuality(r.np)
  if (!q) return null
  return (
    <span style={css('flex-basis:100%;display:flex;flex-direction:column;gap:3px;font-size:13px;color:#3A4250')}>
      <span>다리 쪽별 쓴 걸음 <b style={css('font-variant-numeric:tabular-nums')}>{sidesText(q)}</b></span>
      {q.hint ? <span style={css('color:#A8481A')}>{q.hint}</span> : null}
      {kind === 'v' && q.judgeNote ? <span style={css('color:#5B6472')}>{q.judgeNote}</span> : null}
    </span>
  )
}

/** 회차 결과 화면 위(보고서 종이 밖, 인쇄 안 함): 측정을 얼마나 믿을 수 있는지와 남은 촬영 수 */
export function QualityCard({ r }: { r: Result }) {
  const q = measureQuality(r.np)
  if (!q) return null
  const ok = !q.hint
  return (
    <div className="no-print" style={css(`display:flex;flex-direction:column;gap:10px;padding:16px 20px;border-radius:14px;background:#fff;border:1px solid ${ok ? '#ECE8E2' : '#F0D2BC'}`)}>
      <div style={css('display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap')}>
        <b style={css('font-size:15px')}>측정 신뢰도</b>
        <span style={css('font-size:12.5px;color:#8E949C')}>쪽마다 {MIN_PASSES}번 이상 쓴 걸음이 있어야 지난 측정과 변화를 판단해요 · 권장 촬영은 회차마다 약 20번(좌우 반반)</span>
      </div>
      <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:12px')}>
        {q.sides.map((s) => {
          const n = s.n ?? 0
          const pct = Math.min(100, (n / MIN_PASSES) * 100)
          return (
            <div key={s.side} style={css('display:flex;flex-direction:column;gap:6px')}>
              <span style={css('display:flex;justify-content:space-between;font-size:13.5px')}>
                <span>{s.side} 다리 쪽</span>
                <b style={css(`font-variant-numeric:tabular-nums;color:${s.need ? '#B4501A' : '#1B2433'}`)}>{n} / {MIN_PASSES}</b>
              </span>
              <span style={css('height:8px;border-radius:4px;background:#F2EEE8;overflow:hidden')}>
                <span style={css(`display:block;height:100%;width:${pct}%;background:${s.need ? '#E9A26B' : '#D2601A'}`)}></span>
              </span>
            </div>
          )
        })}
      </div>
      {q.hint ? <span style={css('font-size:14px;font-weight:600;color:#A8481A')}>{q.hint}</span> : <span style={css('font-size:13.5px;color:#5B6472')}>양쪽 모두 충분히 걸어서 지난 측정과 변화를 판단할 수 있어요</span>}
      {q.judgeNote ? <span style={css('font-size:13px;color:#5B6472')}>{q.judgeNote}</span> : null}
      {r.ex.length ? <span style={css('font-size:13px;color:#5B6472')}>뺀 걸음: {r.ex.map(([n, c]) => `${n} ${c}번`).join(', ')}</span> : null}
    </div>
  )
}
