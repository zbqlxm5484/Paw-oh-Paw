/**
 * API 응답 → 디자인 프로토타입이 쓰던 값 모양.
 * 디자인 로직(WebProto·AppProto)은 DOGS·RES 목업 모양을 기준으로 짜여 있어, 그 모양을 그대로 만들어 준다.
 * 화면 문구·배치는 디자인 원본이고, 여기서는 값만 채운다.
 */
import { METRIC_LABEL, fmtMonthDay, metricLabel } from '../api/labels'
import type {
  CompareOut, DogOut, GaitType, Limb, LimbCompareOut, ReportOut, SessionDetailOut, SessionHistoryItem, SessionResultOut, SessionStatus, Sex, SizeClass, StaffOut, TrendsOut, Unit,
} from '../api/types'

/* ---------- 디자인 쪽 코드 ---------- */
export type DSex = 'm' | 'f' | 'mn' | 'fs'
export type DSize = 'S' | 'M' | 'L'
export type DGait = 'walk' | 'trot'
/** 결과 표를 만든 보행 묶음. other = 서버의 OTHER(보행 유형 판별 전에는 모든 통과가 여기로 온다) */
export type DRowsKey = DGait | 'other'
export type DSt = 'ok' | 'part' | 'fail'

export const SEX_TO_API: Record<DSex, Sex> = { m: 'MALE', f: 'FEMALE', mn: 'MALE_NEUTERED', fs: 'FEMALE_SPAYED' }
export const SEX_FROM_API: Record<Sex, DSex> = { MALE: 'm', FEMALE: 'f', MALE_NEUTERED: 'mn', FEMALE_SPAYED: 'fs' }
export const SIZE_TO_API: Record<DSize, SizeClass> = { S: 'SMALL', M: 'MEDIUM', L: 'LARGE' }
export const SIZE_FROM_API: Record<SizeClass, DSize> = { SMALL: 'S', MEDIUM: 'M', LARGE: 'L' }
export const UNIT_SIGN: Record<Unit, string> = { deg: '°', pct: '%', pct_body: '%', body_per_sec: '몸통/초', count: '회' }

/** 디자인의 반려견 */
export interface DDog {
  id: string
  name: string
  breed: string
  birth: string
  kg: string
  sex: DSex
  size: DSize
  sizeManual: boolean
  rehab: string
  focus: Limb | null
  memo: string
  base: string | null
  /** 측정 중인 회차 */
  open: string | null
  count: number
  raw: DogOut
}

export function toDog(d: DogOut): DDog {
  return {
    id: d.id, name: d.name, breed: d.breed, birth: d.birth_year ? String(d.birth_year) : '', kg: String(d.weight_kg),
    sex: d.sex ? SEX_FROM_API[d.sex] : 'm', size: SIZE_FROM_API[d.size_class], sizeManual: d.size_class_manual,
    rehab: d.rehab_start_date ?? '', focus: d.focus_limb, memo: d.memo ?? '', base: d.baseline_session_id, open: d.open_session_id,
    count: d.session_count, raw: d,
  }
}

/** 회차 결과 표의 한 줄(디자인 mrows 의 모양) */
export interface DRow {
  sec: string | false
  n: string
  leg: '앞다리' | '뒷다리'
  code: string
  u: string
  l: number
  r: number
  na: boolean
  reason: string
  /** 좌우 차이 비율(%) */
  si: number
}

/** 디자인의 회차 결과(RES 의 한 항목) */
export interface DRes {
  id: string
  dog: string
  date: string
  time: string
  st: DSt
  w: string
  /** [측정한 통과, 쓴 통과] */
  ps: [number, number]
  ex: [string, number][]
  model: string
  rep: boolean
  /** 결과를 아직 안 받았으면 false. 그동안 수치는 '—' */
  loaded: boolean
  sym: number | null
  rom: number | null
  sL: number | null
  sR: number | null
  rowsBy: Record<DRowsKey, DRow[]>
  measured_on: string
  status: SessionStatus
  isBaseline: boolean
  raw: SessionHistoryItem
  result: SessionResultOut | null
}

const fmtVal = (v: number | null, unit: Unit): number => {
  if (v == null) return 0
  return unit === 'deg' ? Math.round(v * 10) / 10 : Math.round(v)
}

const GAIT_OF: Record<DRowsKey, GaitType> = { walk: 'WALK', trot: 'TROT', other: 'OTHER' }

function rowsOf(result: SessionResultOut, key: DRowsKey): DRow[] {
  const g = result.gaits.find((x) => x.gait_type === GAIT_OF[key])
  if (!g) return []
  const order: LimbCompareOut[] = [...g.limb_compare.filter((c) => c.pair === 'HIND'), ...g.limb_compare.filter((c) => c.pair === 'FORE')]
  let lastLeg = ''
  return order.map((c) => {
    const leg = c.pair === 'HIND' ? '뒷다리' : '앞다리'
    const sec = leg !== lastLeg ? leg : false
    lastLeg = leg
    return {
      sec, n: METRIC_LABEL[c.metric_code] ?? c.metric_code, leg, code: c.metric_code, u: UNIT_SIGN[c.unit],
      l: fmtVal(c.left, c.unit), r: fmtVal(c.right, c.unit), na: !c.comparable, reason: c.reason?.message ?? '',
      si: c.symmetry_index ?? 0,
    }
  })
}

function timeOf(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/** 대칭 지수(%): 좌우 차이 비율이 가장 큰 항목을 100 에서 뺀 값. 디자인은 "높을수록 대칭" 으로 보여 준다 */
export function symOf(rows: DRow[]): number | null {
  const meas = rows.filter((r) => !r.na)
  if (!meas.length) return null
  const top = Math.max(...meas.map((r) => r.si))
  return Math.max(0, Math.min(100, Math.round(100 - top)))
}

export function toResult(h: SessionHistoryItem, dogId: string, result: SessionResultOut | null | undefined): DRes {
  const trot = result ? rowsOf(result, 'trot') : []
  const walk = result ? rowsOf(result, 'walk') : []
  const other = result ? rowsOf(result, 'other') : []
  const main = trot.length ? trot : walk.length ? walk : other
  const stifle = main.find((r) => r.code === 'rom_stifle' && !r.na)
  const stride = main.find((r) => r.code === 'stride_length' && !r.na)
  // 실패: 분석 실패이거나, 분석은 끝났지만 쓸 수 있는 통과가 0건(gaits 빈 배열·used 0)일 때 → 다시 촬영 안내
  // 일부 유효: 무효 촬영이 있거나 유효 통과가 일부뿐(FEW_VALID_PASSES)일 때
  const st: DSt = h.status === 'FAILED' || (result && result.pass_counts.used === 0) ? 'fail' : result && (result.shot_counts.invalid > 0 || result.notices.some((n) => n.code === 'FEW_VALID_PASSES')) ? 'part' : 'ok'
  const vp = h.valid_passes ? h.valid_passes.LEFT + h.valid_passes.RIGHT : 0
  return {
    id: h.id, dog: dogId, date: fmtMonthDay(h.measured_on), time: timeOf(result?.completed_at ?? null), st,
    w: h.weight_kg != null ? String(h.weight_kg) : '-',
    ps: result ? [result.pass_counts.measured, result.pass_counts.used] : [vp, vp],
    ex: result ? result.exclude_summary.map((e) => [e.message, e.count] as [string, number]) : [],
    model: h.model_version ?? result?.model_version ?? '-', rep: h.reports?.OWNER === 'DONE',
    loaded: !!result || h.status === 'FAILED',
    sym: symOf(main), rom: stifle ? Math.round((stifle.l + stifle.r) / 2) : null,
    sL: stride ? stride.l : null, sR: stride ? stride.r : null,
    rowsBy: { trot, walk, other }, measured_on: h.measured_on, status: h.status, isBaseline: h.is_baseline, raw: h, result: result ?? null,
  }
}

/** 디자인 상태 배지: [문구, 배경, 글자색] */
export const ST: Record<DSt, [string, string, string]> = { ok: ['유효', '#E8F3EC', '#2E8B57'], part: ['일부 유효', '#FAF1DF', '#9A6A12'], fail: ['실패', '#F8E7E3', '#C2412D'] }

/** 분석 중 진행도. 디자인은 0~5 단계(STEPS)로 그린다 */
export const STEPS = ['업로드 완료', '반려견 찾는 중', '관절점 찾는 중', '보행 수치 계산 중', '보고서 만드는 중']
export interface DAna {
  dog: string
  sessionId: string
  /** 0~5 */
  p: number
  n: number
  status: SessionStatus
}
export function toAna(s: SessionDetailOut | undefined, dogId: string, sessionId: string): DAna {
  if (!s) return { dog: dogId, sessionId, p: 0, n: 0, status: 'MEASURING' }
  const total = s.shots.length
  const done = s.shots.filter((x) => x.status === 'DONE' || x.status === 'FAILED').length
  let p: number
  if (s.status === 'AGGREGATING') p = 3.5
  else if (s.status === 'DONE') p = 4.5
  else if (!total) p = 0
  else p = 1 + Math.min(1.99, (done / total) * 2)
  return { dog: dogId, sessionId, p, n: total, status: s.status }
}

/** 계정 정보: 디자인 DEMO 모양 */
export interface DAcct {
  type: 'org'
  name: string
  id: string
  loc: string
  dev: string
  staffName: string
  email: string
  /** 서버 알림 설정(192). 예전 서버면 undefined */
  notifOn?: boolean
}
export function toAcct(s: StaffOut | null): DAcct {
  return { type: 'org', name: s?.institution.name ?? '', id: s?.login_id ?? '', loc: '-', dev: '-', staffName: s?.name ?? '', email: s?.email ?? '', notifOn: s?.notif_on }
}

/* ---------- 경과 비교 (api-spec 8절 → 디자인 cp 모양) ---------- */
export const LIMB_KO: Record<Limb, string> = { LF: '왼앞', RF: '오른앞', LH: '왼뒤', RH: '오른뒤' }
export const TREND_CODE: Record<string, string> = { rom: 'rom_stifle', stride: 'stride_length', stance: 'stance_ratio', sym: 'rom_stifle' }

export interface DCompareRow {
  n: string
  limb: string
  lc: string
  vals: string
  j: string
  bg: string
  c: string
  bt: string
}

export function compareRows(cmp: CompareOut | undefined, focus: Limb | null): DCompareRow[] {
  if (!cmp) return []
  const trot = cmp.items.filter((i) => i.gait_type === 'TROT')
  const items = trot.length ? trot : cmp.items
  const rank = (i: (typeof items)[number]) => (focus && i.limb === focus ? 0 : i.judgement !== 'NOT_COMPARABLE' && i.judgement !== 'UNKNOWN' ? 1 : 2)
  return items
    .map((it, idx) => ({ it, idx }))
    .sort((a, b) => rank(a.it) - rank(b.it) || a.idx - b.idx)
    .map(({ it }, i) => {
      const n = metricLabel(it.metric_code)
      const u = UNIT_SIGN[it.unit]
      const bt = i ? '1px solid #F2EFEA' : 'none'
      const isFocus = !!focus && it.limb === focus
      const limb = it.limb === 'NONE' ? '전체' : LIMB_KO[it.limb] + (isFocus ? ' · 관심 다리' : '')
      const lc = isFocus ? '#B4501A' : '#8E949C'
      if (it.base_value == null || it.target_value == null) {
        return { n, limb, lc, vals: it.note?.message ?? '한쪽 회차에서 측정 불가', j: '비교 불가', bg: '#F4F2EE', c: '#8E949C', bt }
      }
      const b = fmtVal(it.base_value, it.unit), t = fmtVal(it.target_value, it.unit), df = Math.round((t - b) * 10) / 10
      // 모델이 달라 판단을 보류한 항목: 값은 보여 주되 증감 판정은 하지 않는다
      if (it.judgement === 'UNKNOWN' || it.judgement === 'NOT_COMPARABLE') {
        return { n, limb, lc, vals: `${b}${u} → ${t}${u}`, j: it.judgement === 'UNKNOWN' ? '판단 보류' : '비교 불가', bg: '#F4F2EE', c: '#8E949C', bt }
      }
      const inR = it.judgement === 'WITHIN_RANGE'
      return {
        n, limb, lc, vals: `${b}${u} → ${t}${u}`,
        j: inR ? '범위 안' : df > 0 ? `▲ 증가 ${df}${u}` : `▼ 감소 ${-df}${u}`,
        bg: inR ? '#F4F2EE' : '#EEE8DF', c: inR ? '#5B6472' : '#1B2433', bt,
      }
    })
}

export interface DTrend {
  tl: string
  tr: string
  dl: { x: number; y: number; c: string }[]
  xl: string[]
  two: boolean
}

/** 추이 그래프 좌표(디자인 320×150 뷰박스). tk=sym 은 좌우 차이 비율을 100 에서 뺀 한 줄 */
export function trendLines(t: TrendsOut | undefined, tk: string): DTrend {
  const empty: DTrend = { tl: '', tr: '', dl: [], xl: [], two: tk !== 'sym' }
  if (!t) return empty
  let A: (number | null)[] = [], Bv: (number | null)[] = [], dates: string[] = []
  if (tk === 'sym') {
    const pair = t.lr_diff.find((p) => p.pair === 'HIND') ?? t.lr_diff[0]
    if (!pair) return empty
    A = pair.points.map((p) => (p.symmetry_index == null ? null : Math.round(100 - p.symmetry_index)))
    dates = pair.points.map((p) => p.measured_on)
  } else {
    const left = t.series.find((s) => s.limb === 'LH' || s.limb === 'LF'), right = t.series.find((s) => s.limb === 'RH' || s.limb === 'RF')
    const src = left ?? t.series[0]
    if (!src) return empty
    dates = src.points.map((p) => p.measured_on)
    A = src.points.map((p) => (p.measurable && p.value != null ? fmtVal(p.value, t.unit) : null))
    Bv = right ? right.points.map((p) => (p.measurable && p.value != null ? fmtVal(p.value, t.unit) : null)) : []
  }
  const allV = [...A, ...Bv].filter((v): v is number => v != null)
  if (!allV.length || dates.length < 2) return { ...empty, xl: dates.map((d) => fmtMonthDay(d).replace('월 ', '.').replace('일', '')) }
  const mn = Math.min(...allV) - 2, mx = Math.max(...allV) + 2
  const X = (i: number) => Math.round(20 + i * (280 / (dates.length - 1))), Y = (v: number) => Math.round(130 - ((v - mn) / (mx - mn)) * 110)
  const pts = (arr: (number | null)[], c: string) => arr.map((v, i) => (v == null ? null : { x: X(i), y: Y(v), c })).filter((p): p is { x: number; y: number; c: string } => !!p)
  const a = pts(A, '#3B6FE0'), b = pts(Bv, '#E5604D')
  return { tl: a.map((p) => `${p.x},${p.y}`).join(' '), tr: b.map((p) => `${p.x},${p.y}`).join(' '), dl: [...a, ...b], xl: dates.map((d) => fmtMonthDay(d).replace('월 ', '.').replace('일', '')), two: Bv.length > 0 }
}

/** 보고서 상태 한 줄(디자인 repStatus) */
export function reportStatusLine(r: ReportOut | undefined, model: string): string {
  if (!r) return '보고서가 아직 없습니다'
  if (r.status === 'DONE') return `생성 완료 · ${r.generation_ms != null ? (r.generation_ms / 1000).toFixed(1) : '-'}초 · 분석 모델 ${r.model_version ?? model} · 템플릿 ${r.template_version ?? '-'}`
  if (r.status === 'FAILED') return `만들지 못했습니다 · ${r.fail_reason?.message ?? ''}`
  return r.status === 'GENERATING' ? '보고서를 만드는 중입니다' : '보고서 생성을 기다리는 중입니다'
}
