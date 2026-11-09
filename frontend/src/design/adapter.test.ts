import { describe, expect, it } from 'vitest'

import type { CompareOut, LimbCompareOut, SessionHistoryItem, SessionResultOut } from '../api/types'
import { compareRows, symOf, toResult, type DDog } from './adapter'
import { delta, num, resultVals } from './shared'

const reason = (code: string, message: string) => ({ code, message })

function row(pair: 'FORE' | 'HIND', code: string, unit: LimbCompareOut['unit'], left: number | null, right: number | null, si: number | null): LimbCompareOut {
  const comparable = left != null && right != null
  return {
    pair, metric_code: code, unit, left, right, diff: comparable ? left! - right! : null, symmetry_index: si, comparable,
    reason: comparable ? null : reason('NO_PASS_FOR_LIMB', '이 방향 영상이 없어 잴 수 없어요'),
  }
}

const HIST: SessionHistoryItem = {
  id: 's1', measured_on: '2026-10-28', weight_kg: 28.1, status: 'DONE', is_baseline: false, valid_passes: { LEFT: 3, RIGHT: 2 },
  model_version: 'v1', reports: null,
}

function result(limb_compare: LimbCompareOut[]): SessionResultOut {
  return {
    id: 's1', dog_id: 'd1', staff: { id: 'u', name: '담당' }, measured_on: '2026-10-28', weight_kg: 28.1, size_class: 'LARGE', status: 'DONE',
    fail_reason: null, model_name: 'pga-pose', model_version: 'v1', completed_at: '2026-10-28T05:20:00Z', aggregated_at: null,
    created_at: '2026-10-28T05:00:00Z', pass_counts: { measured: 8, used: 5, excluded: 3 }, shot_counts: { total: 4, failed: 0, invalid: 0 },
    exclude_summary: [{ ...reason('RUNNING', '뛰었습니다'), count: 3 }], notices: [],
    gaits: [{ gait_type: 'TROT', metrics: [], limb_compare }],
  }
}

const ROWS = [
  row('HIND', 'rom_stifle', 'deg', 42.26, 38.04, 10.51),
  row('HIND', 'stride_length', 'pct_body', null, 40.2, null),     // 왼쪽 측정 불가
  row('HIND', 'stance_ratio', 'pct', 61.6, 58.4, 5.33),
  row('FORE', 'rom_elbow', 'deg', 52.04, 50.96, 2.1),
  row('FORE', 'paw_lift', 'pct_body', 12.4, null, null),            // 오른쪽 측정 불가
]
const DOG = { id: 'd1', name: '보리', breed: '골든 리트리버', birth: '2019', kg: '28.4' } as unknown as DDog

describe('회차 결과 표 (adapter.toResult)', () => {
  const R = toResult(HIST, 'd1', result(ROWS))
  const rows = R.rowsBy.trot

  it('각도는 소수 1자리, 비율은 정수로 반올림', () => {
    const st = rows.find((r) => r.code === 'rom_stifle')!
    expect([st.l, st.r]).toEqual([42.3, 38])
    const sr = rows.find((r) => r.code === 'stance_ratio')!
    expect([sr.l, sr.r]).toEqual([62, 58])
  })

  it('한쪽이라도 측정 불가면 비교 불가(na)로 두고 사유를 붙인다', () => {
    for (const code of ['stride_length', 'paw_lift']) {
      const r = rows.find((x) => x.code === code)!
      expect(r.na).toBe(true)
      expect(r.reason).toBe('이 방향 영상이 없어 잴 수 없어요')
    }
  })

  it('요약 수치는 측정 불가 항목을 0 으로 쓰지 않는다', () => {
    expect(R.sL).toBeNull()       // 걸음 길이 왼쪽 측정 불가 → 왼/오 모두 비움
    expect(R.sR).toBeNull()
    expect(R.rom).toBe(40)        // (42.3 + 38) / 2 반올림
  })

  it('대칭 지수는 비교 가능한 항목만 본다(가장 큰 좌우 차이 비율을 100 에서 뺌)', () => {
    expect(symOf(rows)).toBe(89)  // 100 − 10.51
    expect(symOf(rows.map((r) => ({ ...r, na: true })))).toBeNull()
  })

  it('결과를 아직 못 받은 회차는 수치가 비어 있다', () => {
    const empty = toResult(HIST, 'd1', null)
    expect([empty.sym, empty.rom, empty.sL, empty.sR]).toEqual([null, null, null, null])
    expect(empty.loaded).toBe(false)
  })
})

describe('결과 화면·보고서 문구 (shared.resultVals)', () => {
  const R = toResult(HIST, 'd1', result(ROWS))
  const ctx = { results: [R], dogById: () => DOG }
  const { rd, rp } = resultVals(ctx, R, 'trot')

  it('측정 불가 행은 숫자 대신 비우고 사유를 보여 준다', () => {
    const na = rd.rows.filter((x: { na: boolean }) => x.na)
    expect(na).toHaveLength(2)
    for (const x of na) expect([x.lv, x.rv, x.dv]).toEqual(['', '', ''])
    const rpNa = rp.rows.filter((x: { l: string }) => x.l === '측정 불가')
    expect(rpNa).toHaveLength(2)
    for (const x of rpNa) expect([x.r, x.d]).toEqual(['—', '—'])
  })

  it('걸음 길이 요약이 측정 불가면 — 와 "측정 불가"', () => {
    expect([rd.sL, rd.sR, rd.stD]).toEqual(['—', '—', '측정 불가'])
    expect(rp.items.find((i: { k: string }) => i.k.startsWith('걸음 길이')).v).toBe('측정 불가')
  })

  it('좌우 차이 지수는 소수 1자리, 각도 차이는 소수 1자리', () => {
    expect(rd.topSub).toContain('대칭 지수 차이 10.5%')
    expect(rd.topSub).toContain('차이 4.3°')
  })

  it('직전 회차가 없으면 "첫 측정", 값이 없으면 "측정 불가"', () => {
    expect(delta(80, undefined, '%p')[0]).toBe('첫 측정')
    expect(delta(null, 80, '%p')[0]).toBe('측정 불가')
    expect(delta(82.04, 80, '%p')[0]).toBe('직전 대비 +2%p')
    expect(num(null)).toBe('—')
    expect(num(0)).toBe(0)
  })
})

describe('보행 유형 미판별(OTHER)·유효 통과 0건 회차', () => {
  const ctxOf = (R: ReturnType<typeof toResult>) => ({ results: [R], dogById: () => DOG })

  it('OTHER 묶음만 있으면 그 표를 쓰고, 제목은 "보행 유형 미판별"', () => {
    const r = result(ROWS)
    r.gaits = [{ gait_type: 'OTHER', metrics: [], limb_compare: ROWS }]
    const R = toResult(HIST, 'd1', r)
    expect(R.rowsBy.other).toHaveLength(5)
    expect(R.sym).not.toBeNull()
    for (const g of ['trot', 'walk'] as const) {
      const { rd } = resultVals(ctxOf(R), R, g)
      expect(rd.rows).toHaveLength(5)
      expect(rd.gaitName).toBe('보행 유형 미판별')
    }
  })

  it('속보 표가 있으면 속보가 먼저', () => {
    const r = result(ROWS)
    r.gaits.push({ gait_type: 'OTHER', metrics: [], limb_compare: ROWS.slice(0, 1) })
    const R = toResult(HIST, 'd1', r)
    expect(resultVals(ctxOf(R), R, 'trot').rd.gaitName).toBe('속보')
  })

  it('유효 통과 0건이면 실패(다시 촬영)로, 제외 사유를 함께 보여 준다', () => {
    const r = result([])
    r.gaits = []
    r.pass_counts = { measured: 3, used: 0, excluded: 3 }
    const R = toResult(HIST, 'd1', r)
    expect(R.st).toBe('fail')
    const { rd } = resultVals(ctxOf(R), R, 'trot')
    expect(rd.fail).toBe(true)
    expect(rd.ok).toBe(false)
    expect(rd.failMsg).toContain('다시 찍어 주세요')
    expect(rd.ex).toEqual([{ n: '뛰었습니다', c: 3 }])
  })

  it('서버 실패(FAILED)면 촬영 안내 대신 실패 문구', () => {
    const R = toResult({ ...HIST, status: 'FAILED' }, 'd1', null)
    expect(R.st).toBe('fail')
    const { rd } = resultVals(ctxOf(R), R, 'trot')
    expect(rd.failMsg).toBe('분석에 실패했습니다. 잠시 후 다시 시도해 주세요.')
    expect(rd.failMsg).not.toContain('다시 찍어')
  })
})

describe('경과 비교 표 (adapter.compareRows)', () => {
  const cmp = {
    dog_id: 'd1', base: { session_id: 'a', measured_on: '2026-10-01', model_version: 'v1', kind: 'BASELINE' },
    target: { session_id: 'b', measured_on: '2026-10-28', model_version: 'v1' },
    items: [
      { metric_code: 'rom_stifle', limb: 'RH', gait_type: 'TROT', unit: 'deg', base_value: 36.04, target_value: 40.26, diff: 4.22, judgement: 'INCREASE', note: null },
      { metric_code: 'paw_lift', limb: 'LF', gait_type: 'TROT', unit: 'pct_body', base_value: null, target_value: 12, diff: null, judgement: 'NOT_COMPARABLE', note: reason('NO_BASE', '기준 회차에서 잴 수 없었어요') },
      { metric_code: 'rom_hip', limb: 'LH', gait_type: 'TROT', unit: 'deg', base_value: 30, target_value: 31.2, diff: 1.2, judgement: 'UNKNOWN', note: null },
    ],
  } as unknown as CompareOut

  it('한쪽 회차 값이 없으면 숫자 없이 비교 불가와 사유', () => {
    const r = compareRows(cmp, null).find((x) => x.n === '발 높이')!
    expect(r.j).toBe('비교 불가')
    expect(r.vals).toBe('기준 회차에서 잴 수 없었어요')
    expect(r.vals).not.toMatch(/\b0\b/)
  })

  it('판단 보류 항목은 값은 보여 주되 증감 판정은 하지 않는다', () => {
    const r = compareRows(cmp, null).find((x) => x.n === '고관절 가동 범위')!
    expect(r.j).toBe('판단 보류')
    expect(r.vals).toBe('30°→ 31.2°'.replace('°→', '° →'))
  })

  it('관심 다리 항목이 맨 위로', () => {
    expect(compareRows(cmp, 'LH')[0].n).toBe('고관절 가동 범위')
  })
})
