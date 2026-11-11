// 기준 회차 대비 변화 프로필(앱 수의사용 보고서, QA 2절, S15P31A404-285). 웹 web/src/views/changeProfile.ts·parts/ChangeProfile.tsx 와 같은 규칙.
// 관절·다리마다 '이번 − 기준' 가로 막대 + 오차 범위 회색 띠. 띠를 벗어난 관절만 색(증가 주황, 감소 남색), 범위 안 회색, 판정 불가는 흐린 막대 + '값만'.
import type { CompareItem, CompareOut } from '../../api/types'

/** 회차 비교 오차 범위(백엔드 config/tolerance.yaml, 웹 views/vet.ts TOLERANCE 와 같은 값). 서버 판정이 이 범위로 난다 */
const TOLERANCE: Record<string, number> = { rom_shoulder: 5.0, rom_carpus: 11.8, rom_hip: 5.0, rom_stifle: 8.0, rom_tarsus: 5.9 }
const ROM: [string, string, 'F' | 'H'][] = [
  ['rom_shoulder', '어깨', 'F'], ['rom_elbow', '팔꿈치', 'F'], ['rom_carpus', '앞발목', 'F'],
  ['rom_hip', '고관절', 'H'], ['rom_stifle', '무릎', 'H'], ['rom_tarsus', '뒷발목', 'H'],
]
const LIMBS_OF = { F: ['LF', 'RF'], H: ['LH', 'RH'] } as const
const SIDE: Record<string, string> = { LF: '왼앞', RF: '오른앞', LH: '왼뒤', RH: '오른뒤' }
type J = 'INCREASE' | 'DECREASE' | 'WITHIN_RANGE' | 'VALUE_ONLY'
const LABEL: Record<J, string> = { INCREASE: '증가', DECREASE: '감소', WITHIN_RANGE: '범위 안', VALUE_ONLY: '값만' }
const COLOR: Record<J, string> = { INCREASE: '#D2601A', DECREASE: '#3A4250', WITHIN_RANGE: '#C9C3BA', VALUE_ONLY: '#C9C3BA' }
const CHIP: Record<J, [string, string]> = { INCREASE: ['#FCEEE3', '#A8481A'], DECREASE: ['#E9EBEE', '#3A4250'], WITHIN_RANGE: ['#F2EFEA', '#5B6472'], VALUE_ONLY: ['#fff', '#5B6472'] }
const r1 = (v: number) => Math.round(v * 10) / 10
const korDate = (iso: string) => {
  const [, m, d] = iso.split('-')
  return m && d ? `${Number(m)}월 ${Number(d)}일` : iso
}

interface Row { joint: string; side: string; diff: number; tol: number | null; j: J }

function rowsOf(o: CompareOut, gait: string | undefined): Row[] {
  const rows: Row[] = []
  for (const [code, joint, fh] of ROM) {
    for (const limb of LIMBS_OF[fh]) {
      const it = o.items.find((x: CompareItem) => x.metric_code === code && x.limb === limb && (!gait || x.gait_type === gait))
      if (!it || it.base_value == null || it.target_value == null) continue
      const j: J = it.judgement === 'INCREASE' || it.judgement === 'DECREASE' || it.judgement === 'WITHIN_RANGE' ? it.judgement : 'VALUE_ONLY'
      rows.push({ joint, side: SIDE[limb], diff: r1(it.target_value - it.base_value), tol: j === 'VALUE_ONLY' ? null : TOLERANCE[code] ?? null, j })
    }
  }
  return rows
}

const geom = (v: number, scale: number) => {
  const w = Math.min(50, (Math.abs(v) / scale) * 50)
  return v >= 0 ? { left: 50, width: w } : { left: 50 - w, width: w }
}

/** base: GET /dogs/{id}/compare?base=BASELINE&target=이 회차 응답. 없거나 이번이 기준이면 칸을 뺀다 */
export function AppChangeProfile({ base, gait }: { base: CompareOut | undefined; gait?: string }) {
  if (!base || base.base.session_id === base.target.session_id) return null
  const rows = rowsOf(base, gait)
  if (!rows.length) return null
  const scale = Math.ceil(Math.max(5, ...rows.map((x) => Math.abs(x.diff)), ...rows.map((x) => x.tol ?? 0)) * 1.15)
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 800 }}>기준 회차 대비 변화</h3>
      <span style={{ fontSize: '12px', color: '#5B6472', lineHeight: 1.5 }}>기준 {korDate(base.base.measured_on)} → 이번 {korDate(base.target.measured_on)} · 관절 가동 범위. 회색 띠는 오차 범위예요</span>
      {rows.map((x, i) => {
        const bar = geom(x.diff, scale)
        const band = x.tol != null ? geom(x.tol, scale) : null
        return (
          <div key={i} style={{ display: 'grid', gridTemplateColumns: '78px 1fr 48px 46px', gap: '6px', alignItems: 'center', padding: '4px 0', borderTop: i ? '1px solid #F2EFEA' : 'none' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, whiteSpace: 'nowrap' }}>{x.joint} <span style={{ fontWeight: 500, color: '#5B6472' }}>{x.side}</span></span>
            <div style={{ position: 'relative', height: 12 }}>
              {band ? <span style={{ position: 'absolute', top: 0, bottom: 0, left: `${50 - band.width}%`, width: `${band.width * 2}%`, background: '#ECE8E2', borderRadius: 3 }} /> : null}
              <span style={{ position: 'absolute', top: -2, bottom: -2, left: '50%', width: 1, background: '#A0A7B2' }} />
              <span style={{ position: 'absolute', top: 3, height: 6, left: `${bar.left}%`, width: `${Math.max(bar.width, 0.6)}%`, background: COLOR[x.j], opacity: x.j === 'VALUE_ONLY' ? 0.45 : 1, borderRadius: 2 }} />
            </div>
            <span style={{ fontSize: '12px', fontWeight: 700, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{x.diff > 0 ? '+' : x.diff < 0 ? '−' : ''}{Math.abs(x.diff).toFixed(1)}°</span>
            <span style={{ justifySelf: 'start', padding: '1px 6px', borderRadius: 5, fontSize: '12px', fontWeight: 700, background: CHIP[x.j][0], color: CHIP[x.j][1], border: x.j === 'VALUE_ONLY' ? '1px solid #E2DCD3' : 'none' }}>{LABEL[x.j]}</span>
          </div>
        )
      })}
      {rows.some((x) => x.j === 'VALUE_ONLY') ? <span style={{ fontSize: '12px', color: '#5B6472', lineHeight: 1.5 }}>'값만'은 걸은 횟수가 모자라거나 오차 범위가 정해지지 않아 증가·감소를 가르지 않은 관절이에요.</span> : null}
    </section>
  )
}
