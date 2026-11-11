/**
 * 웹·앱 로직이 같이 쓰는 디자인 상수·계산. 원본 프로토타입의 함수들을 API 값(adapter) 위에서 돌게 옮긴 것.
 */
import { ApiError } from '../api/client'
import { BREEDS } from '../api/labels'
import { ST, allShotsFailed, type DDog, type DGait, type DRes, type DRow, type DRowsKey, type DSize } from './adapter'

const SMALLB = ['말티즈', '푸들', '토이 푸들', '포메라니안', '시츄', '치와와', '비숑 프리제', '요크셔테리어', '닥스훈트', '미니어처 슈나우저', '퍼그', '이탈리안 그레이하운드', '잭 러셀 테리어']
const LARGEB = ['골든 리트리버', '래브라도 리트리버', '사모예드', '시베리안 허스키', '저먼 셰퍼드', '말라뮤트', '알래스칸 말라뮤트', '풍산개']
/** 디자인의 체급 미리보기(견종 → 체중). 저장은 서버가 체중으로 정한다 */
export const autoSize = (breed: string, kg: string): DSize => (SMALLB.includes(breed) ? 'S' : LARGEB.includes(breed) ? 'L' : BREEDS.includes(breed) && breed !== '믹스견' ? 'M' : +kg ? (+kg < 10 ? 'S' : +kg < 25 ? 'M' : 'L') : 'M')
export const SEX = { m: '수컷', f: '암컷', mn: '수컷(중성화)', fs: '암컷(중성화)' } as const
export const SIZE = { S: '소형', M: '중형', L: '대형' } as const
export const LIMB = { LF: '왼앞', RF: '오른앞', LH: '왼뒤', RH: '오른뒤' } as const
export type PetForm = { name: string; breed: string; birth: string; kg: string; sex: keyof typeof SEX; size: DSize | null; rehab: string; focus: keyof typeof LIMB | null; memo: string; base: string | null }
export const EMPTY_PET: PetForm = { name: '', breed: '', birth: '', kg: '', sex: 'm', size: null, rehab: '', focus: null, memo: '', base: null }
export const fmtD = (iso: string) => { const p = (iso || '').split('-'); return p.length === 3 ? `${p[0]}년 ${+p[1]}월 ${+p[2]}일` : iso }
export const short = (d: string) => d.replace('월 ', '.').replace('일', '')
const gs = (p: number, c: number, w: number) => Math.exp(-(((p - c) / w) ** 2))
/** 뒷무릎 각도 곡선(디자인 320×150 뷰박스). depth 가 클수록 깊게 굽힌다 */
export const knee = (depth: number) => { const s: string[] = []; for (let i = 0; i <= 40; i++) { const p = i / 40; const a = 150 - 16 * gs(p, 0.12, 0.07) - depth * gs(p, 0.7, 0.11); s.push(`${(24 + p * 286).toFixed(1)},${(130 - ((a - 90) / 60) * 110).toFixed(1)}`) } return s.join(' ') }
export const errMsg = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback)
export const PREP = '이 기능은 준비 중입니다'
/** 다리 비교 요약 제목에 붙는 보행 묶음 이름. OTHER 묶음은 '기타 보행'이 아니라 아직 유형을 가르지 않은 통과들이다 */
export const GAIT_GROUP_NAME: Record<DRowsKey, string> = { walk: '평보', trot: '속보', other: '보행 유형 미판별' }
/** 분석은 끝났지만 쓸 수 있는 통과가 0건인 회차(DONE·used 0)의 촬영 안내 */
export const NO_VALID_MSG = '쓸 수 있는 통과가 없었습니다. 반려견이 뛰지 않고, 멈추거나 앉지 않고, 일직선으로 걷도록 다시 찍어 주세요.'
/** 서버 쪽 실패(FAILED, 예: 집계 오류). 반려견 탓이 아니므로 촬영 안내를 하지 않는다 */
export const SERVER_FAIL_MSG = '분석에 실패했습니다. 잠시 후 다시 시도해 주세요.'
/** 회차는 끝났지만 영상이 전부 분석 서버에서 실패(보내지 못함·시간 초과·분석 실패). 영상 문제가 아니므로 다시 찍으라고 하지 않는다 */
export const SHOTS_FAILED_MSG = '분석 서버가 영상을 처리하지 못했습니다. 영상 문제가 아니니 다시 찍지 말고, 잠시 후 다시 분석해 주세요.'
export const r1 = (v: number) => Math.round(v * 10) / 10
export const num = (v: number | null | undefined) => (v == null ? '—' : v)
/** 회차 체중 문구. 그날 체중을 안 적은 회차(weight_kg null → '-')는 '-kg' 대신 측정 불가 표기 */
export const wkg = (w: string) => (w && w !== '-' ? `체중 ${w}kg` : '체중 —')
export const desc = (d: DDog) => [d.breed || '견종 미입력', d.birth ? d.birth + '년생' : null, d.kg ? d.kg + 'kg' : null].filter(Boolean).join(' · ')
export const chk = (on: boolean) => (on ? '#D2601A' : '#C9C4BC')
export const pickSt = (on: boolean) => ({ bd: on ? '#D2601A' : '#ECE8E2', bg: on ? '#FCEEE3' : '#fff', c: on ? '#A8481A' : '#3A4250' })
export const seg = (list: [string, string][], cur: string, set: (k: string) => void) => list.map(([k, label]) => { const on = cur === k; return { label, bg: on ? '#fff' : 'transparent', c: on ? '#1B2433' : '#5B6472', sh: on ? '0 1px 3px rgba(27,36,51,.12)' : 'none', pick: () => set(k) } })

/** 디자인 pet 폼 → API 등록·수정 본문. 체급은 직접 고른 때만 보낸다 */
export function petBody(pet: PetForm) {
  const kg = Number(pet.kg)
  return {
    name: pet.name.trim(), breed: pet.breed.trim(), weight_kg: kg,
    size_class: pet.size ? ({ S: 'SMALL', M: 'MEDIUM', L: 'LARGE' } as const)[pet.size] : null,
    birth_year: pet.birth ? Number(pet.birth) : null,
    sex: ({ m: 'MALE', f: 'FEMALE', mn: 'MALE_NEUTERED', fs: 'FEMALE_SPAYED' } as const)[pet.sex],
    rehab_start_date: pet.rehab || null, focus_limb: pet.focus, memo: pet.memo || null,
  }
}

export interface ResultCtx {
  results: DRes[]
  dogById: (id: string) => DDog | undefined
}

export function sessNo(ctx: ResultCtx, R: DRes) { const all = ctx.results.filter((r) => r.dog === R.dog); return all.length - all.findIndex((r) => r.id === R.id) }
export const valid = (ctx: ResultCtx, dogId: string) => ctx.results.filter((r) => r.dog === dogId && r.st !== 'fail')
export const baseOf = (ctx: ResultCtx, d: DDog) => (d.base && ctx.results.find((r) => r.id === d.base && r.st !== 'fail') ? d.base : (valid(ctx, d.id).slice(-1)[0] || ({} as Partial<DRes>)).id)

/** 직전 회차 대비 문구. [문구, 색] */
export function delta(a: number | null, b: number | null | undefined, unit: string): [string, string] {
  if (a == null) return ['측정 불가', '#8E949C']
  if (b == null) return ['첫 측정', '#8E949C']
  const d = r1(a - b)
  return [d > 0 ? `직전 대비 +${d}${unit}` : d < 0 ? `직전 대비 −${-d}${unit}` : '직전과 같음', '#5B6472']
}

/** 회차 결과(rd)와 보고서(rp) 값. 디자인 원본의 계산을 API 표 위에서 한다 */
export function resultVals(ctx: ResultCtx, R: DRes | undefined, G: DGait) {
  let rd: any = { ok: false, fail: false, part: false, rows: [], rank: [], ex: [], name: '', desc: '', when: '', st: '', bg: '', c: '', topTitle: '', topSub: '', failMsg: '', gaitName: '' }
  let rp: any = { title: '', when: '', summary: '', items: [], rows: [], cond: '' }
  if (!R) return { rd, rp }
  const d = ctx.dogById(R.dog) || ({ name: '-', breed: '', birth: '', kg: '' } as DDog), stt = ST[R.st]
  rd = { ...rd, name: d.name, desc: desc(d), when: `${R.date} · ${sessNo(ctx, R)}회차 · ${wkg(R.w)}`, st: stt[0], bg: stt[1], c: stt[2], fail: R.st === 'fail', ok: R.st !== 'fail', part: R.st === 'part',
    failMsg: R.status === 'FAILED' ? R.result?.fail_reason?.message || SERVER_FAIL_MSG : allShotsFailed(R.result) ? SHOTS_FAILED_MSG : NO_VALID_MSG, ex: R.ex.map(([n, c]) => ({ n, c })) }
  if (R.st === 'fail') return { rd, rp }
  const vv = valid(ctx, R.dog), idx = vv.findIndex((x) => x.id === R.id), P = vv[idx + 1]
  // 고른 보행에 표가 없으면 속보 → 평보 → 미판별(OTHER) 순으로 있는 표를 쓴다. gaitKey 는 실제로 보여 준 묶음
  const gaitKey: DRowsKey = R.rowsBy[G].length ? G : R.rowsBy.trot.length ? 'trot' : R.rowsBy.walk.length ? 'walk' : 'other'
  const rows: DRow[] = R.rowsBy[gaitKey]
  const rowsT = R.rowsBy.trot.length ? R.rowsBy.trot : R.rowsBy.walk.length ? R.rowsBy.walk : R.rowsBy.other
  const rank = (rs: DRow[]) => rs.filter((x) => !x.na).map((x) => ({ ...x, df: r1(Math.abs(x.l - x.r)) })).sort((a, b) => b.si - a.si)
  const meas = rank(rows), top = meas[0], topT = rank(rowsT)[0]
  const sL = R.sL, sR = R.sR
  const sd = delta(R.sym, P && P.sym, '점'), rdl = delta(R.rom, P && P.rom, '°')
  const stifle = rowsT.find((x) => x.code === 'rom_stifle')
  const model = `${R.result?.model_name ?? 'pga-pose'} ${R.model}`
  Object.assign(rd, {
    gaitName: GAIT_GROUP_NAME[gaitKey],
    sym: num(R.sym), symD: sd[0], symDC: sd[1], rom: num(R.rom), romD: rdl[0], romDC: rdl[1], sL: num(sL), sR: num(sR),
    stD: sL == null || sR == null ? '측정 불가' : sL === sR ? '좌우 같음' : `${sL > sR ? '오른쪽' : '왼쪽'}이 ${Math.abs(sL - sR)}%p 짧음`, stC: '#5B6472',
    topTitle: top ? `${top.leg} ${top.n}에서 좌우 차이가 가장 큽니다` : R.loaded ? '좌우를 비교할 수 있는 항목이 없습니다' : '결과를 불러오는 중입니다',
    topSub: top ? `왼 ${top.l}${top.u} · 오 ${top.r}${top.u} · 차이 ${top.df}${top.u} · 대칭 지수 차이 ${top.si.toFixed(1)}%` : '',
    rank: [...meas.slice(1, 4).map((x) => ({ n: `${x.leg} · ${x.n}`, v: `차이 ${x.df}${x.u}`, c: '#fff' })), ...rows.filter((x) => x.na).map((x) => ({ n: `${x.leg} · ${x.n}`, v: '비교 불가', c: 'rgba(255,255,255,.5)' }))],
    rows: rows.map((x) => ({ sec: x.sec || false, ok: !x.na, na: !!x.na, n: x.n, reason: x.reason || '', lv: x.na ? '' : x.l + x.u, rv: x.na ? '' : x.r + x.u, dv: x.na ? '' : r1(Math.abs(x.l - x.r)) + x.u })),
    pm: R.ps[0], pu: R.ps[1], px: R.ps[0] - R.ps[1], ex: R.ex.map(([n, c]) => ({ n, c })), model,
    kL: knee((stifle && !stifle.na ? stifle.l : 60) * 0.8), kR: knee((stifle && !stifle.na ? stifle.r : 55) * 0.8),
  })
  rp = {
    title: `${d.name}의 걸음 보고서`, when: `${R.date} 측정 · ${sessNo(ctx, R)}회차 · ${desc(d)}`,
    summary: topT ? `${topT.leg} ${topT.n}에서 왼쪽과 오른쪽 차이가 가장 컸습니다(${topT.df}${topT.u}). 수의사 선생님과 함께 확인해 보세요.` : '좌우를 비교할 수 있는 항목이 없습니다. 수의사 선생님과 함께 확인해 보세요.',
    items: [
      { k: '좌우 대칭 점수', v: num(R.sym) + '점', d: P ? `직전 ${num(P.sym)}점` : '첫 측정' },
      { k: '뒷무릎 움직임 범위', v: stifle && !stifle.na ? `왼 ${stifle.l}° · 오 ${stifle.r}°` : '측정 불가', d: stifle && !stifle.na ? `차이 ${r1(Math.abs(stifle.l - stifle.r))}°` : '' },
      { k: '걸음 길이(등 길이 대비)', v: sL != null && sR != null ? `왼 ${sL}% · 오 ${sR}%` : '측정 불가', d: sL != null && sR != null ? `차이 ${Math.abs(sL - sR)}%p` : '' },
    ],
    rows: [...rowsT.map((x) => ({ n: x.n, l: x.na ? '측정 불가' : x.l + x.u, r: x.na ? '—' : x.r + x.u, d: x.na ? '—' : r1(Math.abs(x.l - x.r)) + x.u })), { n: '대칭 점수', l: '—', r: '—', d: num(R.sym) + '점' }].map((x, i) => ({ ...x, bg: i % 2 ? '#fff' : '#FAF8F5' })),
    cond: `측면 가로 촬영 · 영상 ${R.result?.shot_counts.total ?? '-'}개 · 통과 ${R.ps[0]}개 중 ${R.ps[1]}개 사용 · 분석 모델 ${model}. 측정 불가 항목은 사유와 함께 표시했습니다.`,
  }
  return { rd, rp }
}
