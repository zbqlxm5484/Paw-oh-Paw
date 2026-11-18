/// <reference types="vite/client" />
// 화면에 넣을 값 계산 (디자인의 renderVals를 Python으로 옮김). prototype/proto_app/views.py 그대로.
// 함수 이름·돌려주는 키는 파이썬과 같다. 숫자 서식은 pyfmt(파이썬 round·f-string 흉내).
import dogSmall from '../../public/static/assets/dog/dog_small.svg?raw'
import dogMedium from '../../public/static/assets/dog/dog_medium.svg?raw'
import dogLarge from '../../public/static/assets/dog/dog_large.svg?raw'
import gaitDemo from '../../public/static/assets/dog3d/gait_demo.json'
import gaitRef from '../../public/static/assets/dog3d/gait_ref_plos.json'
import {
  CHANGE_DAYS,
  IMG_KIND,
  LIMB,
  MEMO_CAT,
  NOTE_CAT,
  PAGE_SIZE,
  SEX,
  SITE,
  SIZE,
  SOAP,
  ST,
  STAGE,
  SYM_CHANGE,
  VITAL_REF,
  WEIGHT_CHANGE,
  auto_size,
} from '../config'
import { activeJobs, dogOf, isoToday, resultOf } from '../store/db'
import type { Account, Dog, History, Job, Result, Vital } from '../store/types'
import { floordiv, fmt, fmt_signed, g, jround, maxBy, minBy, pyfloat, pyint, pymod, pyround, pystr, pysum, replaceN, sorted } from './pyfmt'
import * as real from './real'
import type { Row } from './real'

export { jround }

// ── 날짜(YYYY-MM-DD) ──
const DAY = 86400000
function ord(iso: string): number {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return Math.round(Date.UTC(y, m - 1, d) / DAY)
}
function fromOrd(n: number): string {
  return new Date(n * DAY).toISOString().slice(0, 10)
}
const cp = (s: string) => [...s] // 파이썬 문자열 인덱스 = 코드 포인트
const hasM = (r: Result) => !!r.m && Object.keys(r.m).length > 0 // 파이썬 `if r.m`

export function short(d: string): string {
  return d.replaceAll('월 ', '.').replaceAll('일', '')
}

export function fmt_date(iso: string): string {
  const p = (iso || '').split('-')
  return p.length === 3 ? `${p[0]}년 ${Number(p[1])}월 ${Number(p[2])}일` : iso
}

export function desc(d: Dog): string {
  const parts = [d.breed || '견종 미입력', d.birth ? `${d.birth}년생` : null, d.kg ? `${d.kg}kg` : null]
  return parts.filter((p) => p).join(', ')
}

export function st_chip(st: string): { st: string; bg: string; c: string } {
  const [label, bg, c] = ST[st]
  return { st: label, bg, c }
}

export function valid(acct: Account, dog_id: string): Result[] {
  return acct.results.filter((r) => r.dog === dog_id && r.st !== 'fail')
}

/** 대칭 점수가 있는 회차(유효하고 서버가 점수를 낸 것). 점수 추이·직전 대비에 쓴다 */
export function scored(acct: Account, dog_id: string): Result[] {
  return valid(acct, dog_id).filter((r) => !r.nosym)
}

/** 대칭 점수가 없을 때(서버 null) 붙이는 안내 */
export const NO_SYM_HINT = '한쪽 면만 분석돼 좌우를 비교할 수 없습니다. 왼쪽·오른쪽 면을 모두 찍어야 대칭 점수가 나옵니다'

/** 대칭 점수 글자: 실패·점수 없음은 — */
export function symText(r: Result): string {
  return r.st === 'fail' || r.nosym ? '—' : `${r.sym}점`
}

/** 회차 체중 문구. 그날 체중을 안 적은 회차(weight_kg null → '-')는 '-kg' 대신 측정 불가 표기 */
export const wkg = (w: string): string => (w && w !== '-' ? `${w}kg` : '—')

export function sess_no(acct: Account, r: Result): number {
  const all_ = acct.results.filter((x) => x.dog === r.dog)
  return all_.length - all_.findIndex((x) => x.id === r.id)
}

/** "오후 2:55" (회차 시각 "14:55") */
function ampm(hm: string): string {
  const m = /^(\d{1,2}):(\d{2})/.exec(hm || '')
  if (!m) return ''
  const h = Number(m[1])
  return `${h < 12 ? '오전' : '오후'} ${h % 12 === 0 ? 12 : h % 12}:${m[2]}`
}

/** 다른 회차를 가리킬 때의 표기: "2회차, 11월 10일". 이번 회차(cur)와 같은 날이면 시각까지 "2회차, 11월 10일 오전 9:38" */
export function sess_label(acct: Account, x: Result, cur?: Result): string {
  const same = !!cur && cur.id !== x.id && !!x.day && x.day === cur.day
  const t = same ? ampm(x.time) : ''
  return `${sess_no(acct, x)}회차, ${x.date}${t ? ' ' + t : ''}`
}

export function base_of(acct: Account, d: Dog): string | null {
  if (d.base && acct.results.some((r) => r.id === d.base && r.st !== 'fail')) return d.base
  const v = valid(acct, d.id)
  return v.length ? v[v.length - 1].id : null
}

export function delta(a: number, b: number | null | undefined, unit: string): string {
  if (b == null) return '첫 측정'
  const d = a - b
  if (d > 0) return `직전 대비 +${d}${unit}`
  if (d < 0) return `직전 대비 −${-d}${unit}`
  return '직전과 같음'
}

export function avatar(on: boolean) {
  return {
    ring: on ? '0 0 0 3px #FAF9F6,0 0 0 6px #D2601A' : 'none',
    av: on ? '#FCEEE3' : '#EEEAE4', avc: on ? '#A8481A' : '#5B6472',
    nc: on ? '#1B2433' : '#5B6472', nw: on ? 700 : 500,
  }
}

export function seg(items: [string, string][], cur: string) {
  return items.map(([key, label]) => {
    const on = cur === key
    return { key, label, bg: on ? '#fff' : 'transparent', c: on ? '#1B2433' : '#5B6472', sh: on ? '0 1px 3px rgba(27,36,51,.12)' : 'none' }
  })
}

// ── 회차 수치 ──
export function mrows(r: Result, gait: string): Row[] {
  if (hasM(r)) return real.rows(r) // 실측 수치(real.py). 평보·속보 구분은 영상에 없어 같은 값
  const f = gait === 'walk' ? 0.86 : 1
  const v = (x: number) => jround(x * f)
  return [
    { sec: '뒷다리', n: '무릎 가동 범위', l: v(r.j[0][1]), r: v(r.j[0][2]), u: '°', leg: '뒷다리' },
    { n: '고관절 가동 범위', l: v(r.j[1][1]), r: v(r.j[1][2]), u: '°', leg: '뒷다리' },
    { n: '걸음 길이', l: v(r.sL * 1.5), r: v(r.sR * 1.5), u: '%', leg: '뒷다리' },
    { n: '입각기 비율', l: 61, r: 61 - jround((r.sL - r.sR) / 2), u: '%', leg: '뒷다리' },
    { sec: '앞다리', n: '팔꿈치 가동 범위', l: v(r.j[2][1]), r: v(r.j[2][2]), u: '°', leg: '앞다리' },
    { n: '발 들림 높이', na: true, reason: '반대쪽 다리가 가려졌습니다', leg: '앞다리' },
  ]
}

export type Ranked = Row & { l: number; r: number; u: string; df: number; si: number }

export function _rank(rows: Row[]): Ranked[] {
  const out: Ranked[] = []
  for (const x of rows) {
    if (x.na) continue
    const df = Math.abs(x.l! - x.r!)
    out.push({ ...(x as Ranked), df, si: (df / ((x.l! + x.r!) / 2)) * 100 })
  }
  return sorted(out, (x) => -x.si)
}

function _median(vals: (number | null | undefined)[], dflt: number): number {
  const v = (vals.filter((x) => x) as number[]).sort((a, b) => a - b)
  return v.length ? v[floordiv(v.length, 2)] : dflt
}

// 3D 움직임 기준: 시연 회차들의 관절별 가동 범위 중앙값(°). 두 다리 모두 이보다 작으면 둘 다 덜 움직인다
const _JOINT_CODES: Record<string, string> = { 어깨: 'rom_shoulder', 팔꿈치: 'rom_elbow', 앞발목: 'rom_carpus', 고관절: 'rom_hip', 무릎: 'rom_stifle', 뒷발목: 'rom_tarsus' }
export const ROM_REF: Record<string, number> = Object.fromEntries(
  Object.entries(_JOINT_CODES).map(([j, c]) => [
    j,
    pyround(
      _median(
        real.sessions().flatMap((s) => ['LF', 'RF', 'LH', 'RH'].map((leg) => real.met(s.metrics, c, leg))),
        real._HEALTHY[['rom_shoulder', 'rom_elbow', 'rom_carpus'].includes(c) ? 'F' : 'H'][c],
      ),
      1,
    ),
  ]),
)
export const MEDIAN_SPEED = _median(real.sessions().map((s) => s.walk_speed), 1)

export const TEMPLATE_STANCE = 60.0 // 모양 틀(공개 논문 속보 평균 곡선)의 입각기 비율 가정(%)

/** 모양 틀 곡선을 이 회차 수치에 맞춘다: 굽힘 폭 = 가동 범위(°), 디딤 구간 길이 = 입각기 비율(%).
 *  입각기 비율이 틀보다 길면 디딤 구간(곡선 앞쪽)을 늘리고 나머지를 줄인다. 값이 없으면 그 항목은 틀 그대로. */
export function fit_curve(base: number[], rom: number | null, stance: number | null): number[] {
  const n = base.length
  const mean = pysum(base) / base.length
  const amp = Math.max(...base) - Math.min(...base) || 1
  const k = rom ? rom / amp : 1
  const c = base.map((v) => mean + (v - mean) * k)
  if (!stance) return c.map((v) => pyround(v, 1))
  const a = TEMPLATE_STANCE / 100
  const b = Math.min(0.8, Math.max(0.35, stance / 100))
  const out: number[] = []
  for (let i = 0; i < n; i++) {
    const p = i / n
    const q = p < b ? (p / b) * a : a + ((p - b) / (1 - b)) * (1 - a) // 이 회차의 걸음 위치 → 틀의 걸음 위치
    const x = q * n
    const j = pymod(Math.trunc(x), n)
    const f = x - Math.trunc(x)
    out.push(pyround(c[j] * (1 - f) + c[(j + 1) % n] * f, 1))
  }
  return out
}

type Gait = { legs: Record<string, { joint: Record<string, number[]> }> }
type Ref = { gaits: Record<string, Record<string, { dogs: number; mean: number[]; min: number[]; max: number[] }>> }

/** 보고서 "뒷무릎 각도/보행 주기" 그래프. x = 한 걸음 0~100%, y = 무릎 각도(°).
 *  회차에 실측 곡선이 붙어 있으면 그 곡선, 없으면 공개 논문 속보 평균 모양을 이 회차의 다리별 무릎 가동 범위·입각기 비율에 맞춰 만든다. */
export function knee_chart(r: Result) {
  const s = real.session(r.src)
  let L: number[], R: number[], label: string
  if (s && 'LH' in s.knee_curve && 'RH' in s.knee_curve) {
    L = s.knee_curve.LH
    R = s.knee_curve.RH
    label = s.source === 'aihub' ? `AI-Hub 라벨 관절점(${real.source_name(s)}) 근사 곡선` : `실측 영상 ${s.video_names.length}개(${real.source_name(s)}) 걸음 평균`
  } else {
    const base = (gaitDemo as unknown as Gait).legs.LH.joint['무릎'] // 틀은 덜 쓰지 않는 쪽 곡선
    ;[L, R] = ['LH', 'RH'].map((leg) => fit_curve(base, real.met(r.m, 'rom_stifle', leg), real.met(r.m, 'stance_ratio', leg)))
    label = '이 회차 무릎 가동 범위·입각기 비율로 만든 합성 곡선(모양은 공개 논문 속보 평균)'
  }
  // 정상 참고 범위: 공개 데이터 건강한 대형견 6마리 속보 무릎(tools/build_plos_reference.py)
  const ref = (gaitRef as unknown as Ref).gaits.trot['무릎']
  const allv = [...L, ...R, ...ref.min, ...ref.max]
  const lo = Math.floor(Math.min(...allv) / 10) * 10
  const hi = Math.ceil(Math.max(...allv) / 10) * 10
  const [x0, x1, y0, y1] = [44, 300, 12, 120]
  const y = (v: number) => y1 - ((v - lo) / (hi - lo)) * (y1 - y0)
  const pt = (c: number[]) => c.map((v, i) => `${fmt(x0 + ((x1 - x0) * i) / c.length, 1)},${fmt(y(v), 1)}`)
  const line = (c: number[]) => pt(c).join(' ') // 칸 i = 한 걸음의 i/n. 마지막 칸은 100% 바로 앞
  const mid = floordiv(lo + hi, 2)
  return {
    L: line(L), R: line(R), ref_band: [...pt(ref.max), ...pt(ref.min).reverse()].join(' '), ref_mean: line(ref.mean),
    ref_src: `건강한 대형견 ${ref.dogs}마리 속보 범위(Catavitello 외 2015, PLOS ONE, CC BY 4.0)`,
    y: [hi, mid, lo].map((v) => ({ y: pyround(y(v), 1), t: `${v}°` })),
    x: [0, 50, 100].map((p) => ({ x: x0 + ((x1 - x0) * p) / 100, t: `${p}` })), // 눈금 글자에 % 를 빼고 축 이름에 단위(보고서 검사가 "100%" 를 단정 표현으로 본다)
    x0, x1, src: label,
  }
}

/** 회차 결과 화면(rd)과 보고서(rp)에 쓰는 값. */
export function result_view(acct: Account, r: Result, gait = 'trot', home = false) {
  const d = dogOf(acct, r.dog)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rd: Record<string, any> = {
    name: d ? d.name : '-', desc: d ? desc(d) : '', when: `${r.date}, ${sess_no(acct, r)}회차, 체중 ${wkg(r.w)}`,
    ...st_chip(r.st), fail: r.st === 'fail', ok: r.st !== 'fail', part: r.st === 'part', id: r.id, dog: r.dog,
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let rp: Record<string, any> = {}
  if (r.st === 'fail') return { rd, rp }
  const vv = valid(acct, r.dog)
  const idx = vv.findIndex((x) => x.id === r.id)
  const prev = idx + 1 < vv.length ? vv[idx + 1] : null
  const prevS = r.nosym ? null : vv.slice(idx + 1).find((x) => !x.nosym) ?? null // 점수 비교는 점수 있는 직전 회차와
  const rows = mrows(r, home ? 'trot' : gait)
  const rows_t = mrows(r, 'trot')
  const meas = _rank(rows)
  const top = meas[0]
  const top_t = _rank(rows_t)[0]
  const [sL, sR] = hasM(r) ? [r.sL, r.sR] : [jround(r.sL * 1.5), jround(r.sR * 1.5)]
  Object.assign(rd, {
    sym: r.nosym ? '—' : r.sym, symD: r.nosym ? NO_SYM_HINT : delta(r.sym, prevS ? prevS.sym : null, '점'), nosym: !!r.nosym,
    rom: r.rom, romD: delta(r.rom, prev ? prev.rom : null, '°'),
    sL, sR, stD: sL === sR ? '좌우 같음' : `${sL > sR ? '오른쪽' : '왼쪽'}이 ${Math.abs(sL - sR)}%p 짧음`,
    topTitle: `${top.leg} ${top.n}에서 좌우 차이가 가장 큽니다`,
    topSub: `왼 ${top.l}${top.u}, 오 ${top.r}${top.u}, 차이 ${top.df}${top.u}, 대칭 지수 차이 ${fmt(top.si, 1)}%`,
    rank: [
      ...meas.slice(1, 4).map((x) => ({ n: `${x.leg}, ${x.n}`, v: `차이 ${x.df}${x.u}`, c: '#fff' })),
      ...rows.filter((x) => x.na).map((x) => ({ n: `${x.leg}, ${x.n}`, v: '비교 불가', c: 'rgba(255,255,255,.5)' })),
    ],
    rows: rows.map((x) => ({
      sec: x.sec ?? null, na: !!x.na, n: x.n, reason: x.reason ?? '',
      lv: x.na ? '' : `${x.l}${x.u}`, rv: x.na ? '' : `${x.r}${x.u}`,
      dv: x.na ? '' : `${Math.abs(x.l! - x.r!)}${x.u}`,
    })),
    pm: r.ps[0], pu: r.ps[1], px: r.ps[0] - r.ps[1], ex: r.ex, model: `pga-pose ${r.model}`,
    kc: knee_chart(r), n_videos: r.videos.length || 16,
  })
  const k0 = rows_t[0]
  rp = {
    title: `${rd.name}의 걸음 보고서`,
    when: `${r.date} 측정, ${sess_no(acct, r)}회차, ${rd.desc}`,
    summary: `${top_t.leg} ${top_t.n}에서 왼쪽과 오른쪽 차이가 가장 컸어요(${top_t.df}${top_t.u}). 수의사 선생님과 함께 확인해 보세요.`,
    items: [
      { k: '좌우 대칭 점수', v: symText(r), d: r.nosym ? NO_SYM_HINT : prevS ? `직전 ${prevS.sym}점` : '첫 측정' },
      { k: '뒷무릎 움직임 범위', v: `왼 ${k0.l}°, 오 ${k0.r}°`, d: `차이 ${Math.abs(k0.l! - k0.r!)}°` },
      { k: '걸음 길이(등 길이 대비)', v: `왼 ${sL}%, 오 ${sR}%`, d: `차이 ${Math.abs(sL - sR)}%p` },
    ],
    rows: [
      ...rows_t.map((x) => ({
        n: x.n, l: x.na ? '측정 불가' : `${x.l}${x.u}`, r: x.na ? '—' : `${x.r}${x.u}`,
        d: x.na ? '—' : `${Math.abs(x.l! - x.r!)}${x.u}`,
      })),
      { n: '대칭 점수', l: '—', r: '—', d: symText(r) },
    ] as { n: string; l: string; r: string; d: string; bg?: string }[],
    cond: `측면 가로 촬영, 영상 ${r.videos.length || 16}개, 통과 ${r.ps[0]}개 중 ${r.ps[1]}개 사용, 분석 모델 pga-pose ${r.model}. 측정 불가 항목은 사유와 함께 표시했습니다.`
      + (hasM(r) ? ' 걸음 길이·발 들림 높이는 등 길이(T13~장골능) 대비이며, 문헌 값(어깨뼈~고관절 기준)과 비교할 때는 1.92로 나눕니다.' : ''),
  }
  rp.rows.forEach((row: { bg?: string }, i: number) => {
    row.bg = i % 2 ? '#fff' : '#FAF8F5'
  })
  return { rd, rp }
}

// ── 홈: 선택한 반려견 ──
export function dog_detail(acct: Account, d: Dog) {
  const all_ = acct.results.filter((r) => r.dog === d.id)
  const b_id = base_of(acct, d)
  const b_r = b_id ? resultOf(acct, b_id) : undefined
  const hist = all_.map((r, i) => ({
    id: r.id, no: `${sess_no(acct, r)}회차`, date: r.date, w: wkg(r.w), by: r.by || '—',
    pass: r.st === 'fail' ? '—' : `${r.ps[1]} / ${r.ps[0]}`, model: r.model,
    rep: r.rep ? '있음' : '—', base: r.id === b_id, canBase: r.st !== 'fail' && r.id !== b_id,
    ...st_chip(r.st), bt: i ? '1px solid #F2EFEA' : 'none',
  }))
  return {
    name: d.name, desc: `${desc(d)}, ${SEX[d.sex || 'm'] ?? 'None'}`,
    cells: [
      { k: '체급', v: SIZE[d.size || auto_size(d.breed, d.kg)], sub: d.size_manual ? '직접 지정' : '' },
      { k: '재활 시작일', v: d.rehab ? fmt_date(d.rehab) : '미입력', sub: '' },
      { k: '관심 다리', v: d.focus ? LIMB[d.focus] : '미선택', sub: '' },
      { k: '기준 회차', v: b_r ? `${b_r.date}, ${sess_no(acct, b_r)}회차` : '없음', sub: d.base ? '직접 지정' : b_r ? '가장 이른 회차' : '' },
    ],
    memo: d.memo || '없음', hist, count: `${all_.length}회차`,
  }
}

// ── 보고서: 몸 그림 위에 다리별 수치 (10-28) ──
const _DOG_SVG: Record<string, string> = {}
const _RAW_SVG: Record<string, string> = { small: dogSmall, medium: dogMedium, large: dogLarge }
const _LEGS: [string, string, string][] = [['front_left', 'LF', '왼앞'], ['front_right', 'RF', '오른앞'], ['hind_left', 'LH', '왼뒤'], ['hind_right', 'RH', '오른뒤']]
export type Level = [number, string, string, string]
const _LEVEL: Level[] = [ // (대칭 지수 차이 % 미만, 이름, 다리 색, 글자 색)
  [5, '비슷합니다', '#DCEFE2', '#2E8B57'],
  [10, '조금 차이 나요', '#F7D6AE', '#9A6A12'],
  [999, '차이가 큽니다', '#F2A898', '#C2412D'],
]

export function _svg(size: string): string {
  const name = ({ S: 'small', L: 'large' } as Record<string, string>)[size] ?? 'medium'
  if (!(name in _DOG_SVG)) {
    let s = _RAW_SVG[name].replace(/\r\n?/g, '\n') // 파이썬 read_text 처럼 줄바꿈을 \n 으로
    s = replaceN(s.slice(s.indexOf('<svg')), 'width="1024" height="1024"', 'width="100%" height="100%"', 1)
    s = replaceN(s, 'viewBox="0 0 1024 1024"', 'viewBox="362 144 300 736"', 1) // 빈 둘레를 잘라 크게(세 체급 공통 범위)
    _DOG_SVG[name] = s
  }
  return _DOG_SVG[name]
}

function _level(si: number): Level {
  return _LEVEL.find((x) => si < x[0])!
}

export interface LegSide {
  label: string
  weak: boolean
  c: string
  dot: string
  mets: { n: string; v: string; other: string; lower: boolean }[]
}
export interface LegPart {
  si: number
  level: string
  c: string
  say: string
  metric: string
  diff: string
  /** 가장 큰 차이가 난 수치의 왼쪽·오른쪽 값(단위 포함) */
  left: string
  right: string
}
export type BodyMap = ReturnType<typeof body_map>

/** 다리 한 쌍(앞·뒤)마다 좌우 차이를 재서, 덜 쓰는 쪽 다리를 색으로 칠한 그림과 다리별 수치. */
export function body_map(acct: Account, r: Result) {
  const d = dogOf(acct, r.dog)
  const rows: Record<string, Row> = {}
  // 앞·뒷다리에 같은 이름(입각기 비율 등)이 있어 부위까지 붙여 모은다. 이름만 쓰면 뒷다리 카드에 앞다리 값이 들어갔다(11-03 KPI-30)
  for (const x of mrows(r, 'trot')) if (!x.na) rows[`${x.leg}|${x.n}`] = x
  const pairs: [string, string[]][] = [['front', ['팔꿈치 가동 범위']], ['hind', ['무릎 가동 범위', '고관절 가동 범위', '걸음 길이', '입각기 비율']]]
  const word: Record<string, string> = {
    '팔꿈치 가동 범위': '팔꿈치를 굽히는 정도', '무릎 가동 범위': '무릎을 굽히는 정도',
    '고관절 가동 범위': '엉덩이 관절 움직임', '걸음 길이': '한 걸음 길이', '입각기 비율': '땅을 딛고 있는 시간',
  }
  const legs = {} as Record<string, LegSide> & { front: LegPart; hind: LegPart }
  const fills: Record<string, string> = {}
  for (const [part, names] of pairs) {
    const sec = part === 'front' ? '앞다리' : '뒷다리'
    const mets = names.filter((n) => `${sec}|${n}` in rows).map((n) => rows[`${sec}|${n}`] as Row & { l: number; r: number; u: string })
    const sis = mets.map((m) => (Math.abs(m.l - m.r) / ((m.l + m.r) / 2)) * 100)
    const k = maxBy([...mets.keys()], (i) => sis[i])
    const worst = mets[k]
    const si = sis[k]
    const weak = worst.l < worst.r ? 'l' : 'r' // 값이 작은 쪽 = 덜 쓰는 쪽
    const lv = _level(si)
    const side_kr: Record<string, string> = { l: '왼쪽', r: '오른쪽' }
    const leg_kr = part === 'front' ? '앞다리' : '뒷다리'
    let say: string
    if (si < 5) say = `${leg_kr} 양쪽을 비슷하게 씁니다`
    else {
      const w = word[worst.n]
      const wc = cp(w)
      say = `${side_kr[weak]} ${leg_kr}의 ${w}${pymod(wc[wc.length - 1].codePointAt(0)! - 0xac00, 28) ? '이' : '가'} 반대쪽보다 작습니다`
    }
    for (const side of ['l', 'r'] as const) {
      const code = (side === 'l' ? 'L' : 'R') + (part === 'front' ? 'F' : 'H')
      const other = side === 'l' ? 'r' : 'l'
      const on = si >= 5 && side === weak
      fills[code] = on ? lv[2] : si < 5 ? '#DCEFE2' : '#E9E4DC'
      legs[code] = {
        label: Object.fromEntries(_LEGS.map(([, c, k_]) => [c, k_]))[code], weak: on, c: on ? lv[3] : '#5B6472',
        dot: fills[code],
        mets: mets.map((m) => ({ n: m.n, v: `${m[side]}${m.u}`, other: `${m[other]}${m.u}`, lower: m[side] < m[other] })),
      }
    }
    ;(legs as Record<string, LegPart | LegSide>)[part] = {
      si: pyround(si, 1), level: lv[1], c: lv[3], say, metric: worst.n,
      diff: `${Math.abs(worst.l - worst.r)}${worst.u}`,
      left: `${worst.l}${worst.u}`, right: `${worst.r}${worst.u}`,
    }
  }
  let svg = _svg(d ? d.size : 'M')
  for (const [pid, code] of _LEGS) {
    const stroke = d && d.focus === code ? 'stroke="#D2601A" stroke-width="6" stroke-dasharray="14 8"' : 'stroke="#B8B0A4" stroke-width="2"'
    svg = replaceN(svg, `<path id="${pid}" fill="#E9E4DC" stroke="#B8B0A4" stroke-width="2"`, `<path id="${pid}" fill="${fills[code]}" ${stroke}`, 1)
  }
  const vs = valid(acct, r.dog).reverse()
  const fi = vs.findIndex((x) => x.id === r.id)
  const idx = fi >= 0 ? fi : vs.length - 1
  const hist = vs.slice(0, idx + 1).filter((x) => !x.nosym).slice(-8) // 점수 없는 회차는 추이에서 뺀다
  const [lo, hi] = hist.length
    ? [Math.min(...hist.map((x) => x.sym)) - 3, Math.max(...hist.map((x) => x.sym)) + 3]
    : [0, 100]
  const trend = hist.map((x, i) => ({
    x: pyround(30 + i * (300 / Math.max(1, hist.length - 1)), 1), y: pyround(80 - ((x.sym - lo) / (hi - lo)) * 64, 1),
    v: x.sym, t: short(x.date), cur: x.id === r.id,
  }))
  const base_id = d ? base_of(acct, d) : null
  const base = vs.find((x) => x.id === base_id) ?? null
  return {
    svg, legs, sym: r.sym, nosym: !!r.nosym, sym_level: _level(100 - r.sym),
    vs_base: base && base.id !== r.id && !r.nosym && !base.nosym ? r.sym - base.sym : null,
    base_date: base ? short(base.date) : '', base_label: base ? sess_label(acct, base, r) : '',
    prev_label: idx > 0 ? sess_label(acct, vs[idx - 1], r) : '', focus: d && d.focus ? LIMB[d.focus] ?? '' : '',
    trend, trend_line: trend.map((p) => `${pystr(p.x)},${pystr(p.y)}`).join(' '),
  }
}

// ── 홈 표 한 줄 값 (10-28) ──
export function age(d: Dog): string {
  const b = pyint(d.birth)
  return b === null ? '나이 미입력' : `${Number(isoToday().slice(0, 4)) - b}살`
}

export function days_ago(day: string): number {
  return ord(isoToday()) - ord(day)
}

export function latest_vital(d: Dog): Vital | null {
  return d.vitals.length ? d.vitals[0] : null
}

export function _num(x: unknown): number | null {
  return pyfloat(x)
}
const truthyNum = (x: number | null) => x !== null && (x !== 0 || Number.isNaN(x)) // 파이썬 float 의 참거짓

export interface Flag {
  m: string
  c: string
  ref: string
}
export type Flags = Record<'kg' | 'temp' | 'hr' | 'bp', Flag>

/** 바이탈 이상값 표시(EMR 의 H/L). 참고 범위는 config.VITAL_REF(일반 성견). 체중은 직전 방문 대비 변화율. */
export function vital_flags(v: Vital, size = 'M', prev: Vital | null = null): Flags {
  const [red, amber, ok] = ['#C2412D', '#9A6A12', '']
  const out = Object.fromEntries(['kg', 'temp', 'hr', 'bp'].map((k) => [k, { m: '', c: ok, ref: '' }])) as Flags
  let [lo, hi] = VITAL_REF.temp
  const t = _num(v.temp)
  out.temp.ref = `참고 ${pystr(lo)}~${pystr(hi)}℃`
  if (t !== null && !(lo <= t && t <= hi)) Object.assign(out.temp, { m: t > hi ? 'H' : 'L', c: red })
  ;[lo, hi] = VITAL_REF.hr[size || 'M'] ?? VITAL_REF.hr.M
  const h = _num(v.hr)
  out.hr.ref = `참고 ${lo}~${hi}회/분(${SIZE[size || 'M'] ?? ''})`
  if (h !== null && !(lo <= h && h <= hi)) Object.assign(out.hr, { m: h > hi ? 'H' : 'L', c: red })
  const [low, border, high] = VITAL_REF.sbp
  const s = _num(v.sbp)
  out.bp.ref = `수축기 참고 ${low}~${border - 1}, ${border}~${high - 1} 경계, ${high} 이상 높음`
  if (s !== null) {
    if (s >= high || s < low) Object.assign(out.bp, { m: s >= high ? 'H' : 'L', c: red })
    else if (s >= border) Object.assign(out.bp, { m: '경계', c: amber })
  }
  const k = _num(v.kg)
  const pk = prev ? _num(prev.kg) : null
  if (k !== null && truthyNum(pk)) {
    const ch = ((k - pk!) / pk!) * 100
    out.kg.ref = `직전 방문 ${prev!.kg}kg 대비 ${fmt_signed(ch, 1)}%`
    if (Math.abs(ch) > WEIGHT_CHANGE) Object.assign(out.kg, { m: `${ch > 0 ? '▲' : '▼'}${fmt(Math.abs(ch), 0)}%`, c: red })
  }
  return out
}

export interface VitalLine {
  kg: string
  temp: string
  hr: string
  bp: string
  when: string
  f: Flags | Record<string, never>
}

/** 체중/체온/심박/혈압. 재지 않은 값은 '—'. f = 이상값 표시 */
export function vital_line(v: Vital | null | undefined, size = 'M', prev: Vital | null = null): VitalLine {
  if (!v) return { kg: '—', temp: '—', hr: '—', bp: '—', when: '기록 없음', f: {} }
  return {
    kg: v.kg ? `${v.kg}kg` : '—', temp: v.temp ? `${v.temp}℃` : '—',
    hr: v.hr || '—', bp: v.sbp ? `${v.sbp}/${v.dbp}` : '—', when: short_day(v.day),
    f: vital_flags(v, size, prev),
  }
}

/** v 바로 전 방문의 바이탈(체중 변화 비교용). */
export function prev_vital(d: Dog, v: Vital): Vital | null {
  return d.vitals.find((x) => x.day < v.day && x.kg) ?? null
}

export function short_day(day: string): string {
  const p = day.split('-')
  return p.length === 3 ? `${Number(p[1])}/${Number(p[2])}` : day
}

const lastOf = <T>(xs: T[], f: (x: T) => unknown): T | undefined => [...xs].reverse().find(f)
const head = (t: string) => t.split(' (')[0]

// full: 템플릿이 `b.full or b.t` 로 읽지만 views.py 는 채우지 않는다(늘 없음)
export type Badge = { t: string; kind: string; full?: string }

/** 홈에 바로 보이는 특이사항: 최근 수술(없으면 진단) 하나만. */
export function badges(d: Dog): Badge[] {
  const out: Badge[] = []
  const sb = d.srv?.badges
  if (sb) {
    // 서버 배지(271). 중요 메모 배지는 '최근 변동'의 중요 메모와 겹쳐 따로 띄우지 않는다(이 화면의 원래 규칙과 같게)
    for (const b of sb) {
      if (b.code === 'SURGERY') out.push({ t: `${head(b.title ?? '')}, ${SITE[b.site ?? ''] ?? ''}, D+${days_ago(b.on)}`, kind: 'surg' })
      else if (b.code === 'DIAGNOSIS') out.push({ t: `${head(b.title ?? '')}, ${SITE[b.site ?? ''] ?? ''}`, kind: 'diag' })
    }
    return out
  }
  const surg = lastOf(d.history, (h) => h.kind === '수술')
  if (surg) out.push({ t: `${head(surg.title)}, ${SITE[surg.site] ?? ''}, D+${days_ago(surg.day)}`, kind: 'surg' })
  else {
    const diag = lastOf(d.history, (h) => h.kind === '진단')
    if (diag) out.push({ t: `${head(diag.title)}, ${SITE[diag.site] ?? ''}`, kind: 'diag' })
  }
  return out
}

export type Trend = { has: false } | { has: true; pts: string; sym: number; label: string; c: string; single: boolean }

/** 대칭 지수 작은 그래프(최근 유효 회차 6개)와 직전 대비 판정. */
export function trend(acct: Account, d: Dog): Trend {
  const vs = scored(acct, d.id).reverse().slice(-6)
  if (!vs.length) return { has: false }
  const syms = vs.map((r) => r.sym)
  const lo = Math.min(...syms) - 1
  const hi = Math.max(...syms) + 1
  const pts = syms.map((s, i) => `${fmt(4 + i * (64 / Math.max(1, syms.length - 1)), 0)},${fmt(22 - ((s - lo) / (hi - lo)) * 18, 0)}`).join(' ')
  const diff = syms.length > 1 ? syms[syms.length - 1] - syms[syms.length - 2] : 0
  const [label, c] = syms.length === 1 ? ['첫 측정', '#5B6472']
    : diff >= SYM_CHANGE ? ['좋아짐', '#2E8B57']
      : diff <= -SYM_CHANGE ? ['나빠짐', '#C2412D'] : ['비슷함', '#5B6472']
  return { has: true, pts, sym: syms[syms.length - 1], label, c, single: syms.length === 1 }
}

export interface Change {
  t: string
  tone: string
}

/** 최근 CHANGE_DAYS 일 안의 변동 사유와 가장 최근 변동일.
 *  EMR 처럼 조치가 필요하거나 이상한 것만 띄운다(11-02): 재촬영, 보행 나빠짐·좋아짐, 수술 등록, 중요 메모. */
export function changes(acct: Account, d: Dog): [Change[], string] {
  const out: Change[] = []
  let last = ''
  const add = (day: string, label: string, tone: string) => {
    out.push({ t: label, tone })
    if (day > last) last = day
  }
  const sc = d.srv?.changes
  if (sc) {
    // 서버 변동(271, 최근 7일). 앱(AppProto changesOf)과 같은 규칙: 재촬영은 가장 최근 회차가 실패면 '재촬영 필요', 아니면 '일부 유효'
    const latest = acct.results.find((r) => r.dog === d.id && r.day)
    for (const c of sc) {
      if (c.code === 'SURGERY_ADDED') add(c.on, '수술 등록', 'surg')
      else if (c.code === 'RESHOOT_NEEDED') {
        if (!latest || latest.st === 'fail') add(c.on, '재촬영 필요', 'bad')
        else add(c.on, '일부 유효, 재촬영 권장', 'warn')
      } else if (c.code === 'GAIT_BETTER' && c.delta != null) add(c.on, `보행 좋아짐 +${c.delta}점`, 'good')
      else if (c.code === 'GAIT_WORSE' && c.delta != null) add(c.on, `보행 나빠짐 −${-c.delta}점`, 'bad')
      else if (c.code === 'IMPORTANT_NOTE') add(c.on, '중요 메모', 'warn')
    }
    return [out.filter((x, i) => out.findIndex((y) => y.t === x.t) === i), last]
  }
  for (const h of d.history) if (h.kind === '수술' && days_ago(h.day) <= CHANGE_DAYS) add(h.day, '수술 등록', 'surg')
  const rs = acct.results.filter((r) => r.dog === d.id && r.day)
  for (const r of rs) {
    if (days_ago(r.day) > CHANGE_DAYS) continue
    if (r.st === 'fail') {
      add(r.day, '재촬영 필요', 'bad')
      continue
    }
    const prev = r.nosym ? null : rs.find((x) => x.st !== 'fail' && !x.nosym && x.day < r.day)
    if (r.st === 'part') add(r.day, '일부 유효, 재촬영 권장', 'warn')
    if (prev && r.sym - prev.sym >= SYM_CHANGE) add(r.day, `보행 좋아짐 +${r.sym - prev.sym}점`, 'good')
    else if (prev && prev.sym - r.sym >= SYM_CHANGE) add(r.day, `보행 나빠짐 −${prev.sym - r.sym}점`, 'bad')
  }
  for (const n of d.notes) if (n.important && days_ago(n.at.slice(0, 10)) <= CHANGE_DAYS) add(n.at.slice(0, 10), '중요 메모', 'warn')
  const seen = new Set<string>()
  const uniq: Change[] = []
  for (const x of out) {
    // 같은 사유는 한 번만
    if (!seen.has(x.t)) {
      seen.add(x.t)
      uniq.push(x)
    }
  }
  return [uniq, last]
}

export type PatientRow = ReturnType<typeof patient_row>

export function patient_row(acct: Account, d: Dog, live: Set<string>) {
  const [st_label, st_bg, st_c] = STAGE[d.stage]
  const last = acct.results.find((r) => r.dog === d.id)
  const [ch, ch_day] = changes(acct, d)
  const lv = latest_vital(d)
  return {
    id: d.id, no: d.no || '—', name: d.name, init: cp(d.name)[0],
    breed: d.breed || '견종 미입력', size: SIZE[d.size] ?? '', age: age(d), sex: SEX[d.sex] ?? '',
    v: vital_line(lv, d.size, d.vitals.length ? prev_vital(d, lv!) : null), badges: badges(d),
    owner: d.owner || '—', phone4: d.phone ? cp(d.phone).slice(-4).join('') : d.phone4 ?? '',
    last: last ? `${short(last.date)}, ${last.by.split(' ')[0]}` : '측정 전', tr: trend(acct, d),
    stage: st_label, st_bg, st_c, live: live.has(d.id),
    changes: ch, ch_day, site: lastOf(d.history, (h) => h.site)?.site ?? '',
  }
}

// ── 홈: 분석 · 반려견 · 촬영 담당자 목록 (10-28 2판) ──
/** 검색 대상: 이름·동물번호·견종·보호자·진단/수술·메모. */
export function dog_text(d: Dog): string {
  return [d.name, d.no, d.breed, d.owner, d.phone ? cp(d.phone).slice(-4).join('') : d.phone4 ?? '', d.memo,
    ...d.history.map((h) => h.title), ...d.notes.map((n) => n.text), ...(d.srv?.dx_text ? [d.srv.dx_text] : [])].join(' ')
}

export function analysis_rows(acct: Account, rs: Result[]) {
  return rs.map((r) => {
    const d = dogOf(acct, r.dog)!
    return {
      id: r.id, dog: d.id, name: d.name, no: d.no || '—', breed: d.breed || '견종 미입력',
      when: `${short(r.date)} ${r.time}`, no_s: `${sess_no(acct, r)}회차`, ...st_chip(r.st),
      sym: symText(r), sym_tip: r.nosym ? NO_SYM_HINT : '', pass: r.st === 'fail' ? '—' : `${r.ps[1]} / ${r.ps[0]}`,
      by: r.by || '—', badges: badges(d), dx: diagnosis(d), ...sym_view(acct, r),
    }
  })
}

/** 분석 표의 대칭 지수 배지: 수준별 색, 직전 유효 회차 대비 오르내림 */
export function sym_view(acct: Account, r: Result): { sym_bg: string; sym_c: string; sym_d: string; sym_dc?: string } {
  if (r.st === 'fail' || r.nosym) return { sym_bg: '#F2EFEA', sym_c: '#5B6472', sym_d: '' }
  const lv = r.sym >= 90 ? [90, '', '#DCEFE2', '#2E7A4F'] : r.sym >= 80 ? [80, '', '#FBEBC8', '#8A6100']
    : [0, '', '#FBE0D9', '#C2412D'] // 회차 균형 점수 기준(다리 하나 차이 기준 _LEVEL 과 다름)
  const prev = acct.results.find((x) => x.dog === r.dog && x.st !== 'fail' && !x.nosym && (x.day < r.day || (x.day === r.day && x.time < r.time)))
  const dv = prev ? r.sym - prev.sym : 0
  return {
    sym_bg: lv[2] as string, sym_c: lv[3] as string,
    sym_d: prev && dv ? (dv > 0 ? `▲${dv}` : `▼${-dv}`) : '', sym_dc: dv > 0 ? '#2E8B57' : '#C2412D',
  }
}

/** 병명: 히스토리의 가장 최근 진단(분석 표 칸). 괄호 설명은 뺀다 */
export function diagnosis(d: Dog): string {
  const h = lastOf(d.history, (h) => h.kind === '진단')
  return h ? head(h.title) : d.srv?.diag ? head(d.srv.diag) : '—' // 차트를 열기 전 백엔드 반려견은 목록의 최근 진단
}

/** 홈 '오늘' 탭(EMR 의 오늘 접수 목록): 오늘 바이탈·진료 기록·메모·보행 측정이 있거나 지금 분석 중인 반려견.
 *  시각 = 그날 마지막 기록 시각(진료 기록·측정·지금 분석 시작), 최근 시각이 위. 진료 기록(SOAP)이 아직 없으면 '기록 전'. */
/** 그날(기본 오늘) 진료·측정이 있었던 반려견. 진행 중 분석은 오늘에만 붙는다 */
export function today_rows(acct: Account, dogs: Dog[], day = isoToday()) {
  const today = day
  const live = new Map<string, Job>()
  if (day === isoToday()) for (const j of activeJobs(acct)) live.set(j.dog, j)
  const out = []
  for (const d of dogs) {
    const notes = d.notes.filter((n) => noteDay(n) === today)
    const res = acct.results.filter((r) => r.dog === d.id && r.day === today)
    const vit = d.vitals.find((v) => v.day === today)
    if (!(notes.length || res.length || vit || live.has(d.id))) continue
    const job = live.get(d.id)
    const hm = (ms: number) => { const t = new Date(ms); return `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}` }
    const times = [...notes.map((n) => n.at.slice(11, 16)), ...res.map((r) => r.time), ...(vit?.at ? [vit.at.slice(11, 16)] : []), ...(job?.started ? [hm(job.started)] : [])].filter((t) => /^\d{2}:\d{2}$/.test(t))
    const steps: [string, string, string][] = []
    if (vit) steps.push(['바이탈', '#E7EEFB', '#3B5BA9'])
    if (notes.some((n) => n.cat in SOAP)) steps.push(['진료 기록', '#E3F1E7', '#2E7A4F'])
    if (live.has(d.id)) steps.push(['분석 중', '#FCEEE3', '#A8481A'])
    for (const r of res) {
      steps.push([r.st === 'fail' ? '재촬영 필요' : '보행 측정', r.st === 'fail' ? '#FBE0D9' : '#F1ECE5', r.st === 'fail' ? '#C2412D' : '#5B6472'])
    }
    const done = notes.some((n) => n.cat in SOAP)
    const first = sorted(notes, (n) => n.at)[0]
    out.push({
      ...patient_row(acct, d, new Set(live.keys())), time: times.length ? maxBy(times, (t) => t) : '—', // 그날 마지막 기록 시각(11-18)
      steps: steps.map(([t, bg, c]) => ({ t, bg, c })), dx: diagnosis(d),
      who: (first ? first.author : '') || (live.has(d.id) ? live.get(d.id)!.by : '') || (vit ? vit.author : ''),
      todo: done ? '' : '기록 작성',
    })
  }
  return sorted(out, (r) => r.time, true) // 최근 시각이 위로(11-18). 시각 없는 행(지금 분석 중)이 맨 위
}

export function staff_rows(acct: Account, rs: Result[]) {
  void acct
  const by = new Map<string, { name: string; n: number; dogs: Set<string>; last: string; fail: number }>()
  for (const r of rs) {
    if (!r.by) continue
    if (!by.has(r.by)) by.set(r.by, { name: r.by, n: 0, dogs: new Set(), last: '', fail: 0 })
    const x = by.get(r.by)!
    x.n += 1
    x.dogs.add(r.dog)
    if (r.day > x.last) x.last = r.day
    x.fail += r.st === 'fail' ? 1 : 0
  }
  return sorted(by.values(), (x) => -x.n).map((x) => ({ ...x, dogs: x.dogs.size, last: x.last ? short_day(x.last) : '—' }))
}

/** changed: false·'' = 전체, true·'1' = 일주일 간 변동, 'retake' = 재촬영 필요만(홈 요약 카드) */
/** 진료 기록·측정·바이탈이 있는 날짜(홈 달력의 점) */
export function activity_days(acct: Account): Set<string> {
  const s = new Set<string>()
  for (const d of acct.dogs) { for (const n of d.notes) s.add(noteDay(n)); for (const v of d.vitals) s.add(v.day) }
  for (const r of acct.results) if (r.day) s.add(r.day)
  return s
}

export function home_view(acct: Account, view: string, q: string, dog: string, by: string, changed: boolean | string, stage: string, page: number, day = isoToday()) {
  q = q.trim()
  const ch = new Map(acct.dogs.map((d) => [d.id, changes(acct, d)] as const))
  const retakeOf = (v: ReturnType<typeof changes>) => v[0].some((c) => c.t.includes('재촬영') && c.tone === 'bad')
  const dogs = acct.dogs.filter((d) => (!q || dog_text(d).includes(q)) && (!changed || (changed === 'retake' ? retakeOf(ch.get(d.id)!) : ch.get(d.id)![0].length))
    && (!(stage in STAGE) || d.stage === stage))
  const keep = new Set(dogs.map((d) => d.id))
  const rs = acct.results.filter((r) => dogOf(acct, r.dog))
  const counts = {
    dogs: acct.dogs.length, changed: [...ch.values()].filter((v) => v[0].length).length,
    retake: [...ch.values()].filter(retakeOf).length,
    today: today_rows(acct, acct.dogs).length,
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let rows: any[]
  if (view === 'today') rows = today_rows(acct, dogs, day)
  else if (view === 'dogs') {
    rows = dogs.map((d) => ({ ...patient_row(acct, d, new Set()), n: rs.filter((r) => r.dog === d.id).length }))
    if (changed) rows = sorted(rows, (r) => r.ch_day, true)
  } else if (view === 'staff') rows = staff_rows(acct, rs.filter((r) => keep.has(r.dog) || (q && r.by.includes(q))))
  else {
    const sel = rs.filter((r) => (keep.has(r.dog) || (q && r.by.includes(q))) && (!dog || r.dog === dog) && (!by || r.by === by))
    // 최근 분석이 위로(11-18): 측정일 → 끝난 시각 순으로 내림차순
    rows = view === 'analyses' ? analysis_rows(acct, sorted(sel, (r) => `${r.day || ''} ${r.time || ''}`, true)) : []
  }
  const total = rows.length
  const pages = Math.max(1, -floordiv(-total, PAGE_SIZE))
  page = Math.min(Math.max(1, page), pages)
  return { rows: rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE), total, page, pages, ...counts }
}

const dotAt = (at: string) => replaceN(at, '-', '.', 2).slice(2)

/** 차트 위 고정 줄의 메모 카드: 주의·보호자·예약·기타. 중요 먼저, 그 안에서 최신순. 등록할 때 적은 메모(Dog.memo)는 맨 끝. */
export function memos(d: Dog) {
  const rows = sorted(d.notes, (n) => [n.important, n.at], true).filter((n) => n.cat in MEMO_CAT).map((n) => ({
    id: n.id, cat: n.cat, bg: MEMO_CAT[n.cat][0], c: MEMO_CAT[n.cat][1], text: n.text, imp: n.important,
    at: dotAt(n.at), author: n.author,
    revs: n.revs.map(([a, w, t]) => ({ at: dotAt(a), author: w, text: t })),
  }))
  if (d.memo) rows.push({ id: '', cat: '등록', bg: '#F1ECE5', c: '#5B6472', text: d.memo, imp: false, at: '', author: '', revs: [] })
  return rows
}

/** 분석 결과 화면 오른쪽 칸: 메모를 바로 쓰고 보며, 이 회차 진료 기록을 본다. */
export function memo_panel(acct: Account, d: Dog, rid = '') {
  const groups = soap_entries(d, acct)
  return {
    ...patient_row(acct, d, new Set()), rid, memo_cat: MEMO_CAT, memos: memos(d),
    run_soap: groups.filter((g) => rid && g.rid === rid),
    n_res: acct.results.filter((r) => r.dog === d.id).length,
  }
}

/** 방문 목록(EMR 왼쪽 칸): 같은 날짜의 보행 측정·바이탈·진료 기록·진단/수술/재활·영상을 한 방문으로 묶는다. 최신순.
 *  방문은 따로 저장하지 않고 날짜로 묶어 만든다(백엔드에 방문 엔티티 없음). */
export function visits(acct: Account, d: Dog) {
  type V = { day: string; res: Result[]; vital: Vital | null; soap: SoapEntry[]; hist: History[]; imgs: Dog['images'] }
  const by = new Map<string, V>()
  const v = (day: string): V => {
    if (!by.has(day)) by.set(day, { day, res: [], vital: null, soap: [], hist: [], imgs: [] })
    return by.get(day)!
  }
  for (const r of acct.results) if (r.dog === d.id && r.day) v(r.day).res.push(r)
  for (const x of d.vitals) v(x.day).vital = x
  for (const gr of soap_entries(d, acct)) v(gr.day).soap.push(gr)
  for (const h of d.history) v(h.day).hist.push(h)
  for (const im of d.images) v(im.day).imgs.push(im)
  const today = isoToday()
  return sorted(by.keys(), (k) => k, true).map((day) => {
    const x = by.get(day)!
    const res = sorted(x.res, (r) => r.time)
    const rl = res[res.length - 1]
    const tags = x.hist.map((h) => ({ t: h.kind, bg: h.kind === '수술' ? '#FCEEE3' : '#EEF1F6', c: h.kind === '수술' ? '#A8481A' : '#4A5A78' }))
    if (res.length) tags.push({ t: '보행 측정', bg: '#F1ECE5', c: '#5B6472' })
    if (x.imgs.length) tags.push({ t: `영상 ${x.imgs.length}`, bg: '#F1ECE5', c: '#5B6472' })
    const a = x.soap.flatMap((gr) => gr.parts).find((p) => p.cat === 'A' || p.cat === 'S')?.text ?? ''
    const title = x.hist.length ? head(x.hist[0].title) : a || (
      res.length && rl.st !== 'fail' ? (rl.nosym ? '보행 측정, 대칭 점수 없음' : `보행 측정, 대칭 점수 ${rl.sym}점`) : res.length ? '보행 측정, 재촬영 필요'
        : x.vital ? '바이탈 측정' : '')
    const who = (x.soap.length ? x.soap[0].author : '') || (x.hist.length ? x.hist[0].by || x.hist[0].author : '')
      || (res.length ? rl.by : '') || (x.vital ? x.vital.author : '')
    const st = res.length ? st_chip(rl.st) : null
    return {
      day, date: day.slice(2).replaceAll('-', '.'), tags, title, who, st,
      n_soap: x.soap.length, today: day === today,
      res: res.map((r) => ({
        id: r.id, no: `${sess_no(acct, r)}회차`, time: r.time, by: r.by, fail: r.st === 'fail',
        sym: r.sym, sym_t: symText(r), sym_tip: r.nosym ? NO_SYM_HINT : '', rom: r.rom, sL: r.sL, sR: r.sR, ...st_chip(r.st), ...sym_view(acct, r),
      })),
      vital: x.vital ? vital_line(x.vital, d.size, prev_vital(d, x.vital)) : null, vital_by: x.vital ? x.vital.author : '',
      soap: x.soap, hist: x.hist,
      imgs: x.imgs.map((im) => ({ id: im.id, path: im.path, caption: im.caption, kind: IMG_KIND[im.kind] ?? im.kind, by: im.author })),
    }
  })
}

export interface BestView {
  main: string
  label: string
  sub: string
  sub_label: string
  why: string
}

/** 3D 에서 좌우 차이가 가장 잘 보이는 각도. 기본은 덜 쓰는 다리 쪽 옆모습이고, 두 다리를 한 화면에서 견줄 때는
 *  뒷다리면 뒤에서, 앞다리면 앞에서 본다. */
// 보호자용 "알아 두면 좋은 점"(views.owner_guide). 병명·질환 가능성·정상 범위는 말하지 않는다(PR-F08-11). 문구는 수의사 검토 전 초안
const _PLAIN: Record<string, string> = {
  '팔꿈치 가동 범위': '팔꿈치를 굽히는 폭', '무릎 가동 범위': '무릎을 굽히는 폭', '고관절 가동 범위': '엉덩이 관절이 움직이는 폭',
  '걸음 길이': '한 걸음 길이', '입각기 비율': '발을 딛고 있는 시간',
}
const _URGENT = ['다리를 전혀 딛지 않을 때', '만졌을 때 싫어하거나, 붓거나, 열감이 있을 때', '며칠 사이 갑자기 더 절 때']
export interface OwnerGuide { weak: boolean; summary: string; what: string; look: string[]; help: string[]; urgent: string[] }

export function owner_guide(bm: BodyMap): OwnerGuide {
  const fr = bm.legs.front as LegPart, hd = bm.legs.hind as LegPart
  const part = hd.si >= fr.si ? 'hind' : 'front'
  const p = (part === 'hind' ? hd : fr)
  const fh = part === 'hind' ? 'H' : 'F'
  const weak = ['L', 'R'].map((s) => s + fh).find((c) => (bm.legs[c] as LegSide).weak) ?? null
  if (p.si < 5 || !weak)
    return { weak: false, summary: '앞다리·뒷다리 모두 양쪽을 비슷하게 써요.', what: '왼쪽·오른쪽 다리에 몸무게를 비슷하게 싣고 걸어요.',
      look: [], help: ['지금처럼 꾸준히 산책해 주세요', '미끄러운 바닥에는 매트를 깔아 주세요'], urgent: _URGENT }
  const side = weak[0] === 'L' ? '왼쪽' : '오른쪽'
  const other = side === '왼쪽' ? '오른쪽' : '왼쪽'
  const leg = part === 'hind' ? '뒷다리' : '앞다리'
  const mets = (bm.legs[weak] as LegSide).mets
  const m = mets.find((x) => x.n === p.metric) ?? mets[0]
  const plain = _PLAIN[m.n] ?? m.n
  const josa = (plain.charCodeAt(plain.length - 1) - 0xac00) % 28 ? '이' : '가' // 받침 있으면 이, 없으면 가
  const summary = `${side} ${leg}를 덜 써요. ${plain}${josa} ${side} ${m.v}, ${other} ${m.other}예요.`
  const what = `${side} ${leg}에 몸무게를 덜 싣고 걸어요. 그만큼 ${other} ${leg}` + (part === 'hind' ? '와 앞다리가' : '와 뒷다리가') + ' 몸무게를 더 받아요.'
  if (part === 'hind')
    return { weak: true, summary, what, urgent: _URGENT,
      look: [`${side} 뒷다리를 디딜 때 엉덩이가 들썩이거나, 몸이 ${other}으로 기울어 보일 수 있어요`, `앉을 때 ${side} 뒷다리를 옆으로 빼고 앉을 수 있어요`,
        '계단을 오르거나 소파·차에 뛰어오를 때 머뭇거릴 수 있어요'],
      help: ['미끄러운 바닥에는 매트를 깔아 주세요', '계단·점프는 담당 수의사가 괜찮다고 할 때까지 줄여 주세요', '산책은 평지에서 짧게, 자주 하는 것이 좋아요',
        `양쪽 허벅지 굵기를 가끔 손으로 만져 비교해 보세요. ${side}이 가늘어지면 다음 진료 때 알려 주세요`] }
  return { weak: true, summary, what, urgent: _URGENT,
    look: [`${side} 앞다리를 디딜 때 고개가 위로 들리며 끄덕이듯 걸을 수 있어요`, `서 있을 때 ${side} 앞발을 살짝 들거나 짧게 디딜 수 있어요`,
      '계단을 내려가거나 높은 곳에서 뛰어내릴 때 머뭇거릴 수 있어요'],
    help: ['미끄러운 바닥에는 매트를 깔아 주세요', '계단 내려가기·높은 곳에서 뛰어내리기는 담당 수의사가 괜찮다고 할 때까지 줄여 주세요', '산책은 평지에서 짧게, 자주 하는 것이 좋아요'] }
}

export function best_view(bm: { legs: Record<string, unknown> & { front: LegPart; hind: LegPart } }): BestView {
  const pairs: [string, LegPart][] = (['hind', 'front'] as const).map((p) => [p, bm.legs[p]])
  const [part, x] = maxBy(pairs, (t) => t[1].si)
  const leg_kr = part === 'hind' ? '뒷다리' : '앞다리'
  if (x.si < 5) {
    return {
      main: 'right', label: '옆', sub: 'back', sub_label: '뒤',
      why: '좌우 차이가 거의 없습니다. 옆에서 걷는 모양을, 뒤에서 두 뒷다리가 같이 움직이는지 보세요.',
    }
  }
  const fh = part === 'front' ? 'F' : 'H'
  const weak = ['L', 'R'].map((s) => s + fh).find((c) => (bm.legs[c] as LegSide).weak)!
  const side = weak[0] === 'L' ? 'left' : 'right'
  const side_kr = side === 'left' ? '왼쪽' : '오른쪽'
  const [sub, sub_kr] = part === 'hind' ? ['back', '뒤'] : ['front', '앞']
  return {
    main: side, label: `${side_kr} 옆`, sub, sub_label: sub_kr,
    why: `${side_kr} ${leg_kr}가 덜 움직입니다. ${side_kr} 옆에서 보면 그 다리가 관절을 덜 굽히고 짧게 딛는 게 가려지지 않고 보입니다. `
      + `${sub_kr}에서 보면 두 ${leg_kr}의 발 드는 높이를 한 화면에서 견줄 수 있습니다.`,
  }
}

/** 환자 단위 영상·사진 모아 보기(경과 탭): 촬영일 순(오래된 것 먼저)이라 수술 전 → 후가 왼쪽에서 오른쪽으로 놓인다. */
export function image_list(d: Dog) {
  return sorted(d.images, (x) => x.day).map((im) => ({
    id: im.id, day: im.day, date: im.day.slice(2).replaceAll('-', '.'), path: im.path, caption: im.caption,
    kind: IMG_KIND[im.kind] ?? im.kind, pre: im.kind === 'pre', post: im.kind === 'post', by: im.author,
  }))
}

export interface Episode {
  start: string
  title: string
  site: string
  by: string
  events: { day: string; kind: string; title: string }[]
  done?: boolean
  n?: number
  range?: string
}

/** 진단 이력(EMR 오른쪽 칸): 진단 하나에 뒤따른 수술·재활을 묶는다. 종결 기록이 있으면 종결, 아니면 진행중.
 *  회차 = 진단일 이후 보행 측정 수. */
export function dx_history(acct: Account, d: Dog): Episode[] {
  const eps: Episode[] = []
  for (const h of d.history) {
    if (h.kind === '진단' || !eps.length) eps.push({ start: h.day, title: head(h.title), site: SITE[h.site] ?? '', by: h.by || h.author, events: [] })
    if (h.kind !== '진단') eps[eps.length - 1].events.push({ day: h.day.slice(2).replaceAll('-', '.'), kind: h.kind, title: h.title })
  }
  eps.forEach((e, i) => {
    const end = i + 1 < eps.length ? eps[i + 1].start : null
    const done = e.events.some((x) => x.title.includes('종결'))
    e.done = done
    e.n = acct.results.filter((r) => r.dog === d.id && r.day >= e.start && (!end || r.day < end)).length
    e.range = e.start.slice(2).replaceAll('-', '.') + ' ~' + (done ? ' ' + lastOf(e.events, (x) => x.title.includes('종결'))!.day : '')
  })
  return eps.reverse()
}

/** 담당: 주치의 = 최근 진단·수술한 수의사, 최근 측정 = 마지막 회차 측정자. */
export function care_team(acct: Account, d: Dog): { doctor: string; measurer: string } {
  const h = lastOf(d.history, (h) => (h.kind === '수술' || h.kind === '진단') && !!h.by)
  const last = acct.results.find((r) => r.dog === d.id)
  return { doctor: h ? h.by : '—', measurer: last && last.by ? last.by : '—' }
}

// ── 반려견 차트 (10-28) ──
/** 차트 요약 탭: 시간 축 하나에 대칭 지수 선, 수술·재활 단계 세로선, 메모·바이탈 점. */
export function chart_summary(acct: Account, d: Dog) {
  const vs = scored(acct, d.id).reverse().filter((r) => r.day) // 대칭 점수 그래프라 점수 있는 회차만
  const days = [...d.history.map((h) => h.day), ...vs.map((r) => r.day), ...d.vitals.map((v) => v.day), ...d.notes.map((n) => noteDay(n))]
  if (!days.length) return { has: false as const }
  const t0 = ord(minBy(days, (x) => x))
  const t1 = ord(isoToday())
  const span = Math.max(1, t1 - t0)
  const [W, H, L, R, T, B] = [760, 220, 44, 16, 18, 52] // 그림 크기와 여백
  const X = (day: string) => pyround(L + ((ord(day) - t0) / span) * (W - L - R), 1)
  const syms = vs.map((r) => r.sym)
  const [lo, hi] = syms.length ? [Math.min(...syms) - 3, Math.max(...syms) + 3] : [70, 100]
  const Y = (v: number) => pyround(T + ((hi - v) / (hi - lo)) * (H - T - B), 1)
  const marks = d.history.filter((h) => h.kind === '수술' || h.kind === '재활').map((h) => ({ x: X(h.day), kind: h.kind, label: head(h.title), day: short_day(h.day) }))
  const pts = vs.map((r) => ({ x: X(r.day), y: Y(r.sym), sym: r.sym, day: short_day(r.day), by: r.by, id: r.id }))
  const notes = d.notes.map((n) => ({ x: X(noteDay(n)), imp: n.important, t: cp(n.text).slice(0, 40).join(''), day: short_day(noteDay(n)) }))
  const vit = d.vitals.map((v) => ({ x: X(v.day) }))
  const ticks = []
  for (let k = 0; k < 6; k++) {
    const day = t0 + pyround((span * k) / 5)
    ticks.push({ x: pyround(L + (k / 5) * (W - L - R), 1), t: short_day(fromOrd(day)) })
  }
  const [first, last] = vs.length ? [vs[0], vs[vs.length - 1]] : [null, null]
  const surg = lastOf(d.history, (h) => h.kind === '수술')
  return {
    has: true as const, W, H, L, R, T, B, line: pts.map((p) => `${pystr(p.x)},${pystr(p.y)}`).join(' '),
    pts, marks, notes, vit, ticks,
    yt: [pyround(lo + 3), pyround((lo + hi) / 2), pyround(hi - 3)].map((v) => ({ y: Y(v), v })),
    facts: [
      { k: '수술 후', v: surg ? `D+${days_ago(surg.day)}` : '수술 없음', sub: surg ? head(surg.title) : '' },
      {
        k: '대칭 점수', v: last ? `${last.sym}점` : '—',
        sub: last && first !== last ? `첫 측정 ${first!.sym}점 → ${fmt_signed(last.sym - first!.sym)}점` : last ? '첫 측정' : '유효 측정 없음',
      },
      { k: '보행 측정', v: `${vs.length}회 유효`, sub: last ? `마지막 ${short_day(last.day)}, ${last.by}` : '' },
      { k: '마지막 바이탈', v: vital_line(latest_vital(d)).when, sub: d.vitals.length ? d.vitals[0].author : '' },
    ],
  }
}

export interface NoteRow {
  id: string
  /** 방문일 YYYY-MM-DD */
  day: string
  at: string
  author: string
  cat: string
  text: string
  imp: boolean
  rid: string
  run: string
  soap: string
  revs: { at: string; author: string; text: string }[]
}

/** 메모·진료 기록의 방문일: 서버 방문일(visited_on), 없으면 쓴 날 */
export const noteDay = (n: { day?: string; at: string }): string => n.day || n.at.slice(0, 10)

export function note_rows(d: Dog, acct?: Account | null): NoteRow[] {
  const run_label = (rid: string) => {
    // 회차 메모면 "10.25 · 5회차"
    const r = acct && rid ? resultOf(acct, rid) : undefined
    return r ? `${short(r.date)}, ${sess_no(acct!, r)}회차` : ''
  }
  return sorted(d.notes, (n) => [n.important, n.at], true).map((n) => ({ // 중요 메모 먼저, 그 안에서 최신순
    id: n.id, day: noteDay(n), at: dotAt(n.at), author: n.author, cat: n.cat, text: n.text,
    imp: n.important, rid: n.rid, run: run_label(n.rid),
    soap: (SOAP[n.cat] ?? ['', ''])[0],
    revs: n.revs.map(([a, w, t]) => ({ at: dotAt(a), author: w, text: t })),
  }))
}

export interface SoapEntry {
  /** 방문일 YYYY-MM-DD */
  day: string
  at: string
  author: string
  rid: string
  run: string
  imp: boolean
  parts: NoteRow[]
}

/** 차트 '진료 기록' 탭: 같은 시각·같은 사람·같은 회차로 쓴 메모를 한 기록으로 묶고 S·O·A·P 순서로 보인다(EMR 방식).
 *  중요 표시가 있는 기록이 먼저, 그 안에서 최신순. */
export function soap_entries(d: Dog, acct?: Account | null): SoapEntry[] {
  const groups = new Map<string, SoapEntry>()
  for (const n of note_rows(d, acct)) {
    if (!(n.cat in SOAP)) continue // 메모(주의·보호자·예약·기타)는 진료 기록이 아니다
    const key = JSON.stringify([n.day, n.at, n.author, n.rid])
    if (!groups.has(key)) groups.set(key, { day: n.day, at: n.at, author: n.author, rid: n.rid, run: n.run, imp: false, parts: [] })
    const gr = groups.get(key)!
    gr.imp = gr.imp || n.imp
    gr.parts.push(n)
  }
  const order = Object.fromEntries(NOTE_CAT.map((k, i) => [k, i]))
  for (const gr of groups.values()) gr.parts = sorted(gr.parts, (x) => order[x.cat] ?? 9)
  return sorted(groups.values(), (gr) => [gr.imp, gr.at], true)
}

/** 차트 위 고정 줄의 체중 추이(최근 n번 방문). 세로 폭은 최소 ±0.5kg 로 잡아 작은 흔들림이 크게 보이지 않게 한다. */
export function kg_trend(d: Dog, n = 8) {
  const kg = [...d.vitals].reverse().filter((v) => truthyNum(_num(v.kg))).map((v) => [v.day, _num(v.kg)!] as [string, number]).slice(-n)
  if (kg.length < 2) return { has: false as const }
  const vals = kg.map(([, k]) => k)
  const mx = Math.max(...vals)
  const mn = Math.min(...vals)
  const mid = (mx + mn) / 2
  const half = Math.max(0.5, ((mx - mn) / 2) * 1.15)
  const [W, H] = [72, 22]
  const pts = kg.map(([, k], i) => [2 + (i * (W - 4)) / (kg.length - 1), H - 3 - ((k - (mid - half)) / (2 * half)) * (H - 6)] as [number, number])
  const ch = ((vals[vals.length - 1] - vals[0]) / vals[0]) * 100
  return {
    has: true as const, W, H, line: pts.map(([x, y]) => `${fmt(x, 1)},${fmt(y, 1)}`).join(' '), last: pts[pts.length - 1],
    text: `${g(vals[0])}→${g(vals[vals.length - 1])}kg`, ch: `${fmt_signed(ch, 1)}%`, n: kg.length, since: short_day(kg[0][0]),
    c: Math.abs(ch) > WEIGHT_CHANGE ? '#C2412D' : '#5B6472',
  }
}

export function vital_rows(d: Dog) {
  const rows = d.vitals.map((v) => ({ day: v.day, ...vital_line(v, d.size, prev_vital(d, v)), author: v.author }))
  const kg = [...d.vitals].reverse().filter((v) => v.kg).map((v) => [v.day, Number(v.kg.trim())] as [string, number])
  let spark = ''
  if (kg.length > 1) {
    const lo = Math.min(...kg.map(([, k]) => k)) - 0.2
    const hi = Math.max(...kg.map(([, k]) => k)) + 0.2
    spark = kg.map(([, k], i) => `${fmt(6 + i * (188 / (kg.length - 1)), 0)},${fmt(34 - ((k - lo) / (hi - lo)) * 28, 0)}`).join(' ')
  }
  return { rows, kg_spark: spark, kg_range: kg.length ? `${pystr(kg[0][1])} → ${pystr(kg[kg.length - 1][1])}kg` : '' }
}

// ── 경과 비교 ──
type Fn = (r: Result) => number
const stride = (side: 'sL' | 'sR'): Fn => (r) => (hasM(r) ? r[side] : jround(r[side] * 1.5))
const _CMP: [string, string | null, Fn | null, string][] = [
  ['무릎 가동 범위', 'LH', (r) => r.j[0][1], '°'], ['무릎 가동 범위', 'RH', (r) => r.j[0][2], '°'],
  ['고관절 가동 범위', 'LH', (r) => r.j[1][1], '°'], ['고관절 가동 범위', 'RH', (r) => r.j[1][2], '°'],
  ['걸음 길이(등 길이 기준)', 'LH', stride('sL'), '%'], ['걸음 길이(등 길이 기준)', 'RH', stride('sR'), '%'],
  ['팔꿈치 가동 범위', 'LF', (r) => r.j[2][1], '°'], ['팔꿈치 가동 범위', 'RF', (r) => r.j[2][2], '°'],
  ['대칭 점수', null, (r) => r.sym, '점'], ['발 들림 높이(등 길이 기준)', 'LF', null, '%'],
]
const _TREND: Record<string, [Fn, Fn | null]> = {
  rom: [(r) => r.j[0][1], (r) => r.j[0][2]],
  stride: [stride('sL'), stride('sR')],
  stance: [
    (r) => (hasM(r) ? pyround(real.met(r.m, 'stance_ratio', 'LH') || 0) : 61),
    (r) => (hasM(r) ? pyround(real.met(r.m, 'stance_ratio', 'RH') || 0) : 61 - jround((r.sL - r.sR) / 2)),
  ],
  sym: [(r) => r.sym, null],
}
export const TREND_KEYS: [string, string][] = [['rom', '무릎 가동 범위'], ['stride', '걸음 길이'], ['stance', '입각기 비율'], ['sym', '대칭 점수']]

export function compare_view(acct: Account, d: Dog, mode: string, tk: string) {
  const vs = valid(acct, d.id).reverse() // 오래된 회차부터
  if (vs.length < 2) return { has: false as const, name: d.name }
  const t = vs[vs.length - 1]
  const b_id = base_of(acct, d)
  let b = mode === 'base' ? vs.find((r) => r.id === b_id) ?? null : vs[vs.length - 2]
  if (!b || b.id === t.id) b = vs[vs.length - 2]
  const order = sorted([..._CMP.entries()], ([i, p]) => [d.focus && p[1] === d.focus ? 0 : p[2] ? 1 : 2, i])
  const rows = order.map(([, [n, limb, fn, u]], i) => {
    const focus = !!d.focus && limb === d.focus
    const bt = i ? '1px solid #F2EFEA' : 'none'
    if (!fn) return { n, limb: LIMB[limb!], lc: '#5B6472', vals: '한쪽 회차에서 측정 불가', j: '비교 불가', bg: '#F4F2EE', c: '#5B6472', bt }
    if (!limb && (b.nosym || t.nosym)) return { n, limb: '전체', lc: '#5B6472', vals: '한쪽 회차에 대칭 점수 없음', j: '비교 불가', bg: '#F4F2EE', c: '#5B6472', bt }
    const bv = fn(b)
    const tv = fn(t)
    const df = tv - bv
    const in_range = Math.abs(df) <= 1
    return {
      n, limb: limb ? LIMB[limb] + (focus ? ' (관심 다리)' : '') : '전체',
      lc: focus ? '#B4501A' : '#5B6472', vals: `${bv}${u} → ${tv}${u}`,
      // 퍼센트 값끼리의 차이는 %p(백엔드 회차 비교 vet.ts serverCompareRows 와 같은 표기)
      j: in_range ? '범위 안' : df > 0 ? `▲ 증가 ${df}${u === '%' ? '%p' : u}` : `▼ 감소 ${-df}${u === '%' ? '%p' : u}`,
      bg: in_range ? '#F4F2EE' : '#EEE8DF', c: in_range ? '#5B6472' : '#1B2433', bt,
    }
  })
  const [left_fn, right_fn] = _TREND[tk] ?? _TREND.rom
  const tv = tk === 'sym' ? vs.filter((r) => !r.nosym) : vs // 대칭 점수 추이는 점수 있는 회차만
  const a_vals = tv.map(left_fn)
  const b_vals = right_fn ? tv.map(right_fn) : []
  const all_v = [...a_vals, ...b_vals]
  const mn = Math.min(...all_v) - 2
  const mx = Math.max(...all_v) + 2
  const X = (i: number) => jround(20 + i * (280 / Math.max(1, tv.length - 1)))
  const Y = (v: number) => jround(130 - ((v - mn) / (mx - mn)) * 110)
  return {
    has: true as const, name: d.name, baseLabel: mode === 'base' ? '기준 회차' : '직전 회차',
    baseDate: `${b.date}, ${sess_no(acct, b)}회차`, tDate: `${t.date}, ${sess_no(acct, t)}회차`,
    modelChanged: b.model !== t.model,
    modelMsg: `두 회차의 분석 모델이 달라요(${b.model} → ${t.model}). 분석 방식이 바뀌어 수치를 그대로 비교하기 어렵습니다.`,
    rows, tl: a_vals.map((v, i) => `${X(i)},${Y(v)}`).join(' '),
    tr: b_vals.map((v, i) => `${X(i)},${Y(v)}`).join(' '),
    dl: [...a_vals.map((v, i) => ({ x: X(i), y: Y(v), c: '#3B6FE0' })), ...b_vals.map((v, i) => ({ x: X(i), y: Y(v), c: '#E5604D' }))],
    xl: tv.map((r) => short(r.date)), two: right_fn !== null,
    focusNote: d.focus ? `관심 다리(${LIMB[d.focus]})를 맨 앞에 보여 드립니다.` : '위에서 관심 다리를 고르면 그 다리를 맨 앞에 보여 드립니다.',
  }
}
