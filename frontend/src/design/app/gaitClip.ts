// 3D 보행 보기의 '측정 걸음' 곡선을 이 회차의 실제 관절 각도(GET /shots/{id}/angles)로 만든다.
// 웹(web/src/views/gaitClip.ts)에 같은 코드가 있다(두 프로젝트는 코드를 공유하지 않는다). 고치면 둘 다.
//
// 3D 장면(Gait3dMount)이 먹는 형식은 견본 gait_demo.json 과 같다: 다리(LF·RF·LH·RH)마다 관절 이름(어깨·팔꿈치·앞발목 / 고관절·무릎·뒷발목)별
// 한 걸음을 50칸으로 나눈 각도(°). 각도 API 는 걸음 경계 없이 프레임별 각도만 주므로, 여기서 걸음을 자른다:
//   빈 프레임 메우기(짧은 구멍만) → 살짝 매끈하게 → 자기상관으로 한 걸음 길이 → 그 길이 간격의 봉우리로 걸음 자르기 → 걸음마다 50칸으로 늘이고 평균.
// 각도 API 는 카메라 쪽 다리만 준다. 왼쪽면·오른쪽면 촬영을 하나씩 골라 좌우를 채우고, 한쪽 촬영이 없으면 반대쪽 곡선을 그대로 비춰 쓴다(그 사실을 note 에 적는다).
import type { AnglesOut, GaitType, JointCode } from '../../api/types'

export const N_PHASE = 50
export type GaitClip = { legs: Record<string, { strides?: number; joint: Record<string, number[]> }>; [k: string]: unknown }

/** 각도 API 관절 코드 → 3D 장면(engine/angles.py) 관절 이름 */
export const JOINT_NAME: Record<JointCode, string> = { shoulder: '어깨', elbow: '팔꿈치', carpus: '앞발목', hip: '고관절', stifle: '무릎', tarsus: '뒷발목' }
const FRONT: JointCode[] = ['shoulder', 'elbow', 'carpus']
const HIND: JointCode[] = ['hip', 'stifle', 'tarsus']
export const GAIT_KO: Record<string, string> = { WALK: '평보', TROT: '속보', PACE: '측대보', OTHER: '보행 유형 미판별' }

type Series = (number | null)[]

/** 안쪽의 짧은 빈 구간(maxGap 프레임 이하)만 앞뒤 값으로 잇는다. 앞뒤 끝의 빈 값·긴 구멍은 그대로 둔다 */
export function fillGaps(s: Series, maxGap: number): Series {
  const out = s.slice()
  let i = 0
  while (i < out.length) {
    if (out[i] != null) { i++; continue }
    let j = i
    while (j < out.length && out[j] == null) j++
    const a = out[i - 1], b = out[j]
    if (i > 0 && j < out.length && a != null && b != null && j - i <= maxGap) {
      for (let k = i; k < j; k++) out[k] = a + ((b - a) * (k - i + 1)) / (j - i + 1)
    }
    i = j
  }
  return out
}

/** 가운데 이동 평균(창 안의 값 있는 프레임만). 빈 프레임은 빈 채로 */
export function smooth(s: Series, half: number): Series {
  if (half <= 0) return s.slice()
  return s.map((v, i) => {
    if (v == null) return null
    let sum = 0, n = 0
    for (let k = Math.max(0, i - half); k <= Math.min(s.length - 1, i + half); k++) { const x = s[k]; if (x != null) { sum += x; n++ } }
    return sum / n
  })
}

/** 자기상관이 가장 큰 간격(프레임) = 한 걸음 길이. 두 배 간격을 잘못 고르지 않게, 최댓값의 80% 이상인 첫 봉우리를 쓴다 */
export function estimatePeriod(s: Series, lo: number, hi: number): { period: number; r: number } | null {
  const vals = s.filter((v): v is number => v != null)
  if (vals.length < lo * 2) return null
  const m = vals.reduce((a, b) => a + b, 0) / vals.length
  const rs: number[] = []
  const top = Math.min(hi, Math.floor(s.length / 1.5))
  for (let lag = 0; lag <= top; lag++) {
    if (lag < lo) { rs.push(-Infinity); continue }
    let num = 0, da = 0, db = 0, n = 0
    for (let i = 0; i + lag < s.length; i++) {
      const a = s[i], b = s[i + lag]
      if (a == null || b == null) continue
      num += (a - m) * (b - m); da += (a - m) ** 2; db += (b - m) ** 2; n++
    }
    rs.push(n >= lo && da > 0 && db > 0 ? num / Math.sqrt(da * db) : -Infinity)
  }
  let best = -Infinity
  for (const r of rs) if (r > best) best = r
  if (!(best > 0.2)) return null
  for (let lag = lo; lag <= top; lag++) {
    const r = rs[lag]
    if (r >= 0.8 * best && r >= (rs[lag - 1] ?? -Infinity) && r >= (rs[lag + 1] ?? -Infinity)) return { period: lag, r }
  }
  return null
}

/** 한 걸음 길이 간격으로 찾은 봉우리 사이 = 걸음. 사이에 빈 프레임이 있거나 길이가 한 걸음의 0.7~1.3배를 벗어나면 버린다 */
export function strideBounds(s: Series, period: number): [number, number][] {
  const half = Math.max(1, Math.round(period * 0.4))
  const peaks: number[] = []
  for (let i = 0; i < s.length; i++) {
    const v = s[i]
    if (v == null) continue
    // 창 안에서 가장 크고(같으면 앞의 것), 양옆에 값이 하나 이상 있어야 한다(끝에서 오르던 중이면 봉우리가 아니다)
    let top = true, left = false, right = false
    for (let k = Math.max(0, i - half); k <= Math.min(s.length - 1, i + half) && top; k++) {
      const x = s[k]
      if (k === i || x == null) continue
      if (x > v || (x === v && k < i)) top = false
      if (k < i) left = true
      else right = true
    }
    if (top && left && right && (!peaks.length || i - peaks[peaks.length - 1] >= period * 0.6)) peaks.push(i)
  }
  const out: [number, number][] = []
  for (let k = 1; k < peaks.length; k++) {
    const a = peaks[k - 1], b = peaks[k]
    if (b - a < period * 0.7 || b - a > period * 1.3) continue
    out.push([a, b])
  }
  return out
}

/** s[a..b] 를 n 칸(0 ≤ 위치 < 1)으로 늘인다. 빈 값이 끼어 있으면 null */
export function resample(s: Series, a: number, b: number, n = N_PHASE): number[] | null {
  const out: number[] = []
  for (let k = 0; k < n; k++) {
    const x = a + ((b - a) * k) / n, i = Math.floor(x), f = x - i
    const p = s[i], q = s[Math.min(b, i + 1)]
    if (p == null || q == null) return null
    out.push(p + (q - p) * f)
  }
  return out
}

/** 한 다리(같은 통과의 세 관절)를 걸음으로 잘라 관절별 50칸 곡선 목록을 돌려준다. 세 관절은 같은 걸음 경계를 쓴다 */
export function legStrides(joints: Record<string, Series>, fps: number): Record<string, number[][]> {
  const f = fps > 0 ? fps : 30
  const prep: Record<string, Series> = {}
  for (const [k, s] of Object.entries(joints)) prep[k] = smooth(fillGaps(s ?? [], Math.max(1, Math.round(f * 0.1))), Math.max(0, Math.round(f / 60)))
  // 걸음 길이를 가장 또렷하게 보이는 관절을 기준으로(한 걸음 0.25~1.2초)
  let ref: { k: string; period: number; r: number } | null = null
  for (const [k, s] of Object.entries(prep)) {
    const p = estimatePeriod(s, Math.max(3, Math.round(f * 0.25)), Math.round(f * 1.2))
    if (p && (!ref || p.r > ref.r)) ref = { k, ...p }
  }
  const out: Record<string, number[][]> = {}
  if (!ref) return out
  const bounds = strideBounds(prep[ref.k], ref.period)
  for (const [k, s] of Object.entries(prep)) {
    const cs = bounds.map(([a, b]) => resample(s, a, b)).filter((c): c is number[] => !!c)
    if (cs.length) out[k] = cs
  }
  return out
}

const mean = (cs: number[][]): number[] => cs[0].map((_, i) => Math.round((cs.reduce((s, c) => s + c[i], 0) / cs.length) * 100) / 100)

export interface ClipInfo {
  /** 곡선을 만든 보행 유형 */
  gait: string
  /** 실제 각도가 있는 쪽(L·R) */
  sides: ('L' | 'R')[]
  /** 그 쪽 각도가 하나도 없어(촬영 없음) 반대쪽 곡선을 통째로 비춰 쓴 쪽 */
  mirrored: ('L' | 'R')[]
  /** 그 쪽 각도는 있지만 걸음을 못 자른 다리·관절이 있어 그것만 반대쪽 곡선을 쓴 쪽 */
  borrowed: ('L' | 'R')[]
  /** 평균에 쓴 걸음 수(다리별 가장 많은 관절 기준) */
  strides: number
  shots: number
  passes: number
}

/** 각도 응답들(같은 회차의 촬영들) → 3D 걸음 곡선. 고른 보행 유형의 유효 통과만 쓴다. 한 다리도 못 만들면 null */
export function clipFromAngles(resps: AnglesOut[], gait: string): { clip: GaitClip; info: ClipInfo } | null {
  const acc: Record<string, Record<string, number[][]>> = {}
  let passes = 0
  const shots = new Set<string>()
  for (const r of resps) {
    for (const p of r.passes) {
      if (p.gait_type !== gait) continue
      const side = p.camera_side === 'LEFT' ? 'L' : p.camera_side === 'RIGHT' ? 'R' : null
      if (!side) continue
      let used = false
      for (const [part, codes] of [['F', FRONT], ['H', HIND]] as const) {
        const js: Record<string, Series> = {}
        for (const c of codes) js[JOINT_NAME[c]] = p.angles?.[c] ?? []
        const st = legStrides(js, r.fps)
        for (const [j, cs] of Object.entries(st)) { ((acc[side + part] ||= {})[j] ||= []).push(...cs); used = true }
      }
      if (used) { passes++; shots.add(r.shot_id) }
    }
  }
  const legs: GaitClip['legs'] = {}
  let strides = 0
  for (const [code, js] of Object.entries(acc)) {
    const joint: Record<string, number[]> = {}
    let n = 0
    for (const [j, cs] of Object.entries(js)) { joint[j] = mean(cs); n = Math.max(n, cs.length) }
    legs[code] = { strides: n, joint }
    strides += n
  }
  const has = (s: 'L' | 'R') => !!(legs[s + 'F'] || legs[s + 'H'])
  const sides = (['L', 'R'] as const).filter(has)
  if (!sides.length) return null
  const mirrored: ('L' | 'R')[] = [], borrowed: ('L' | 'R')[] = []
  for (const s of ['L', 'R'] as const) {
    const o = s === 'L' ? 'R' : 'L'
    let copied = false
    for (const part of ['F', 'H']) {
      const mine = legs[s + part], other = legs[o + part]
      if (!other) continue
      if (!mine) { legs[s + part] = { strides: 0, joint: { ...other.joint } }; copied = true; continue }
      // 한 관절만 빠졌으면 그 관절만 반대쪽에서
      for (const [j, c] of Object.entries(other.joint)) if (!mine.joint[j]) { mine.joint[j] = c; copied = true }
    }
    if (copied) (sides.includes(s) ? borrowed : mirrored).push(s)
  }
  const info: ClipInfo = { gait, sides: [...sides], mirrored, borrowed, strides, shots: shots.size, passes }
  const clip: GaitClip = {
    source: 'GET /shots/{id}/angles', label: '이 회차 실제 측정', n_phase: N_PHASE,
    hind_after_front: { L: 0.5, R: 0.5 }, legs,
  }
  return { clip, info }
}

/** 회차 상세의 촬영 목록 한 줄(필요한 필드만) */
export interface ShotLite {
  id: string
  status: string
  validity?: string | null
  passes?: { camera_side: string; gait_type: string; is_valid: boolean }[]
}

/** 각도를 받을 촬영 고르기: 보행 유형(prefer 에 유효 통과가 있으면 그것, 없으면 유효 통과가 가장 많은 유형)을 정하고,
 *  쪽마다 그 유형의 유효 통과가 많은 촬영부터 max 개 */
export function pickShots(shots: ShotLite[], prefer: string | null, max = 2): { gait: string; L: string[]; R: string[] } | null {
  const ok = shots.filter((s) => s.status === 'DONE' && s.validity !== 'INVALID')
  const count: Record<string, number> = {}
  for (const s of ok) for (const p of s.passes ?? []) if (p.is_valid) count[p.gait_type] = (count[p.gait_type] ?? 0) + 1
  const gaits = Object.entries(count).sort((a, b) => b[1] - a[1])
  // 통과 정보가 없는 옛 응답이면 유형을 모른 채 DONE 촬영을 다 후보로
  const gait = prefer && count[prefer] ? prefer : gaits[0]?.[0] ?? prefer
  if (!gait) return null
  const of = (side: string) => ok
    .map((s) => ({ id: s.id, n: s.passes ? s.passes.filter((p) => p.is_valid && p.camera_side === side && p.gait_type === gait).length : -1 }))
    .filter((x) => x.n !== 0)
    .sort((a, b) => b.n - a.n)
    .slice(0, max)
    .map((x) => x.id)
  const L = of('LEFT'), R = of('RIGHT')
  if (!L.length && !R.length) return null
  // 통과 정보가 없어 양쪽 후보가 같으면 한 번만
  return { gait, L, R: R.filter((id) => !L.includes(id)) }
}

export interface GaitLoad {
  clip: GaitClip | null
  real: boolean
  /** 화면에 작게 붙이는 출처 표시 */
  note: string
}

export const DEMO_NOTE = '견본 걸음입니다(이 회차의 각도를 불러오지 못함)'

/** 출처 표시 문구 */
export function realNote(info: ClipInfo): string {
  const side = (s: 'L' | 'R') => (s === 'L' ? '왼쪽' : '오른쪽')
  let t = `이 회차 실제 측정 · ${GAIT_KO[info.gait] ?? info.gait} ${info.strides}걸음 평균`
  if (info.mirrored.length) t += ` · ${info.mirrored.map(side).join('·')} 다리는 촬영이 없어 반대쪽 값을 비춰 그림`
  else if (info.borrowed.length) t += ' · 걸음을 못 자른 관절 일부는 반대쪽 값으로 채움'
  return t
}

/** 회차 id → 3D 걸음 곡선. 실제 각도를 못 만들면 견본(gait_demo.json)으로, 견본도 못 받으면 clip null(일반 걸음만) */
export async function loadSessionGait(
  deps: { session: (id: string) => Promise<{ shots: ShotLite[] }>; angles: (shotId: string) => Promise<AnglesOut>; demo: () => Promise<GaitClip | null> },
  sessionId: string | null | undefined,
  prefer: GaitType | string | null,
): Promise<GaitLoad> {
  if (sessionId) {
    try {
      const s = await deps.session(sessionId)
      const pick = pickShots(s.shots ?? [], prefer)
      if (pick) {
        const ids = [...pick.L, ...pick.R]
        const resps = (await Promise.all(ids.map((id) => deps.angles(id).catch(() => null)))).filter((r): r is AnglesOut => !!r && Array.isArray(r.passes))
        const got = clipFromAngles(resps, pick.gait)
        if (got) return { clip: got.clip, real: true, note: realNote(got.info) }
      }
    } catch {
      /* 견본으로 */
    }
  }
  const demo = await deps.demo().catch(() => null)
  return { clip: demo, real: false, note: demo ? DEMO_NOTE : '걸음 곡선을 불러오지 못했습니다(일반 걸음만)' }
}
