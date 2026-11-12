import { describe, expect, it } from 'vitest'
import type { CompareOut } from '../api/client'
import { geom, judgeFromServer, judgeLocal, profileFromServer } from './changeProfile'

describe('변화 프로필 판정', () => {
  it('오차 범위보다 크면 증가·감소, 경계값은 범위 안, 범위가 없으면 값만', () => {
    expect(judgeLocal(9.4, 8)).toBe('INCREASE')
    expect(judgeLocal(-6, 5)).toBe('DECREASE')
    expect(judgeLocal(8, 8)).toBe('WITHIN_RANGE')
    expect(judgeLocal(-5, 5)).toBe('WITHIN_RANGE')
    expect(judgeLocal(20, null)).toBe('VALUE_ONLY')
  })
  it('서버 판정 UNKNOWN·NOT_COMPARABLE 은 값만', () => {
    expect(judgeFromServer('INCREASE')).toBe('INCREASE')
    expect(judgeFromServer('UNKNOWN')).toBe('VALUE_ONLY')
    expect(judgeFromServer('NOT_COMPARABLE')).toBe('VALUE_ONLY')
  })
})

describe('막대 위치', () => {
  it('0 은 가운데(50%), 양수는 오른쪽·음수는 왼쪽으로, 축 끝을 넘지 않는다', () => {
    expect(geom(5, 10)).toEqual({ left: 50, width: 25 })
    expect(geom(-5, 10)).toEqual({ left: 25, width: 25 })
    expect(geom(100, 10)).toEqual({ left: 50, width: 50 })
  })
})

describe('서버 비교 응답 → 프로필', () => {
  const base = { session_id: 'b', measured_on: '2026-10-13', model_version: 'm', kind: 'BASELINE' }
  const item = (metric_code: string, limb: string, b: number, t: number, judgement: string) => ({
    metric_code, limb, gait_type: 'OTHER', unit: 'deg', base_value: b, target_value: t, diff: t - b, judgement, note: null,
  })
  it('가동 범위만, 관절 순서대로 다리별 줄을 만들고 판정을 옮긴다', () => {
    const o: CompareOut = {
      dog_id: 'd', base, target: { session_id: 't', measured_on: '2026-11-09', model_version: 'm' }, model_changed: false,
      items: [item('rom_stifle', 'RH', 42.1, 51.5, 'INCREASE'), item('rom_shoulder', 'LF', 33.6, 33.6, 'WITHIN_RANGE'), item('stance_ratio', 'RH', 37, 40, 'UNKNOWN'), item('rom_elbow', 'RF', 67.8, 67.8, 'UNKNOWN')],
    }
    const v = profileFromServer(o, 'OTHER')!
    expect(v.rows.map((x) => `${x.code}|${x.limb}|${x.j}`)).toEqual(['rom_shoulder|LF|WITHIN_RANGE', 'rom_elbow|RF|VALUE_ONLY', 'rom_stifle|RH|INCREASE'])
    expect(v.rows[2].diff).toBe(9.4)
    expect(v.rows[1].tol).toBeNull()
    expect(v.scale).toBeGreaterThanOrEqual(10)
  })
  it('이번 회차가 기준이면 없음', () => {
    const o: CompareOut = { dog_id: 'd', base, target: { session_id: 'b', measured_on: '2026-10-13', model_version: 'm' }, model_changed: false, items: [] }
    expect(profileFromServer(o, 'OTHER')).toBeNull()
  })
})
