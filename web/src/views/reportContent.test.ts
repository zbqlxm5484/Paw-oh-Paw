import { describe, expect, it } from 'vitest'
import type { ReportContentCompare, ReportContentGait, ReportContentOut } from '../api/client'
import type { ClipInfo, GaitClip } from './gaitClip'
import {
  baselineDiff, cardGait, isWeak, kneeChartView, kneeFromClip, legCard, legFills, levelOf, LEVEL_STYLE, paintBody, pairViews, pickGait, symLevel, trendPoints,
} from './reportContent'

const line = (pair: string, code: string, diff: number | null, si: number | null, comparable = true): ReportContentCompare => ({
  pair, pair_label: pair === 'FORE' ? '앞다리' : '뒷다리', metric_code: code, label: code, left: 'L', right: 'R', diff: 'D',
  symmetry_index: si == null ? '-' : `${si}%`, diff_value: diff, symmetry_value: si, comparable, reason: comparable ? null : '사유',
})

const gait = (gait_type: string, compare: ReportContentCompare[] = []): ReportContentGait => ({
  gait_type, label: gait_type, notes: [], compare, changes: [],
  rows: [
    { metric_code: 'rom_elbow', label: '팔꿈치 가동 범위', unit: 'deg', cells: { LF: { value: 54, text: '54.0°', reason: null }, RF: { value: 38.9, text: '38.9°', reason: null } } },
    { metric_code: 'rom_stifle', label: '무릎 가동 범위', unit: 'deg', cells: { LH: { value: 99.6, text: '99.6°', reason: null }, RH: { value: 85.2, text: '85.2°', reason: null } } },
    { metric_code: 'rom_hip', label: '고관절 가동 범위', unit: 'deg', cells: { LH: { value: 41.2, text: '41.2°', reason: null }, RH: { value: 28, text: '28.0°', reason: null } } },
    { metric_code: 'paw_lift', label: '발 들림 높이', unit: 'pct_body', cells: { LH: { value: 18.4, text: '18.40%', reason: null }, RH: { value: 22.2, text: '22.20%', reason: null } } },
  ],
})

function content(over: Partial<ReportContentOut> = {}): ReportContentOut {
  return {
    session_id: 's3', edition: 'OWNER', template_version: '0.5',
    session: { measured_on: '2026-11-09', round: 3, model_name: 'pga-pose', model_version: 'v1', weight_kg: 6.1, size_class: 'SMALL', symmetry_score: 76 },
    dog: { name: '콩이', breed: '말티즈', sex: 'MALE', birth_year: 2020, focus_limb: 'RH' },
    previous: null, baseline: null, history: [],
    sentences: { title: '콩이 보행 평가 보고서', edition_label: '보호자용', intro: '', summary: [], previous_note: null, previous_gaps: [], caution: [], glossary: [], disclaimer: '' },
    gaits: [], ...over,
  }
}

describe('보고서 내용 → 인쇄 종이 값', () => {
  it('보행 유형은 속보 → 평보 → 미판별 순으로 있는 것을 고른다', () => {
    expect(pickGait([gait('OTHER'), gait('WALK'), gait('TROT')])!.gait_type).toBe('TROT')
    expect(pickGait([gait('OTHER'), gait('WALK')])!.gait_type).toBe('WALK')
    expect(pickGait([gait('OTHER')])!.gait_type).toBe('OTHER')
    expect(pickGait([])).toBeNull()
  })

  it('legs 가 없으면 compare 의 대칭 지수 최대인 줄로 단계·덜 쓰는 다리를 정한다', () => {
    const g = gait('TROT', [
      line('HIND', 'rom_stifle', 14.4, 15.58), line('HIND', 'rom_hip', 13.2, 38.15), line('HIND', 'paw_lift', -3.8, 18.7),
      line('FORE', 'rom_elbow', 15.1, 32.5), line('FORE', 'rom_carpus', null, null, false),
    ])
    const pv = pairViews(content({ gaits: [g] }), g)
    expect(pv.HIND).toMatchObject({ level: 'LARGE', metric_code: 'rom_hip', weak: 'RH', server: false }) // 왼 − 오 > 0 → 오른쪽이 작다
    expect(pv.FORE).toMatchObject({ level: 'LARGE', metric_code: 'rom_elbow', weak: 'RF' })
    const near = gait('TROT', [line('HIND', 'rom_stifle', -2, 4.9), line('FORE', 'rom_elbow', -3, 7)])
    const pn = pairViews(content(), near)
    expect(pn.HIND).toMatchObject({ level: 'SIMILAR', weak: 'LH' })
    expect(pn.FORE).toMatchObject({ level: 'SLIGHT', weak: 'LF' })
    // 비슷하면 그림에 덜 쓰는 다리로 칠하지 않는다
    expect(isWeak(pn, 'LH')).toBe(false)
    expect(isWeak(pn, 'LF')).toBe(true)
    expect(legFills(pn)).toEqual({ LF: LEVEL_STYLE.SLIGHT.fill, RF: '#E9E4DC', LH: LEVEL_STYLE.SIMILAR.fill, RH: LEVEL_STYLE.SIMILAR.fill })
  })

  it('diff_value 가 없으면 표의 두 값으로 작은 쪽을 고른다', () => {
    const g = gait('TROT', [{ ...line('HIND', 'rom_stifle', null, 15.58) }])
    expect(pairViews(content(), g).HIND.weak).toBe('RH')
  })

  it('서버 legs(새 모양)가 있으면 그대로 쓰고, 빠진 쌍은 단계 없음', () => {
    const g = gait('TROT', [line('HIND', 'rom_hip', 13.2, 38.15), line('HIND', 'rom_stifle', 14.4, 15.58), line('FORE', 'rom_elbow', 15.1, 32.5)])
    const c = content({
      gaits: [g],
      legs: [{ pair: 'HIND', gait_type: 'TROT', metric_code: 'rom_stifle', label: '무릎 가동 범위', symmetry_index: '15.6%', symmetry_value: 15.58, weak_limb: 'LH', level: 'SLIGHT' }],
    })
    const pv = pairViews(c, g)
    expect(pv.HIND).toMatchObject({ level: 'SLIGHT', weak: 'LH', metric_code: 'rom_stifle', server: true })
    expect(pv.HIND.line!.metric_code).toBe('rom_stifle')
    // 앞다리는 compare 에 줄이 있어도 서버가 legs 에서 뺐으면 단계 없음(화면이 대신 정하지 않는다)
    expect(pv.FORE).toMatchObject({ level: null, line: null, server: true })
  })

  it('다리 카드 보행 유형: legs[0].gait_type, legs 가 없으면 TROT → WALK → OTHER 중 비교할 수 있는 첫 유형', () => {
    const trotNo = gait('TROT', [line('HIND', 'rom_hip', null, null, false)])
    const walk = gait('WALK', [line('HIND', 'rom_hip', 3, 8.2)])
    const other = gait('OTHER', [line('HIND', 'rom_hip', 3, 12)])
    expect(cardGait(content({ gaits: [other, walk, trotNo] }))!.gait_type).toBe('WALK')
    expect(cardGait(content({ gaits: [other, trotNo] }))!.gait_type).toBe('OTHER')
    // 비교할 수 있는 유형이 없으면 순서상 첫 유형
    expect(cardGait(content({ gaits: [gait('OTHER'), trotNo] }))!.gait_type).toBe('TROT')
    const leg = { pair: 'HIND' as const, gait_type: 'OTHER', metric_code: 'rom_hip', label: '', symmetry_index: '12.0%', symmetry_value: 12, weak_limb: 'RH' as const, level: 'LARGE' as const }
    expect(cardGait(content({ gaits: [other, walk], legs: [leg] }))!.gait_type).toBe('OTHER')
  })

  it('단계 경계는 소수 첫째 자리로 반올림한 값으로 가른다', () => {
    expect(levelOf(4.94)).toBe('SIMILAR')
    expect(levelOf(4.95)).toBe('SLIGHT') // 화면에는 5.0%
    expect(levelOf(9.949)).toBe('SLIGHT')
    expect(levelOf(9.95)).toBe('LARGE') // 화면에는 10.0%
    const g = gait('TROT', [line('HIND', 'rom_stifle', -2, 4.96), line('FORE', 'rom_elbow', -3, 9.96)])
    const pv = pairViews(content(), g)
    expect(pv.HIND.level).toBe('SLIGHT')
    expect(pv.FORE.level).toBe('LARGE')
  })

  it('다리 카드 값은 rows 의 칸 글 그대로(보호자용 = 단계를 정한 수치 하나, 수의사용 = 가동 범위 등)', () => {
    const g = gait('TROT', [line('HIND', 'rom_hip', 13.2, 38.15), line('FORE', 'rom_elbow', 15.1, 32.5)])
    const pv = pairViews(content(), g)
    expect(legCard(g, 'RH', 'OWNER', pv)).toEqual([{ n: '고관절 가동 범위', v: '28.0°', other: '41.2°', lower: true }])
    expect(legCard(g, 'LF', 'OWNER', pv)).toEqual([{ n: '팔꿈치 가동 범위', v: '54.0°', other: '38.9°', lower: false }])
    // 수의사용: 발 들림 높이처럼 카드에 안 싣는 수치는 뺀다
    expect(legCard(g, 'LH', 'VET', pv).map((m) => m.v)).toEqual(['99.6°', '41.2°'])
  })

  it('기준 회차 차이: baseline.diff, 없으면 점수 차이, 이번 회차가 기준이면 없음', () => {
    const b = { session_id: 's1', measured_on: '2026-10-01', round: 1, symmetry_score: 70 }
    expect(baselineDiff(content({ baseline: { ...b, diff: 5 } }))).toBe(5)
    expect(baselineDiff(content({ baseline: b }))).toBe(6)
    expect(baselineDiff(content({ baseline: { ...b, session_id: 's3' } }))).toBeNull()
    expect(baselineDiff(content())).toBeNull()
    // 서버가 null 을 주면(한쪽 점수 없음) 화면이 계산하지 않는다
    expect(baselineDiff(content({ baseline: { ...b, diff: null } }))).toBeNull()
  })

  it('대칭 점수 색 단계: symmetry_level, 없으면 100 − 점수', () => {
    expect(symLevel(content())).toBe('LARGE') // 100 − 76 = 24
    expect(symLevel(content({ session: { ...content().session, symmetry_score: 93 } }))).toBe('SLIGHT')
    expect(symLevel(content({ session: { ...content().session, symmetry_level: 'SIMILAR' } }))).toBe('SIMILAR')
  })

  it('history → 추세 점: 실패 회차(null)는 빼고 이번 회차를 표시', () => {
    const pts = trendPoints([
      { measured_on: '2026-10-01', round: 1, symmetry_score: 70 },
      { measured_on: '2026-10-15', round: 2, symmetry_score: null },
      { measured_on: '2026-11-09', round: 3, symmetry_score: 76 },
    ], 3)
    expect(pts).toEqual([
      { x: 30, y: 64, v: 70, t: '10.1', cur: false },
      { x: 330, y: 32, v: 76, t: '11.9', cur: true },
    ])
    expect(trendPoints([], 1)).toEqual([])
  })

  it('몸 그림: 다리 색과 관심 다리 점선', () => {
    const svg = ['front_left', 'front_right', 'hind_left', 'hind_right'].map((id) => `<path id="${id}" fill="#E9E4DC" stroke="#B8B0A4" stroke-width="2"/>`).join('')
    const out = paintBody(svg, { LF: '#a', RF: '#b', LH: '#c', RH: '#d' }, 'RH')
    expect(out).toContain('<path id="front_left" fill="#a" stroke="#B8B0A4" stroke-width="2"')
    expect(out).toContain('<path id="hind_right" fill="#d" stroke="#D2601A" stroke-width="6" stroke-dasharray="14 8"')
  })

  it('무릎 곡선: 실제 곡선만, 반대쪽에서 빌려 온 쪽은 뺀다', () => {
    const a = Array.from({ length: 50 }, (_, i) => 100 + 30 * Math.sin((i / 50) * 2 * Math.PI))
    const b = a.map((v) => v - 5)
    const info = (o: Partial<ClipInfo>): ClipInfo => ({ gait: 'OTHER', sides: ['L', 'R'], mirrored: [], borrowed: [], strides: 6, shots: 2, passes: 4, ...o })
    const clip = (l: number[], r: number[]): GaitClip => ({ legs: { LH: { joint: { 무릎: l } }, RH: { joint: { 무릎: r } } } })
    expect(kneeFromClip(clip(a, b), info({}))).toMatchObject({ L: a, R: b })
    // 오른쪽 촬영이 없어 왼쪽을 비춘 경우 → 오른쪽 선은 없음
    expect(kneeFromClip(clip(a, a), info({ sides: ['L'], mirrored: ['R'] }))).toMatchObject({ L: a, R: null })
    // 오른쪽 무릎만 걸음을 못 잘라 빌려 온 경우(같은 배열)
    expect(kneeFromClip(clip(a, a), info({ borrowed: ['R'] }))).toMatchObject({ L: a, R: null })
    expect(kneeFromClip(clip(a, a), info({ borrowed: ['L', 'R'] }))).toBeNull()
    const kc = kneeChartView({ gait: 'OTHER', L: a, R: null, strides: 6 })
    expect(kc.L.split(' ')).toHaveLength(50)
    expect(kc.R).toBe('')
    expect(kc.y.map((t) => t.t)[0]).toMatch(/°$/)
  })
})
