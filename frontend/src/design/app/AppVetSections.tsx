// 앱 보고서 · 수의사용 탭(웹 수의사용 보고서와 같은 구성, S15P31A404-210·103):
// 왼쪽과 오른쪽 비교(관절별 위아래 막대), 뒷무릎 각도·보행 주기, 지난 측정과 비교(서버 비교 API), 무릎 가동 범위 변화(서버 추이 API).
import type { CompareItem, CompareOut, SessionResultOut, TrendsOut } from '../../api/types'
import kneeCycle from './knee_cycle.json'

const BLUE = '#3B6FE0'
const ORANGE = '#D2601A'
const GAIT_NAME: Record<string, string> = { WALK: '평보', TROT: '속보', OTHER: '보행 유형 미판별' }
const JOINTS: [string, string, 'F' | 'H'][] = [
  ['rom_shoulder', '어깨', 'F'], ['rom_elbow', '팔꿈치', 'F'], ['rom_carpus', '앞발목', 'F'],
  ['rom_hip', '고관절', 'H'], ['rom_stifle', '무릎', 'H'], ['rom_tarsus', '뒷발목', 'H'],
]
const NAME: Record<string, string> = Object.fromEntries(JOINTS.map(([c, n]) => [c, n]))
const H2: React.CSSProperties = { margin: 0, fontSize: '15px', fontWeight: 800, letterSpacing: '-0.3px' }
const f1 = (v: number) => (Math.round(v * 10) / 10).toFixed(1)

/** 대표 보행: 속보가 있으면 속보, 없으면 평보 */
export function mainGaitOf(r: SessionResultOut | null | undefined): 'TROT' | 'WALK' | 'OTHER' {
  const g = (r?.gaits ?? []).filter((x) => x.metrics.length).map((x) => x.gait_type)
  return (['TROT', 'WALK', 'OTHER'] as const).find((x) => g.includes(x)) ?? 'TROT'
}

function Legend() {
  return (
    <div style={{ display: 'flex', gap: '12px', fontSize: '11.5px', color: '#5B6472' }}>
      <span><span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 3, background: BLUE, marginRight: 4 }} />왼쪽</span>
      <span><span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 3, background: ORANGE, marginRight: 4 }} />오른쪽</span>
    </div>
  )
}

function LrBars({ result }: { result: SessionResultOut }) {
  const gaits = (['WALK', 'TROT', 'OTHER'] as const).map((t) => result.gaits.find((g) => g.gait_type === t)).filter((g) => g && g.metrics.length)
  const blocks = gaits.map((g) => {
    const val = (code: string, limb: string) => g!.metrics.find((m) => m.metric_code === code && m.limb === limb && m.measurable)?.value ?? null
    const rows = JOINTS.map(([code, n, fh]) => ({ code, n, l: val(code, 'L' + fh), r: val(code, 'R' + fh) }))
      .filter((x): x is { code: string; n: string; l: number; r: number } => x.l != null && x.r != null)
    const ratio = (x: { l: number; r: number }) => (x.l + x.r ? Math.abs(x.l - x.r) / ((x.l + x.r) / 2) : 0)
    const top = rows.length ? rows.reduce((a, b) => (ratio(b) > ratio(a) ? b : a)) : null
    return { gait: GAIT_NAME[g!.gait_type] ?? g!.gait_type, rows, top: top && ratio(top) > 0 ? top.code : '' }
  }).filter((b) => b.rows.length)
  if (!blocks.length) return null
  const mx = Math.max(1, ...blocks.flatMap((b) => b.rows.flatMap((x) => [x.l, x.r])))
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <h3 style={H2}>왼쪽과 오른쪽 비교</h3>
      <Legend />
      {blocks.map((b) => (
        <div key={b.gait} style={{ display: 'flex', flexDirection: 'column' }}>
          <b style={{ fontSize: '12px', color: '#5B6472', padding: '6px 2px', borderBottom: '1px solid #ECE8E2', display: 'flex', justifyContent: 'space-between' }}><span>{b.gait}</span><span>좌우 차이</span></b>
          {b.rows.map((x) => (
            <div key={x.code} style={{ display: 'grid', gridTemplateColumns: '58px 1fr 46px', gap: '8px', alignItems: 'center', padding: '7px 2px', borderBottom: '1px solid #F2EFEA', background: x.code === b.top ? '#FAF8F5' : 'transparent' }}>
              <b style={{ fontSize: '13px' }}>{x.n}</b>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {([[x.l, BLUE], [x.r, ORANGE]] as const).map(([v, c], i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <span style={{ height: 7, borderRadius: 4, background: c, width: `calc(${(v / mx) * 100}% - 38px)`, minWidth: 3 }} />
                    <span style={{ fontSize: '11px', color: '#3A4250', fontVariantNumeric: 'tabular-nums' }}>{f1(v)}°</span>
                  </div>
                ))}
              </div>
              <b style={{ textAlign: 'right', fontSize: '13.5px', fontVariantNumeric: 'tabular-nums' }}>{f1(Math.abs(x.l - x.r))}°</b>
            </div>
          ))}
        </div>
      ))}
    </section>
  )
}

const SIDE: Record<string, string> = { LF: '왼쪽', RF: '오른쪽', LH: '왼쪽', RH: '오른쪽' }
function badge(it: CompareItem): [string, string, string] {
  const d = it.diff ?? 0
  if (it.judgement === 'INCREASE') return [`▲ ${f1(Math.abs(d))}° 증가`, '#1B2433', '#fff']
  if (it.judgement === 'DECREASE') return [`▼ ${f1(Math.abs(d))}° 감소`, '#1B2433', '#fff']
  if (it.judgement === 'WITHIN_RANGE') return ['범위 안', '#EEE8DF', '#3A4250']
  return ['값만', '#fff', '#5B6472']
}

function CmpList({ cmp }: { cmp: CompareOut | undefined }) {
  const items = (cmp?.items ?? []).filter((x) => NAME[x.metric_code] && x.base_value != null && x.target_value != null)
  const order = (it: CompareItem) => (it.judgement === 'INCREASE' || it.judgement === 'DECREASE' ? 0 : it.judgement === 'WITHIN_RANGE' ? 1 : 2)
  const sorted = [...items].sort((a, b) => order(a) - order(b) || Math.abs(b.diff ?? 0) - Math.abs(a.diff ?? 0))
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <h3 style={H2}>지난 측정과 비교{cmp ? <span style={{ fontSize: '12px', fontWeight: 600, color: '#5B6472', marginLeft: 6 }}>{cmp.base.measured_on} 대비</span> : null}</h3>
      {!cmp ? <span style={{ fontSize: '12.5px', color: '#5B6472' }}>비교할 직전 회차가 없어요.</span> : (
        <>
          {cmp.model_changed ? <span style={{ fontSize: '12px', color: '#5B6472' }}>분석 모델이 달라 변화는 판단하지 않고 값만 적었어요.</span> : null}
          {sorted.map((it, i) => {
            const [t, bg, fg] = badge(it)
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '7px 2px', borderBottom: '1px solid #F2EFEA', fontSize: '13px' }}>
                <span style={{ flex: 1, minWidth: 0 }}><b>{NAME[it.metric_code]}</b> <span style={{ color: it.limb.startsWith('L') ? BLUE : ORANGE, fontSize: '12px', fontWeight: 600 }}>{SIDE[it.limb]}</span></span>
                <span style={{ color: '#5B6472', fontSize: '12px', fontVariantNumeric: 'tabular-nums' }}>{f1(it.base_value!)} → <b style={{ color: '#1B2433' }}>{f1(it.target_value!)}°</b></span>
                <span style={{ height: 22, padding: '0 8px', borderRadius: 11, background: bg, color: fg, border: `1px solid ${bg === '#fff' ? '#D8D2C8' : bg}`, fontSize: '11px', fontWeight: 700, display: 'flex', alignItems: 'center', whiteSpace: 'nowrap' }}>{t}</span>
              </div>
            )
          })}
        </>
      )}
    </section>
  )
}

/** 이 회차 무릎 가동 범위·입각기 비율에 맞춰 늘이고 줄인 한 걸음 곡선(웹 knee_chart·fit_curve 와 같은 계산) */
const TEMPLATE_STANCE = 60.0
function fitCurve(base: number[], rom: number | null, stance: number | null): number[] {
  const n = base.length
  const mean = base.reduce((a, b) => a + b, 0) / n
  const amp = Math.max(...base) - Math.min(...base) || 1
  const k = rom ? rom / amp : 1
  const c = base.map((v) => mean + (v - mean) * k)
  if (!stance) return c
  const a = TEMPLATE_STANCE / 100
  const b = Math.min(0.8, Math.max(0.35, stance / 100))
  return c.map((_, i) => {
    const p = i / n
    const x = (p < b ? (p / b) * a : a + ((p - b) / (1 - b)) * (1 - a)) * n
    const j = Math.trunc(x) % n
    const f = x - Math.trunc(x)
    return c[j] * (1 - f) + c[(j + 1) % n] * f
  })
}

function KneeCycle({ result }: { result: SessionResultOut }) {
  const g = result.gaits.find((x) => x.gait_type === mainGaitOf(result))
  const val = (code: string, limb: string) => g?.metrics.find((m) => m.metric_code === code && m.limb === limb && m.measurable)?.value ?? null
  if (!g || val('rom_stifle', 'LH') == null || val('rom_stifle', 'RH') == null) return null
  const [L, R] = (['LH', 'RH'] as const).map((leg) => fitCurve(kneeCycle.base, val('rom_stifle', leg), val('stance_ratio', leg)))
  const ref = kneeCycle.ref
  const all = [...L, ...R, ...ref.min, ...ref.max]
  const lo = Math.floor(Math.min(...all) / 10) * 10, hi = Math.ceil(Math.max(...all) / 10) * 10
  const x0 = 44, x1 = 300, y0 = 12, y1 = 120
  const Y = (v: number) => y1 - ((v - lo) / (hi - lo)) * (y1 - y0)
  const pt = (c: number[]) => c.map((v, i) => `${(x0 + ((x1 - x0) * i) / c.length).toFixed(1)},${Y(v).toFixed(1)}`)
  const line = (c: number[]) => pt(c).join(' ')
  const mid = Math.floor((lo + hi) / 2)
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <h3 style={H2}>뒷무릎 각도 · 보행 주기</h3>
      <svg viewBox="0 0 320 150" style={{ width: '100%', display: 'block', fontFamily: 'inherit' }}>
        <g stroke="#ECE8E2" strokeDasharray="3 4">{[hi, mid, lo].map((v) => <line key={v} x1={x0} y1={Y(v)} x2={x1} y2={Y(v)} />)}</g>
        <g fontSize="9.5" fill="#8E949C">
          {[hi, mid, lo].map((v) => <text key={v} x={x0 - 5} y={Y(v) + 3} textAnchor="end">{v}°</text>)}
          {[0, 50, 100].map((p) => <text key={'x' + p} x={x0 + ((x1 - x0) * p) / 100} y="133" textAnchor="middle">{p}</text>)}
          <text x={(x0 + x1) / 2} y="146" textAnchor="middle">한 걸음 (뒷발 착지 → 다음 착지, %)</text>
          <text x="10" y="66" textAnchor="middle" transform="rotate(-90 10 66)">무릎 각도</text>
        </g>
        <polygon points={[...pt(ref.max), ...pt(ref.min).reverse()].join(' ')} fill="#E9E6E1" opacity=".75" />
        <polyline points={line(ref.mean)} fill="none" stroke="#A0A7B2" strokeWidth="1.3" strokeDasharray="2 3" />
        <polyline points={line(L)} fill="none" stroke={BLUE} strokeWidth="2" />
        <polyline points={line(R)} fill="none" stroke="#E5604D" strokeWidth="2" strokeDasharray="5 4" />
      </svg>
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', fontSize: '11.5px', color: '#5B6472' }}>
        <span><span style={{ display: 'inline-block', width: 16, borderTop: `2px solid ${BLUE}`, verticalAlign: 'middle', marginRight: 5 }} />왼쪽</span>
        <span><span style={{ display: 'inline-block', width: 16, borderTop: '2px dashed #E5604D', verticalAlign: 'middle', marginRight: 5 }} />오른쪽</span>
        <span><span style={{ display: 'inline-block', width: 16, height: 9, background: '#E9E6E1', verticalAlign: 'middle', marginRight: 5 }} />정상 참고 범위</span>
      </div>
    </section>
  )
}

function KneeTrend({ trend }: { trend: TrendsOut | undefined }) {
  const pick = (limb: string) => trend?.series.find((s) => s.limb === limb)?.points ?? []
  const L = pick('LH'), R = pick('RH')
  const dates = [...new Set([...L, ...R].map((p) => p.measured_on))].sort().slice(-8)
  if (dates.length < 2) return null
  const at = (pts: typeof L, d: string) => pts.find((p) => p.measured_on === d)?.value ?? null
  const lv = dates.map((d) => at(L, d)), rv = dates.map((d) => at(R, d))
  const all = [...lv, ...rv].filter((v): v is number => v != null)
  const lo = Math.floor((Math.min(...all) - 3) / 5) * 5, hi = Math.ceil((Math.max(...all) + 3) / 5) * 5
  const W = 320, H = 140, x0 = 30, x1 = 280, y0 = 12, y1 = 112
  const X = (i: number) => x0 + (i * (x1 - x0)) / (dates.length - 1)
  const Y = (v: number) => y1 - ((v - lo) / (hi - lo)) * (y1 - y0)
  const line = (vs: (number | null)[]) => vs.map((v, i) => (v == null ? null : `${X(i)},${Y(v)}`)).filter(Boolean).join(' ')
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <h3 style={H2}>무릎 가동 범위 변화</h3>
      <Legend />
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', display: 'block', fontFamily: 'inherit' }}>
        {[lo, (lo + hi) / 2, hi].map((v, i) => <g key={i}><line x1={x0} x2={x1} y1={Y(v)} y2={Y(v)} stroke="#ECE8E2" strokeDasharray="3 4" /><text x={x0 - 5} y={Y(v) + 3} fontSize="9" fill="#8E949C" textAnchor="end">{Math.round(v)}</text></g>)}
        {dates.map((d, i) => <text key={d} x={X(i)} y={H - 8} fontSize="9" fill="#8E949C" textAnchor="middle">{d.slice(5)}</text>)}
        {([[lv, BLUE], [rv, ORANGE]] as const).map(([vs, c], k) => (
          <g key={k}>
            <polyline points={line(vs)} fill="none" stroke={c} strokeWidth="2" strokeLinejoin="round" />
            {vs.map((v, i) => (v == null ? null : <circle key={i} cx={X(i)} cy={Y(v)} r={i === vs.length - 1 ? 4 : 3} fill={i === vs.length - 1 ? c : '#fff'} stroke={c} strokeWidth="2" />))}
            {vs[vs.length - 1] != null ? <text x={X(vs.length - 1) + 6} y={Y(vs[vs.length - 1]!) + 3} fontSize="9.5" fontWeight="700" fill="#1B2433">{f1(vs[vs.length - 1]!)}°</text> : null}
          </g>
        ))}
      </svg>
    </section>
  )
}

export function AppVetSections({ result, cmp, trend }: { result: SessionResultOut | null | undefined; cmp: CompareOut | undefined; trend: TrendsOut | undefined }) {
  if (!result) return null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <LrBars result={result} />
      <KneeCycle result={result} />
      <CmpList cmp={cmp} />
      <KneeTrend trend={trend} />
    </div>
  )
}
