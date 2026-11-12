import { describe, expect, it } from 'vitest'

import type { AnglesOut, AnglesPass } from '../api/client'
import { extremeFrames, loadAngleFrames, minMaxIndex, seekSec } from './angleFrames'

const pass = (no: number, side: 'LEFT' | 'RIGHT', gait: string, start: number, stifle: (number | null)[]): AnglesPass => ({
  pass_no: no, camera_side: side, gait_type: gait, start_frame: start,
  angles: { shoulder: [], elbow: [], carpus: [], hip: [], stifle, tarsus: [] },
})
const resp = (id: string, passes: AnglesPass[], fps = 60): AnglesOut => ({ shot_id: id, fps, passes })

describe('minMaxIndex', () => {
  it('빈 값은 건너뛰고 가장 작은·큰 위치를 준다', () => {
    expect(minMaxIndex([null, 120, 95.5, null, 150, 140])).toEqual({ min: 2, max: 4 })
  })
  it('같은 값이면 앞의 프레임', () => {
    expect(minMaxIndex([100, 90, 90, 130, 130])).toEqual({ min: 1, max: 3 })
  })
  it('값이 2개 미만이거나 모두 같으면 null', () => {
    expect(minMaxIndex([])).toBeNull()
    expect(minMaxIndex([null, 120, null])).toBeNull()
    expect(minMaxIndex([120, 120, 120])).toBeNull()
  })
  it('NaN·무한대는 값으로 치지 않는다', () => {
    expect(minMaxIndex([Number.NaN, 110, Infinity, 100, -Infinity])).toEqual({ min: 3, max: 1 })
  })
})

describe('extremeFrames', () => {
  it('고른 보행의 통과들 전체에서 가장 굽힌·편 프레임(번호는 start_frame 기준, 시각은 frame/fps)', () => {
    const r = resp('s1', [
      pass(1, 'LEFT', 'TROT', 100, [130, 101.2, 150]),
      pass(2, 'LEFT', 'TROT', 300, [140, 160.4, null, 110]),
      pass(3, 'LEFT', 'WALK', 500, [10, 200]), // 다른 보행은 보지 않는다
    ])
    const ex = extremeFrames(r, 'TROT', 'stifle')!
    expect(ex.flex).toEqual({ pass_no: 1, frame: 101, sec: 101 / 60, deg: 101.2 })
    expect(ex.ext).toEqual({ pass_no: 2, frame: 301, sec: 301 / 60, deg: 160.4 })
  })
  it('그 보행의 각도가 없거나 fps 가 없으면 null', () => {
    expect(extremeFrames(resp('s', [pass(1, 'LEFT', 'WALK', 0, [100, 120])]), 'TROT', 'stifle')).toBeNull()
    expect(extremeFrames(resp('s', [pass(1, 'LEFT', 'TROT', 0, [null, null])]), 'TROT', 'stifle')).toBeNull()
    expect(extremeFrames(resp('s', [pass(1, 'LEFT', 'TROT', 0, [100, 120])], 0), 'TROT', 'stifle')).toBeNull()
  })
})

describe('seekSec', () => {
  it('프레임 한가운데 시각, 영상 끝을 넘지 않게', () => {
    expect(seekSec(30, 60)).toBeCloseTo(30.5 / 60)
    expect(seekSec(600, 60, 5)).toBeCloseTo(5 - 0.5 / 60)
  })
})

describe('loadAngleFrames', () => {
  const shots = [
    { id: 'a', seq_no: 1, status: 'DONE', validity: 'VALID', passes: [{ camera_side: 'LEFT', gait_type: 'TROT', is_valid: true }] },
    { id: 'b', seq_no: 2, status: 'DONE', validity: 'VALID', passes: [{ camera_side: 'RIGHT', gait_type: 'TROT', is_valid: true }] },
  ]
  const angles: Record<string, AnglesOut> = {
    a: resp('a', [pass(1, 'LEFT', 'TROT', 10, [120, 90, 150])]),
    b: resp('b', [pass(1, 'RIGHT', 'TROT', 0, [100, 140])], 30),
  }
  const deps = (video: Record<string, { video_status: string; video_url: string | null }>) => ({
    session: async () => ({ shots }),
    angles: async (id: string) => angles[id],
    shot: async (id: string) => video[id],
  })

  it('쪽마다 결과 영상이 있는 촬영의 프레임과 주소', async () => {
    const out = await loadAngleFrames(deps({ a: { video_status: 'READY', video_url: '/v/a' }, b: { video_status: 'READY', video_url: '/v/b' } }), 'sess', 'TROT')
    expect(out.map((x) => [x.side, x.shotId, x.seqNo, x.fps, x.videoUrl, x.ex.flex.frame, x.ex.ext.frame])).toEqual([
      ['LEFT', 'a', 1, 60, '/v/a', 11, 12],
      ['RIGHT', 'b', 2, 30, '/v/b', 0, 1],
    ])
  })
  it('결과 영상이 READY 가 아니면 그 촬영은 뺀다', async () => {
    const out = await loadAngleFrames(deps({ a: { video_status: 'FAILED', video_url: null }, b: { video_status: 'PENDING', video_url: null } }), 'sess', 'TROT')
    expect(out).toEqual([])
  })
  it('회차를 못 받으면 빈 배열', async () => {
    const out = await loadAngleFrames({ ...deps({}), session: async () => { throw new Error('x') } }, 'sess', 'TROT')
    expect(out).toEqual([])
  })
})
