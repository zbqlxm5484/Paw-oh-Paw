// 예시 회차의 보행 수치를 시연 회차 값으로 채운다. prototype/proto_app/real.py 그대로.
// 시연 회차(demo_sessions.json)는 시연 데이터(fixture.json 의 sessions)로 온다. 회사 데이터는 없음.
import { db } from '../store/db'
import type { Metrics, RealSession, Result } from '../store/types'
import { pyround, pysum, sorted } from './pyfmt'

export const MIN_CYCLES = 4
// (화면 이름, 수치 코드, 앞/뒤, 단위). 디딤 비율·걸음 길이·발 높이는 엔진 v0 정의(몸통 = T13~장골능 길이 기준)
export const ROWS: [string, string, string, string, string][] = [
  ['뒷다리', '무릎 가동 범위', 'rom_stifle', 'H', '°'], ['뒷다리', '고관절 가동 범위', 'rom_hip', 'H', '°'],
  ['뒷다리', '뒷발목 가동 범위', 'rom_tarsus', 'H', '°'], ['뒷다리', '걸음 길이(등 길이 대비)', 'stride_length', 'H', '%'],
  ['뒷다리', '입각기 비율', 'stance_ratio', 'H', '%'], ['뒷다리', '발 들림 높이(등 길이 대비)', 'paw_lift', 'H', '%'],
  ['앞다리', '어깨 가동 범위', 'rom_shoulder', 'F', '°'], ['앞다리', '팔꿈치 가동 범위', 'rom_elbow', 'F', '°'],
  ['앞다리', '앞발목 가동 범위', 'rom_carpus', 'F', '°'], ['앞다리', '걸음 길이(등 길이 대비)', 'stride_length', 'F', '%'],
  ['앞다리', '입각기 비율', 'stance_ratio', 'F', '%'], ['앞다리', '발 들림 높이(등 길이 대비)', 'paw_lift', 'F', '%'],
]
export const SYM_CODES: [string, string][] = [['rom_stifle', 'H'], ['rom_hip', 'H'], ['rom_elbow', 'F'], ['stride_length', 'H'], ['stance_ratio', 'H']]

/** 양쪽 다리가 다 찍히고 걸음 4개 이상인 회차만 (fixture 는 이미 거른 목록) */
export function sessions(): RealSession[] {
  return db.sessions.filter((s) => s.passes.L && s.passes.R && s.cycles >= MIN_CYCLES)
}

/** '출처:촬영 묶음' → 실측 회차 */
export function session(src: string): RealSession | null {
  const sid = src ? src.slice(src.indexOf(':') + 1) : ''
  return sessions().find((s) => s.id === sid) ?? null
}

const SOURCE: Record<string, string> = { jenny: '제니', wowwow: '와우와우', aihub: 'AI-Hub' }
export function source_name(s: RealSession): string {
  return (SOURCE[s.source] ?? s.source) + ` ${s.id}`
}

export function met(m: Metrics | null | undefined, code: string, leg: string): number | null {
  const v = (m?.[leg] || {})[code]
  return v === undefined ? null : v
}

/** 좌우 차이 비율(%) = |왼 − 오| ÷ 평균 */
export function si(left: number | null, right: number | null): number | null {
  if (left == null || right == null || left + right === 0) return null
  return (Math.abs(left - right) / ((left + right) / 2)) * 100
}

function pairOf(m: Metrics, code: string, fh: string): [number, number] {
  return [pyround(met(m, code, 'L' + fh) || 0), pyround(met(m, code, 'R' + fh) || 0)]
}

function symOf(m: Metrics): number {
  const sis = SYM_CODES.map(([c, fh]) => si(met(m, c, 'L' + fh), met(m, c, 'R' + fh))).filter((x): x is number => x !== null)
  return sis.length ? Math.max(0, pyround(100 - pysum(sis) / sis.length)) : 0
}

/** 실측 회차 s 의 수치로 결과 r 의 수치 칸을 채운다(상태·날짜·측정자는 그대로). */
export function apply(r: Result, s: RealSession): void {
  applyMetrics(r, s.metrics)
  r.src = `${s.source}:${s.id}`
  const used = s.passes.L + s.passes.R
  r.ps = [s.video_names.length, used]
  r.ex = s.video_names.length > used ? [['방향·관절점 부족', s.video_names.length - used]] : []
}

/** 다리별 수치 m 으로 결과의 요약 칸(관절 3개·걸음 길이·대칭 지수·무릎 가동)을 채운다. 백엔드 결과도 같은 계산을 쓴다 */
export function applyMetrics(r: Result, m: Metrics): void {
  r.m = m
  r.j = [['무릎', ...pairOf(m, 'rom_stifle', 'H')], ['고관절', ...pairOf(m, 'rom_hip', 'H')], ['팔꿈치', ...pairOf(m, 'rom_elbow', 'F')]]
  ;[r.sL, r.sR] = pairOf(m, 'stride_length', 'H')
  r.sym = symOf(m)
  r.rom = pyround((r.j[0][1] + r.j[0][2]) / 2)
}

/** 실패가 아닌 예시 회차에 실측 회차를 차례로 붙인다(오래된 회차부터). */
/** 같은 날·같은 시각 회차의 순서: id 의 앞글자, 그다음 숫자 크기(real.py _id_key). 문자열로 견주면 res998 이 res1000 뒤로 간다 */
function id_key(rid: string): [string, number, string] {
  const m = /^(\D*)(\d*)/.exec(rid)!
  return [m[1], Number(m[2] || 0), rid]
}

export function fill(results: Result[]): void {
  const ss = sessions()
  if (!ss.length) return
  let i = 0
  for (const r of sorted(results, (r) => [r.day, r.time, ...id_key(r.id)])) {
    if (r.st !== 'fail') {
      apply(r, ss[i % ss.length])
      i += 1
    }
  }
}

export interface Row {
  n: string
  leg: string
  sec?: string
  na?: boolean
  reason?: string
  l?: number
  r?: number
  u?: string
}

/** 회차 수치 표. 한쪽이 없으면 비교 불가 */
export function rows(r: Result): Row[] {
  const out: Row[] = []
  let last: string | null = null
  for (const [sec, name, code, fh, unit] of ROWS) {
    const left = met(r.m, code, 'L' + fh)
    const right = met(r.m, code, 'R' + fh)
    const row: Row = { n: name, leg: sec }
    if (sec !== last) {
      row.sec = sec
      last = sec
    }
    if (left == null || right == null) Object.assign(row, { na: true, reason: '이 방향 영상에서 해당 관절을 잴 수 없었습니다' })
    else Object.assign(row, { l: pyround(left), r: pyround(right), u: unit })
    out.push(row)
  }
  return out
}

// ── 시연용 극단 합성(11-02): 대표 반려견 한 마리는 오른쪽 뒷다리를 크게 덜 쓰다가 회차마다 나아지는 이야기 ──
export const _HEALTHY: Record<string, Record<string, number>> = {
  F: { rom_shoulder: 32.0, rom_elbow: 48.0, rom_carpus: 68.0, stance_ratio: 60.0, stride_length: 230.0, paw_lift: 24.0 },
  H: { rom_hip: 28.0, rom_stifle: 53.0, rom_tarsus: 52.0, stance_ratio: 58.0, stride_length: 235.0, paw_lift: 22.0 },
}

/** f = 오른쪽 뒷다리 가동 범위가 왼쪽의 몇 배인지(0.3 = 거의 안 굽힘, 1 = 같음). */
export function limp_metrics(f: number): Metrics {
  const m: Metrics = {}
  for (const leg of ['LF', 'RF', 'LH', 'RH']) m[leg] = { ..._HEALTHY[leg[1]] }
  for (const code of ['rom_hip', 'rom_stifle', 'rom_tarsus', 'paw_lift']) m.RH[code] = pyround(m.LH[code] * f, 1)
  m.RH.stride_length = pyround(m.LH.stride_length * (0.55 + 0.45 * f), 1)
  m.RH.stance_ratio = pyround(m.LH.stance_ratio * (0.7 + 0.3 * f), 1) // 덜 디딘다
  m.LH.stance_ratio = pyround(m.LH.stance_ratio * (1.12 - 0.12 * f), 1) // 반대쪽이 더 오래 버틴다
  for (const leg of ['LF', 'RF']) m[leg].stance_ratio = pyround(m[leg].stance_ratio * (1.08 - 0.08 * f), 1) // 앞다리로 몸무게를 옮긴다
  return m
}

export function showcase(results: Result[], dog_id: string, start = 0.22, end = 0.6): void {
  const rs = sorted(results.filter((r) => r.dog === dog_id && r.st !== 'fail'), (r) => [r.day, r.time, r.id])
  rs.forEach((r, i) => {
    const f = start + (end - start) * (i / Math.max(1, rs.length - 1))
    const m = limp_metrics(f)
    r.m = m
    r.src = '' // src 를 비우면 무릎 곡선은 시연 걸음(gait_demo.json, 같은 절뚝임)을 쓴다
    r.j = [['무릎', ...pairOf(m, 'rom_stifle', 'H')], ['고관절', ...pairOf(m, 'rom_hip', 'H')], ['팔꿈치', ...pairOf(m, 'rom_elbow', 'F')]]
    ;[r.sL, r.sR] = pairOf(m, 'stride_length', 'H')
    r.sym = symOf(m)
    r.rom = pyround((r.j[0][1] + r.j[0][2]) / 2)
  })
}
