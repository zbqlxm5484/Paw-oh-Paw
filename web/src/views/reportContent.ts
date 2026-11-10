// 서버 보고서 내용(GET /sessions/{id}/report-content, 285) → 인쇄 종이의 칸 값.
// 글·숫자는 서버 값을 그대로 옮기고 새 숫자를 만들지 않는다. 예전 서버라 칸(legs·baseline.diff·symmetry_level)이 없을 때만
// 서버가 준 다른 값으로 서버와 같은 규칙을 따라 대신한다(몸 그림 색 단계·덜 쓰는 다리·기준 회차 차이).
import gaitRef from '../../public/static/assets/dog3d/gait_ref_plos.json'
import type {
  AnglesOut, LegLevel, PairCode, ReportContentCompare, ReportContentGait, ReportContentHistory, ReportContentOut, ReportContentRow,
} from '../api/client'
import { clipFromAngles, pickShots, type ClipInfo, type GaitClip, type ShotLite } from './gaitClip'

/** 보행 유형 고르는 순서: 속보 → 평보 → 미판별(서버의 대칭 점수·legs 와 같은 순서), 그 밖은 받은 순서 */
const GAIT_PICK = ['TROT', 'WALK', 'OTHER']
const ordered = (gaits: ReportContentGait[]): ReportContentGait[] =>
  [...gaits].sort((a, b) => (GAIT_PICK.indexOf(a.gait_type) + 1 || 9) - (GAIT_PICK.indexOf(b.gait_type) + 1 || 9))

/** 그 순서로 있는 첫 유형 */
export function pickGait(gaits: ReportContentGait[]): ReportContentGait | null {
  return ordered(gaits)[0] ?? null
}

/** 대상 수치를 비교할 수 있는 줄(비교 가능하고 대칭 지수가 있는 줄)이 있는지 */
const comparableLines = (g: ReportContentGait | null | undefined): ReportContentCompare[] =>
  (g?.compare ?? []).filter((x) => x.comparable && x.symmetry_value != null)

/** 다리 카드·몸 그림에 쓸 보행 유형: 서버 legs[0].gait_type, legs 가 없으면(예전 서버) 그 순서로 비교할 수 있는 첫 유형,
 *  그것도 없으면 그 순서로 있는 첫 유형 */
export function cardGait(c: ReportContentOut): ReportContentGait | null {
  const g = c.legs?.[0]?.gait_type
  if (g) {
    const hit = c.gaits.find((x) => x.gait_type === g)
    if (hit) return hit
  }
  return ordered(c.gaits).find((x) => comparableLines(x).length) ?? pickGait(c.gaits)
}

/** 색 단계(views._LEVEL 과 같은 색·이름) */
export const LEVEL_STYLE: Record<LegLevel, { name: string; fill: string; text: string }> = {
  SIMILAR: { name: '비슷합니다', fill: '#DCEFE2', text: '#2E8B57' },
  SLIGHT: { name: '조금 차이 나요', fill: '#F7D6AE', text: '#9A6A12' },
  LARGE: { name: '차이가 큽니다', fill: '#F2A898', text: '#C2412D' },
}
/** 화면에 찍히는 값(소수 첫째 자리로 반올림)으로 가른다: 5 미만 비슷 / 10 미만 조금 / 그 이상 큼(서버와 같은 규칙) */
export const round1 = (v: number): number => Math.round((v + Number.EPSILON) * 10) / 10
export const levelOf = (si: number): LegLevel => {
  const v = round1(si)
  return v < 5 ? 'SIMILAR' : v < 10 ? 'SLIGHT' : 'LARGE'
}

const PAIR_LIMBS: Record<PairCode, [string, string]> = { FORE: ['LF', 'RF'], HIND: ['LH', 'RH'] }
export const PAIRS: PairCode[] = ['FORE', 'HIND']

export interface PairView {
  pair: PairCode
  level: LegLevel | null
  /** 덜 쓰는 다리(값이 작은 쪽). 비슷하면 그림에 칠하지 않는다 */
  weak: string | null
  metric_code: string | null
  /** 이 쌍의 단계를 정한 비교 줄(서버 compare). 없으면 null */
  line: ReportContentCompare | null
  /** legs 가 서버에서 왔으면 true, compare 로 대신 정했으면 false */
  server: boolean
}

const cellValue = (rows: ReportContentRow[], code: string, limb: string): number | null => rows.find((r) => r.metric_code === code)?.cells[limb]?.value ?? null

/** 값이 작은 쪽 다리. diff_value(왼쪽 − 오른쪽) 부호로, 없으면 표의 두 값으로 */
function smallerSide(line: ReportContentCompare, rows: ReportContentRow[], pair: PairCode): string | null {
  const [l, r] = PAIR_LIMBS[pair]
  let d = line.diff_value
  if (d == null) {
    const lv = cellValue(rows, line.metric_code, l)
    const rv = cellValue(rows, line.metric_code, r)
    d = lv != null && rv != null ? lv - rv : null
  }
  if (d == null || d === 0) return null
  return d < 0 ? l : r
}

/** 쌍마다 대칭 지수(symmetry_value)가 가장 큰 비교 줄 */
export function topLine(gait: ReportContentGait | null, pair: PairCode): ReportContentCompare | null {
  const lines = comparableLines(gait).filter((x) => x.pair === pair)
  return lines.reduce<ReportContentCompare | null>((a, b) => (a == null || b.symmetry_value! > a.symmetry_value! ? b : a), null)
}

const NONE = (pair: PairCode, server: boolean): PairView => ({ pair, level: null, weak: null, metric_code: null, line: null, server })

/** 몸 그림의 색 단계·덜 쓰는 다리. 서버 legs 가 있으면 그대로(빠진 쌍 = 비교할 대상 수치 없음),
 *  legs 칸 자체가 없으면(예전 서버) gait 의 compare 로 서버와 같은 규칙 */
export function pairViews(c: ReportContentOut, gait: ReportContentGait | null): Record<PairCode, PairView> {
  const out = {} as Record<PairCode, PairView>
  for (const pair of PAIRS) {
    if (c.legs) {
      const leg = c.legs.find((x) => x.pair === pair)
      if (!leg) { out[pair] = NONE(pair, true); continue }
      const g = c.gaits.find((x) => x.gait_type === leg.gait_type) ?? gait
      const line = g?.compare.find((x) => x.pair === pair && x.metric_code === leg.metric_code) ?? null
      out[pair] = { pair, level: leg.level, weak: leg.weak_limb, metric_code: leg.metric_code, line, server: true }
      continue
    }
    const line = topLine(gait, pair)
    out[pair] = line
      ? { pair, level: levelOf(line.symmetry_value!), weak: smallerSide(line, gait!.rows, pair), metric_code: line.metric_code, line, server: false }
      : NONE(pair, false)
  }
  return out
}

/** 다리 색: 덜 쓰는 다리 = 단계 색, 비슷하면 양쪽 연두, 그 밖은 회색(views.body_map 과 같은 규칙) */
export function legFills(p: Record<PairCode, PairView>): Record<string, string> {
  const fills: Record<string, string> = {}
  for (const pair of PAIRS) {
    const v = p[pair]
    for (const limb of PAIR_LIMBS[pair]) {
      fills[limb] = !v.level ? '#E9E4DC' : v.level === 'SIMILAR' ? LEVEL_STYLE.SIMILAR.fill : v.weak === limb ? LEVEL_STYLE[v.level].fill : '#E9E4DC'
    }
  }
  return fills
}

/** 그림에 '덜 쓰는 다리'로 칠할지(비슷하면 칠하지 않는다) */
export const isWeak = (p: Record<PairCode, PairView>, limb: string): boolean => {
  const v = p[limb.endsWith('F') ? 'FORE' : 'HIND']
  return !!v.level && v.level !== 'SIMILAR' && v.weak === limb
}

// 다리 카드에는 관절 가동 범위만(몸 그림 옆 자리가 좁다). 걸음 길이·입각기 비율 등은 수의사용 좌우 비교 표에 모두 있다
const CARD_CODES = ['rom_shoulder', 'rom_elbow', 'rom_carpus', 'rom_hip', 'rom_stifle', 'rom_tarsus']
const OTHER_LIMB: Record<string, string> = { LF: 'RF', RF: 'LF', LH: 'RH', RH: 'LH' }

export interface CardMetric { n: string; v: string; other: string; lower: boolean }

/** 다리 카드 수치(서버 rows 의 칸 글 그대로). 보호자용은 그 쌍의 단계를 정한 수치 하나, 수의사용은 관절 가동 범위 */
export function legCard(gait: ReportContentGait | null, limb: string, edition: string, p: Record<PairCode, PairView>): CardMetric[] {
  if (!gait) return []
  const other = OTHER_LIMB[limb]
  const rows = gait.rows.filter((r) => CARD_CODES.includes(r.metric_code) && r.cells[limb])
  const pick = (r: ReportContentRow): CardMetric => {
    const a = r.cells[limb]!, b = r.cells[other]
    return { n: r.label, v: a.text, other: b?.text ?? '-', lower: a.value != null && b?.value != null && a.value < b.value }
  }
  if (edition === 'VET') return rows.map(pick)
  const code = p[limb.endsWith('F') ? 'FORE' : 'HIND'].metric_code
  // 보호자용: 단계를 정한 수치(걸음 길이·입각기 비율일 수도 있다), 없으면 첫 가동 범위
  const main = gait.rows.find((r) => r.metric_code === code && r.cells[limb]) ?? rows[0]
  return main ? [pick(main)] : []
}

/** 대칭 점수 색 단계: 서버 symmetry_level, 없으면 100 − 점수로 같은 규칙 */
export function symLevel(c: ReportContentOut): LegLevel | null {
  const s = c.session.symmetry_level
  if (s === 'SIMILAR' || s === 'SLIGHT' || s === 'LARGE') return s
  return c.session.symmetry_score == null ? null : levelOf(100 - c.session.symmetry_score)
}

/** 기준 회차 대비(%p): baseline.diff, 없으면 symmetry_score − baseline.symmetry_score. 이번 회차가 기준이거나 값이 없으면 null */
export function baselineDiff(c: ReportContentOut): number | null {
  const b = c.baseline
  if (!b || b.session_id === c.session_id) return null
  if (b.diff !== undefined) return b.diff // 서버 값(한쪽이라도 없으면 null)
  if (c.session.symmetry_score == null || b.symmetry_score == null) return null
  return Math.round((c.session.symmetry_score - b.symmetry_score) * 100) / 100
}

/** "2026-11-09" → "11.9"(화면 추세 눈금과 같은 모양) */
export const shortDay = (iso: string): string => {
  const [, m, d] = iso.split('-').map(Number)
  return m && d ? `${m}.${d}` : iso
}

export interface TrendPoint { x: number; y: number; v: number; t: string; cur: boolean }

/** history(오래된 순, 이 회차 포함) → 추세 점. 실패 회차(null)는 뺀다. 좌표는 views.body_map 의 trend 와 같은 식 */
export function trendPoints(history: ReportContentHistory[], round: number): TrendPoint[] {
  const hist = history.filter((h): h is ReportContentHistory & { symmetry_score: number } => h.symmetry_score != null).slice(-8)
  if (!hist.length) return []
  const lo = Math.min(...hist.map((h) => h.symmetry_score)) - 3
  const hi = Math.max(...hist.map((h) => h.symmetry_score)) + 3
  const r1 = (v: number) => Math.round(v * 10) / 10
  const curIdx = hist.map((h) => h.round).lastIndexOf(round)
  return hist.map((h, i) => ({
    x: r1(30 + i * (300 / Math.max(1, hist.length - 1))), y: r1(80 - ((h.symmetry_score - lo) / (hi - lo)) * 64),
    v: h.symmetry_score, t: shortDay(h.measured_on), cur: curIdx >= 0 ? i === curIdx : i === hist.length - 1,
  }))
}

/** 체급 코드 → 몸 그림 크기(views._svg 의 S·M·L) */
export const sizeCode = (s: string | null | undefined): string => ({ SMALL: 'S', LARGE: 'L' } as Record<string, string>)[s ?? ''] ?? 'M'

const SVG_LEGS: [string, string][] = [['front_left', 'LF'], ['front_right', 'RF'], ['hind_left', 'LH'], ['hind_right', 'RH']]

/** 몸 그림 SVG 에 다리 색과 관심 다리 점선을 넣는다(views.body_map 과 같은 치환) */
export function paintBody(svg: string, fills: Record<string, string>, focus: string | null | undefined): string {
  for (const [pid, code] of SVG_LEGS) {
    const stroke = focus === code ? 'stroke="#D2601A" stroke-width="6" stroke-dasharray="14 8"' : 'stroke="#B8B0A4" stroke-width="2"'
    svg = svg.replace(`<path id="${pid}" fill="#E9E4DC" stroke="#B8B0A4" stroke-width="2"`, `<path id="${pid}" fill="${fills[code]}" ${stroke}`)
  }
  return svg
}

// ── 수의사용 뒷무릎 각도 · 보행 주기: 이 회차의 실제 각도(GET /sessions/{id} → /shots/{id}/angles)로만 그린다 ──
// 곡선은 웹 3D 와 같은 views/gaitClip.ts(촬영 고르기·걸음 자르기·50칸 평균)로 만든다. 못 만들면 null → 칸을 뺀다(견본·합성 곡선 쓰지 않음)

export interface KneeCurve { gait: string; L: number[] | null; R: number[] | null; strides: number }

/** 3D 걸음 곡선에서 LH·RH 무릎 곡선. 촬영이 없거나 걸음을 못 잘라 반대쪽 곡선을 빌려 온 쪽은 빼고(같은 배열을 가리킨다),
 *  두 쪽 다 실제 곡선이 없으면 null */
export function kneeFromClip(clip: GaitClip, info: ClipInfo): KneeCurve | null {
  const l = clip.legs.LH?.joint['무릎'] ?? null
  const r = clip.legs.RH?.joint['무릎'] ?? null
  const realSide = (s: 'L' | 'R') => info.sides.includes(s) && !info.mirrored.includes(s)
  let L = l && realSide('L') ? l : null
  let R = r && realSide('R') ? r : null
  if (L && R && L === R) {
    // 한쪽이 반대쪽 무릎을 빌려 왔다: 빌려 온 쪽(borrowed)을 뺀다. 둘 다 빌린 표시면 어느 쪽이 원본인지 몰라 둘 다 뺀다
    const bl = info.borrowed.includes('L'), br = info.borrowed.includes('R')
    if (bl && !br) L = null
    else if (br && !bl) R = null
    else L = R = null
  }
  if (!L && !R) return null
  return { gait: info.gait, L, R, strides: info.strides }
}

/** 회차 id → 실제 무릎 곡선. 회차·촬영·각도 중 하나라도 못 받거나 걸음을 못 자르면 null */
export async function loadKneeCurve(
  deps: { session: (id: string) => Promise<{ shots: ShotLite[] }>; angles: (shotId: string) => Promise<AnglesOut> },
  sessionId: string,
  prefer: string | null,
): Promise<KneeCurve | null> {
  try {
    const s = await deps.session(sessionId)
    const pick = pickShots(s.shots ?? [], prefer)
    if (!pick) return null
    const ids = [...pick.L, ...pick.R]
    const resps = (await Promise.all(ids.map((id) => deps.angles(id).catch(() => null)))).filter((r): r is AnglesOut => !!r && Array.isArray(r.passes))
    const got = clipFromAngles(resps, pick.gait)
    return got ? kneeFromClip(got.clip, got.info) : null
  } catch {
    return null
  }
}

type Ref = { gaits: Record<string, Record<string, { dogs: number; mean: number[]; min: number[]; max: number[] }>> }
type Tick = { y: number; x: number; t: string }
export interface KneeChartView { y: Tick[]; x: Tick[]; x0: number; x1: number; ref_band: string; ref_mean: string; L: string; R: string }

/** 무릎 곡선 → Report.tsx KneeChart 가 받는 모양(views.knee_chart 와 같은 좌표·눈금). 정상 참고 범위는 공개 자료 무릎(평보면 walk, 그 밖은 trot) */
export function kneeChartView(k: KneeCurve): KneeChartView {
  const ref = (gaitRef as unknown as Ref).gaits[k.gait === 'WALK' ? 'walk' : 'trot']['무릎']
  const allv = [...(k.L ?? []), ...(k.R ?? []), ...ref.min, ...ref.max]
  const lo = Math.floor(Math.min(...allv) / 10) * 10
  const hi = Math.ceil(Math.max(...allv) / 10) * 10
  const [x0, x1, y0, y1] = [44, 300, 12, 120]
  const f1 = (v: number) => (Math.round(v * 10) / 10).toFixed(1)
  const y = (v: number) => y1 - ((v - lo) / (hi - lo)) * (y1 - y0)
  const pt = (c: number[]) => c.map((v, i) => `${f1(x0 + ((x1 - x0) * i) / c.length)},${f1(y(v))}`)
  const line = (c: number[] | null) => (c ? pt(c).join(' ') : '')
  const mid = Math.floor((lo + hi) / 2)
  return {
    L: line(k.L), R: line(k.R), ref_band: [...pt(ref.max), ...pt(ref.min).reverse()].join(' '), ref_mean: line(ref.mean),
    y: [hi, mid, lo].map((v) => ({ y: Math.round(y(v) * 10) / 10, x: 0, t: `${v}°` })),
    x: [0, 50, 100].map((p) => ({ x: x0 + ((x1 - x0) * p) / 100, y: 0, t: `${p}` })),
    x0, x1,
  }
}
