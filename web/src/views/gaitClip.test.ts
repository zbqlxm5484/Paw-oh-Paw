import { describe, expect, it } from 'vitest'

import type { AnglesOut, AnglesPass } from '../api/client'
import { clipFromAngles, DEMO_NOTE, estimatePeriod, fillGaps, legStrides, loadSessionGait, N_PHASE, pickShots, strideBounds } from './gaitClip'

/** fps 60, 한 걸음 period 프레임, 가동 범위 amp 인 매끈한 곡선 */
const wave = (n: number, period: number, amp: number, mid = 120, shift = 0) =>
  Array.from({ length: n }, (_, i) => mid + (amp / 2) * Math.sin((2 * Math.PI * (i + shift)) / period))

const pass = (side: 'LEFT' | 'RIGHT', gait: 'TROT' | 'WALK', amp: Record<string, number>, n = 180, period = 30): AnglesPass => ({
  pass_no: 1, camera_side: side, gait_type: gait, start_frame: 0,
  angles: {
    shoulder: wave(n, period, amp.shoulder ?? 30), elbow: wave(n, period, amp.elbow ?? 40, 130, 5), carpus: wave(n, period, amp.carpus ?? 50, 180, 9),
    hip: wave(n, period, amp.hip ?? 28, 110), stifle: wave(n, period, amp.stifle ?? 45, 130, 4), tarsus: wave(n, period, amp.tarsus ?? 40, 135, 8),
  },
})
const rom = (c: number[]) => Math.max(...c) - Math.min(...c)

describe('걸음 자르기', () => {
  it('짧은 구멍만 잇는다', () => {
    expect(fillGaps([1, null, 3, null, null, null, 7], 2)).toEqual([1, 2, 3, null, null, null, 7])
    expect(fillGaps([null, 1, 2], 3)).toEqual([null, 1, 2])
  })
  it('한 걸음 길이를 자기상관으로 찾는다(두 배 길이를 고르지 않는다)', () => {
    const p = estimatePeriod(wave(240, 32, 40), 15, 72)
    expect(p?.period).toBe(32)
  })
  it('봉우리 사이로 걸음을 자른다', () => {
    const b = strideBounds(wave(200, 40, 30), 40)
    expect(b.length).toBeGreaterThanOrEqual(3)
    for (const [a, e] of b) expect(e - a).toBe(40)
  })
  it('관절별 50칸 곡선, 가동 범위를 보존한다', () => {
    const st = legStrides({ 무릎: wave(300, 36, 44), 고관절: wave(300, 36, 20) }, 60)
    expect(st.무릎.length).toBeGreaterThanOrEqual(5)
    expect(st.무릎[0]).toHaveLength(N_PHASE)
    expect(rom(st.무릎[0])).toBeGreaterThan(40)
  })
})

describe('각도 → 3D 곡선', () => {
  it('왼쪽·오른쪽 촬영으로 네 다리를 채우고, 고른 보행 유형만 쓴다', () => {
    const L: AnglesOut = { shot_id: 'a', fps: 60, passes: [pass('LEFT', 'TROT', { stifle: 20 }), pass('LEFT', 'WALK', { stifle: 80 })] }
    const R: AnglesOut = { shot_id: 'b', fps: 60, passes: [pass('RIGHT', 'TROT', { stifle: 46 })] }
    const got = clipFromAngles([L, R], 'TROT')!
    expect(Object.keys(got.clip.legs).sort()).toEqual(['LF', 'LH', 'RF', 'RH'])
    expect(Object.keys(got.clip.legs.LH.joint).sort()).toEqual(['고관절', '무릎', '뒷발목'].sort())
    expect(Math.abs(rom(got.clip.legs.LH.joint.무릎) - 20)).toBeLessThan(1.5)
    expect(Math.abs(rom(got.clip.legs.RH.joint.무릎) - 46)).toBeLessThan(2.5)
    expect(got.info.mirrored).toEqual([])
    expect(got.info.passes).toBe(2)
  })
  it('한쪽 촬영만 있으면 반대쪽을 비춰 쓰고 그 사실을 남긴다', () => {
    const got = clipFromAngles([{ shot_id: 'b', fps: 60, passes: [pass('RIGHT', 'TROT', {})] }], 'TROT')!
    expect(got.info.sides).toEqual(['R'])
    expect(got.info.mirrored).toEqual(['L'])
    expect(got.info.borrowed).toEqual([])
    expect(got.clip.legs.LF.joint.어깨).toEqual(got.clip.legs.RF.joint.어깨)
  })
  it('빈 통과·다른 유형뿐이면 null', () => {
    expect(clipFromAngles([{ shot_id: 'a', fps: 60, passes: [] }], 'TROT')).toBeNull()
    expect(clipFromAngles([{ shot_id: 'a', fps: 60, passes: [pass('LEFT', 'WALK', {})] }], 'TROT')).toBeNull()
  })
})

describe('촬영 고르기·불러오기', () => {
  const shot = (id: string, side: string, gait: string, n: number, extra: Partial<{ status: string; validity: string }> = {}) => ({
    id, status: 'DONE', validity: 'VALID', ...extra,
    passes: Array.from({ length: n }, () => ({ camera_side: side, gait_type: gait, is_valid: true })),
  })
  it('통과가 가장 많은 보행 유형, 쪽마다 통과 많은 촬영', () => {
    const p = pickShots([shot('a', 'LEFT', 'WALK', 3), shot('b', 'LEFT', 'WALK', 1), shot('c', 'RIGHT', 'WALK', 2), shot('d', 'RIGHT', 'TROT', 1), shot('e', 'LEFT', 'WALK', 5, { validity: 'INVALID' })], null, 1)
    expect(p).toEqual({ gait: 'WALK', L: ['a'], R: ['c'] })
    expect(pickShots([shot('d', 'RIGHT', 'TROT', 1), shot('a', 'LEFT', 'WALK', 3)], 'TROT')?.gait).toBe('TROT')
    expect(pickShots([shot('a', 'LEFT', 'WALK', 3, { status: 'FAILED' })], null)).toBeNull()
  })
  it('각도를 못 받으면 견본과 표시 문구', async () => {
    const demoClip = { legs: {} }
    const fail = await loadSessionGait({ session: async () => ({ shots: [shot('a', 'LEFT', 'TROT', 2)] }), angles: async () => { throw new Error('404') }, demo: async () => demoClip }, 's1', 'TROT')
    expect(fail).toEqual({ clip: demoClip, real: false, note: DEMO_NOTE })
    const none = await loadSessionGait({ session: async () => { throw new Error('x') }, angles: async () => ({ shot_id: '', fps: 60, passes: [] }), demo: async () => demoClip }, 's1', null)
    expect(none.real).toBe(false)
    const ok = await loadSessionGait({
      session: async () => ({ shots: [shot('a', 'LEFT', 'TROT', 1), shot('b', 'RIGHT', 'TROT', 1)] }),
      angles: async (id) => ({ shot_id: id, fps: 60, passes: [pass(id === 'a' ? 'LEFT' : 'RIGHT', 'TROT', {})] }),
      demo: async () => demoClip,
    }, 's1', 'TROT')
    expect(ok.real).toBe(true)
    expect(ok.note).toMatch(/^이 회차 실제 측정, 속보 \d+걸음 평균$/)
  })
})
