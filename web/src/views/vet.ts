// 수의사용 보고서의 추가 섹션(백엔드 보고서 시안 반영, S15P31A404-103·208):
// 좌우 비교(위아래 막대), 지난 측정과 비교, 무릎 가동 범위 변화, 그 밖의 수치.
// 화면 데이터는 회차 결과(Result)에서 만든다. 지난 측정 비교의 판정은 백엔드 비교 API(15.8)가 있으면 그 값을 쓰고,
// 없으면(시연 데이터·이력 API 없는 서버) 같은 규칙을 이 파일의 오차 범위로 흉내 낸다.
import type { CompareItemOut, CompareOut } from '../api/client'
import type { Account, Metrics, Result } from '../store/types'

export const GAIT_CODE: Record<string, string> = { 속보: 'TROT', 평보: 'WALK', '보행 유형 미판별': 'OTHER' }
const GAIT_ORDER = ['평보', '속보', '보행 유형 미판별']

/** (수치 코드, 이름, 설명, 앞/뒤). 설명은 보고서 용어(terms.yaml)와 같은 말 */
export const JOINTS: [string, string, string, 'F' | 'H'][] = [
  ['rom_shoulder', '어깨', '', 'F'],
  ['rom_elbow', '팔꿈치', '', 'F'],
  ['rom_carpus', '앞발목', '앞다리의 발목 관절(사람의 손목에 해당)', 'F'],
  ['rom_hip', '고관절', '뒷다리가 몸통과 이어지는 엉덩이 관절', 'H'],
  ['rom_stifle', '무릎', '', 'H'],
  ['rom_tarsus', '뒷발목', '뒷다리의 발목 관절(사람의 발목에 해당)', 'H'],
]
const NAME: Record<string, string> = Object.fromEntries(JOINTS.map(([c, n]) => [c, n]))
const UNIT: Record<string, string> = { deg: '°', pct: '%', pct_body: '%' }

/** 회차 비교 오차 범위(백엔드 config/tolerance.yaml 의 develop 값). 백엔드 비교 API 가 없을 때만 쓴다 */
export const TOLERANCE: Record<string, number> = { rom_shoulder: 5.0, rom_carpus: 11.8, rom_hip: 5.0, rom_stifle: 8.0, rom_tarsus: 5.9, stance_ratio: 5.8 }

const r1 = (v: number) => Math.round(v * 10) / 10
const fmt = (v: number) => r1(v).toFixed(1)

/** 보행 유형별 다리 수치. 예전 결과(보행 하나만 저장)는 대표 보행 하나로 */
export function gaitsOf(r: Result): [string, Metrics][] {
  const mg = r.mg && Object.keys(r.mg).length ? r.mg : { [r.gait || '속보']: r.m }
  return GAIT_ORDER.filter((g) => mg[g]).map((g) => [g, mg[g]] as [string, Metrics])
}

const val = (m: Metrics | undefined, code: string, limb: string): number | null => {
  const v = m?.[limb]?.[code]
  return v === undefined || v === null ? null : v
}

// ── 1. 왼쪽과 오른쪽 비교 ──
export interface LrRow { code: string; n: string; desc: string; l: number; r: number; diff: string; top: boolean; wl: number; wr: number }
export interface LrGait { gait: string; rows: LrRow[] }

/** 보행 유형마다 관절 가동 범위의 좌우 막대. 비율(대칭 지수)로 차이가 가장 큰 줄에 top 표시 */
export function lrCompare(r: Result): LrGait[] {
  const out: LrGait[] = []
  for (const [gait, m] of gaitsOf(r)) {
    const rows: LrRow[] = []
    for (const [code, n, desc, fh] of JOINTS) {
      const l = val(m, code, 'L' + fh)
      const rt = val(m, code, 'R' + fh)
      if (l == null || rt == null) continue
      rows.push({ code, n, desc, l, r: rt, diff: fmt(Math.abs(l - rt)) + '°', top: false, wl: 0, wr: 0 })
    }
    if (!rows.length) continue
    const ratio = (x: LrRow) => (x.l + x.r ? Math.abs(x.l - x.r) / ((x.l + x.r) / 2) : 0)
    const top = rows.reduce((a, b) => (ratio(b) > ratio(a) ? b : a))
    top.top = ratio(top) > 0
    out.push({ gait, rows })
  }
  // 막대 길이는 모든 보행에서 같은 눈금(가장 큰 값 = 100%)
  const mx = Math.max(1, ...out.flatMap((g) => g.rows.flatMap((x) => [x.l, x.r])))
  for (const g of out) for (const x of g.rows) [x.wl, x.wr] = [(x.l / mx) * 100, (x.r / mx) * 100]
  return out
}

// ── 2. 지난 측정과 비교 ──
export type Judge = 'INCREASE' | 'DECREASE' | 'WITHIN_RANGE' | 'RANGE_NOT_SET' | 'UNKNOWN' | 'NOT_COMPARABLE'
export interface CmpRow { n: string; side: string; u: string; b: number; t: number; tol: number | null; j: Judge; diff: string }
export interface CmpView {
  baseDate: string
  modelChanged: boolean
  changed: CmpRow[]
  within: CmpRow[]
  valueOnly: CmpRow[]
  /** 막대 눈금(모든 줄 같은 눈금) */
  lo: number
  hi: number
  /** 백엔드 판정이면 true, 이 브라우저에서 흉내 낸 것이면 false */
  server: boolean
}

const SIDE: Record<string, string> = { LF: '왼쪽', RF: '오른쪽', LH: '왼쪽', RH: '오른쪽' }

function view(rows: CmpRow[], baseDate: string, modelChanged: boolean, server: boolean): CmpView {
  const vals = rows.flatMap((x) => [x.b - (x.tol ?? 0), x.t, x.b + (x.tol ?? 0)])
  const lo = Math.floor((Math.min(...vals, 1e9) - 2) / 10) * 10
  const hi = Math.ceil((Math.max(...vals, -1e9) + 2) / 10) * 10
  const big = (x: CmpRow) => Math.abs(x.t - x.b)
  return {
    baseDate, modelChanged, server, lo, hi,
    changed: rows.filter((x) => x.j === 'INCREASE' || x.j === 'DECREASE').sort((a, b) => big(b) - big(a)),
    within: rows.filter((x) => x.j === 'WITHIN_RANGE'),
    valueOnly: rows.filter((x) => x.j === 'RANGE_NOT_SET' || x.j === 'UNKNOWN'),
  }
}

/** 백엔드 비교 API 응답 → 화면. 관절 가동 범위만, 값이 둘 다 있는 줄만 */
export function cmpFromServer(o: CompareOut, gait: string): CmpView {
  const rows: CmpRow[] = []
  for (const code of JOINTS.map(([c]) => c)) {
    for (const it of o.items.filter((x: CompareItemOut) => x.metric_code === code && x.gait_type === gait)) {
      if (it.base_value == null || it.target_value == null) continue
      const tol = TOLERANCE[code] ?? null
      rows.push({
        n: NAME[code], side: SIDE[it.limb] ?? it.limb, u: UNIT[it.unit] ?? '', b: it.base_value, t: it.target_value,
        tol: it.judgement === 'RANGE_NOT_SET' || it.judgement === 'UNKNOWN' ? null : tol, j: it.judgement as Judge,
        diff: fmt(it.target_value - it.base_value),
      })
    }
  }
  return view(rows, o.base.measured_on, o.model_changed, true)
}

/** 이 회차 r 바로 앞의 유효 회차(같은 반려견) */
export function previousOf(acct: Account, r: Result): Result | null {
  const vs = acct.results.filter((x) => x.dog === r.dog && x.st !== 'fail')
  const i = vs.findIndex((x) => x.id === r.id)
  return i >= 0 && i + 1 < vs.length ? vs[i + 1] : null
}

/** 백엔드 판정이 없을 때: 같은 보행의 직전 회차 값과 오차 범위로 판정(통과 수 조건은 알 수 없어 보지 않는다) */
export function cmpLocal(acct: Account, r: Result, gait: string): CmpView | null {
  const p = previousOf(acct, r)
  if (!p) return null
  const tm = Object.fromEntries(gaitsOf(r))[gait]
  const bm = Object.fromEntries(gaitsOf(p))[gait]
  if (!tm || !bm) return null
  const rows: CmpRow[] = []
  for (const [code, n, , fh] of JOINTS) {
    for (const s of ['L', 'R']) {
      const b = val(bm, code, s + fh)
      const t = val(tm, code, s + fh)
      if (b == null || t == null) continue
      const tol = TOLERANCE[code] ?? null
      const d = r1(t - b)
      const j: Judge = p.model !== r.model ? 'UNKNOWN' : tol == null ? 'RANGE_NOT_SET' : Math.abs(d) <= tol ? 'WITHIN_RANGE' : d > 0 ? 'INCREASE' : 'DECREASE'
      rows.push({ n, side: s === 'L' ? '왼쪽' : '오른쪽', u: '°', b, t, tol: j === 'RANGE_NOT_SET' || j === 'UNKNOWN' ? null : tol, j, diff: fmt(d) })
    }
  }
  return view(rows, p.day || p.date, p.model !== r.model, false)
}

// ── 3. 무릎 가동 범위 변화 ──
export interface TrendView { x: string[]; l: (number | null)[]; r: (number | null)[]; lo: number; hi: number }

/** 이 회차까지의 유효 회차(오래된 것부터)에서 무릎 가동 범위 좌우. 같은 보행 값만 */
export function kneeTrend(acct: Account, r: Result, gait: string): TrendView | null {
  const vs = acct.results.filter((x) => x.dog === r.dog && x.st !== 'fail')
  const i = vs.findIndex((x) => x.id === r.id)
  const upto = (i >= 0 ? vs.slice(i) : vs).slice(0, 8).reverse()
  const pts = upto.map((x) => {
    const m = Object.fromEntries(gaitsOf(x))[gait]
    return { d: (x.day || '').slice(5) || x.date, l: val(m, 'rom_stifle', 'LH'), r: val(m, 'rom_stifle', 'RH') }
  }).filter((p) => p.l != null || p.r != null)
  if (pts.length < 2) return null
  const all = pts.flatMap((p) => [p.l, p.r]).filter((v): v is number => v != null)
  return {
    x: pts.map((p) => p.d), l: pts.map((p) => p.l), r: pts.map((p) => p.r),
    lo: Math.floor((Math.min(...all) - 3) / 5) * 5, hi: Math.ceil((Math.max(...all) + 3) / 5) * 5,
  }
}

// ── 4. 그 밖의 수치 ──
export const OTHER: [string, string, string][] = [
  ['stride_length', '걸음 길이(몸통 길이 기준)', '%'],
  ['stance_ratio', '입각기 비율', '%'],
  ['paw_lift', '발 들림 높이(몸통 길이 기준)', '%'],
  ['stifle_cv', '무릎 움직임 일관성', '%'],
]
export const LIMBS: [string, string][] = [['LF', '왼앞'], ['RF', '오른앞'], ['LH', '왼뒤'], ['RH', '오른뒤']]

/** 대표 보행의 다리별 그 밖의 수치. 값이 하나도 없는 줄은 뺀다 */
export function otherRows(r: Result, gait: string): { n: string; v: string[] }[] {
  const m = Object.fromEntries(gaitsOf(r))[gait] ?? r.m
  return OTHER.map(([code, n, u]) => ({ n, v: LIMBS.map(([limb]) => { const x = val(m, code, limb); return x == null ? '-' : `${fmt(x)}${u}` }) }))
    .filter((row) => row.v.some((x) => x !== '-'))
}

// ── 경과 비교 화면(Compare.tsx)의 줄을 서버 비교 API 로 ──
const CMP_NAME: Record<string, string> = {
  rom_stifle: '무릎 가동 범위', rom_hip: '고관절 가동 범위', rom_tarsus: '뒷발목 가동 범위',
  rom_shoulder: '어깨 가동 범위', rom_elbow: '팔꿈치 가동 범위', rom_carpus: '앞발목 가동 범위',
  stride_length: '걸음 길이', stance_ratio: '입각기 비율',
}
const GAIT_NAME: Record<string, string> = { TROT: '속보', WALK: '평보', OTHER: '보행 유형 미판별' }

/** 서버 비교 결과 → 경과 비교 화면의 줄 모양(views.compare_view 의 rows 와 같은 칸). 대표 보행 하나, 관심 다리 먼저 */
export function serverCompareRows(o: CompareOut, focus?: string | null) {
  const gaits = [...new Set(o.items.map((x) => x.gait_type))]
  const gait = ['TROT', 'WALK', 'OTHER'].find((g) => gaits.includes(g)) ?? gaits[0]
  const codes = Object.keys(CMP_NAME)
  const items = o.items
    .filter((x) => x.gait_type === gait && codes.includes(x.metric_code))
    .sort((a, b) => Number(!!focus && b.limb === focus) - Number(!!focus && a.limb === focus) || codes.indexOf(a.metric_code) - codes.indexOf(b.metric_code))
  const LIMB_K: Record<string, string> = { LF: '왼앞', RF: '오른앞', LH: '왼뒤', RH: '오른뒤' }
  const rows = items.map((x, i) => {
    const u = UNIT[x.unit] ?? ''
    const isFocus = !!focus && x.limb === focus
    const bt = i ? '1px solid #F2EFEA' : 'none'
    const limb = (LIMB_K[x.limb] ?? x.limb) + (isFocus ? ' · 관심 다리' : '') + ` · ${GAIT_NAME[x.gait_type] ?? x.gait_type}`
    if (x.base_value == null || x.target_value == null) {
      return { n: CMP_NAME[x.metric_code], limb, lc: '#8E949C', vals: x.note?.message ?? '한쪽 회차에서 측정 불가', j: '비교 불가', bg: '#F4F2EE', c: '#8E949C', bt }
    }
    const d = x.diff ?? x.target_value - x.base_value
    const j = x.judgement === 'INCREASE' ? `▲ 증가 ${fmt(Math.abs(d))}${u}` : x.judgement === 'DECREASE' ? `▼ 감소 ${fmt(Math.abs(d))}${u}` : x.judgement === 'WITHIN_RANGE' ? '범위 안' : '값만'
    const moved = x.judgement === 'INCREASE' || x.judgement === 'DECREASE'
    return {
      n: CMP_NAME[x.metric_code], limb, lc: isFocus ? '#B4501A' : '#8E949C', vals: `${fmt(x.base_value)}${u} → ${fmt(x.target_value)}${u}`,
      j, bg: moved ? '#EEE8DF' : '#F4F2EE', c: moved ? '#1B2433' : '#5B6472', bt,
    }
  })
  return { rows, modelChanged: o.model_changed, baseDate: o.base.measured_on, tDate: o.target.measured_on }
}
