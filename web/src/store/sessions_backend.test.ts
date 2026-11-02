import { describe, expect, it } from 'vitest'

import type { MetricOut, SessionResultOut } from '../api/client'
import { toResult } from './sessions_backend'

const metric = (metric_code: string, limb: string, value: number | null): MetricOut => ({
  metric_code, limb, value, unit: 'deg', measurable: value != null, unmeasurable_reason: null, n_passes: 3,
})

const METRICS = [
  metric('rom_stifle', 'LH', 40), metric('rom_stifle', 'RH', 30), metric('rom_hip', 'LH', 20), metric('rom_hip', 'RH', 20),
  metric('rom_elbow', 'LF', 50), metric('rom_elbow', 'RF', 50), metric('stride_length', 'LH', 41), metric('stride_length', 'RH', 39),
  metric('walk_speed', 'NONE', 1.2),
]

function out(over: Partial<SessionResultOut> = {}): SessionResultOut {
  return {
    id: 's1', dog_id: 'd1', staff: { id: 'u', name: '담당' }, measured_on: '2026-11-02', weight_kg: 12.3, size_class: 'MEDIUM',
    status: 'DONE', fail_reason: null, model_name: 'pga-pose', model_version: 'v1', created_at: '2026-11-02T05:00:00Z',
    completed_at: '2026-11-02T05:20:00Z', pass_counts: { measured: 6, used: 4, excluded: 2 }, shot_counts: { total: 3, failed: 0, invalid: 0 },
    exclude_summary: [{ code: 'RUNNING', message: '뛰었습니다', count: 2 }], notices: [],
    gaits: [{ gait_type: 'OTHER', metrics: METRICS, limb_compare: [] }],
    ...over,
  }
}

describe('백엔드 회차 결과 → 화면 결과 (sessions_backend.toResult)', () => {
  it('OTHER 묶음만 있으면 그 수치를 쓰고 이름은 "보행 유형 미판별"', () => {
    const r = toResult(out(), 'd1')
    expect(r.st).toBe('ok')
    expect(r.gait).toBe('보행 유형 미판별')
    expect(r.m.LH.rom_stifle).toBe(40)
    expect(r.m.NONE).toBeUndefined()
    expect(r.j[0]).toEqual(['무릎', 40, 30])
    expect([r.sL, r.sR]).toEqual([41, 39])
    expect(r.ps).toEqual([6, 4])
    expect(r.ex).toEqual([['뛰었습니다', 2]])
  })

  it('속보 묶음이 있으면 속보가 먼저', () => {
    const r = toResult(out({ gaits: [{ gait_type: 'OTHER', metrics: METRICS, limb_compare: [] }, { gait_type: 'TROT', metrics: METRICS.slice(0, 2), limb_compare: [] }] }), 'd1')
    expect(r.gait).toBe('속보')
  })

  it('유효 통과 0건이면 실패로 두고 제외 사유를 싣는다', () => {
    const r = toResult(out({ gaits: [], pass_counts: { measured: 3, used: 0, excluded: 3 } }), 'd1')
    expect(r.st).toBe('fail')
    expect(r.ex).toEqual([['뛰었습니다', 2]])
    expect(r.gait).toBeUndefined()
  })

  it('분석 실패면 서버 사유 문구를 싣는다', () => {
    const r = toResult(out({ status: 'FAILED', fail_reason: { code: 'AGGREGATION_FAILED', message: '수치를 계산하지 못했어요' }, gaits: [] }), 'd1')
    expect(r.st).toBe('fail')
    expect(r.fail_msg).toBe('수치를 계산하지 못했어요')
    expect(toResult(out({ status: 'FAILED', gaits: [] }), 'd1').fail_msg).toBe('분석에 실패했어요. 잠시 후 다시 시도해 주세요.')
  })

  it('유효 통과 0건(DONE)은 화면 기본 촬영 안내를 쓴다(따로 문구를 싣지 않음)', () => {
    expect(toResult(out({ gaits: [], pass_counts: { measured: 3, used: 0, excluded: 3 } }), 'd1').fail_msg).toBeUndefined()
  })

  it('무효 촬영이 있으면 일부 유효', () => {
    expect(toResult(out({ shot_counts: { total: 3, failed: 0, invalid: 1 } }), 'd1').st).toBe('part')
  })
})
