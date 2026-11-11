import { describe, expect, it } from 'vitest'
import { MIN_PASSES, measureQuality, sidesText } from './quality'

describe('measureQuality', () => {
  it('양쪽 다 기준 이상이면 안내가 없다', () => {
    const q = measureQuality({ LF: 8, LH: 9, RF: 10, RH: 8 })!
    expect(sidesText(q)).toBe(`왼쪽 9/${MIN_PASSES} · 오른쪽 10/${MIN_PASSES}`)
    expect(q.hint).toBeNull()
    expect(q.judgeNote).toBeNull()
  })

  it('한쪽이 모자라면 그쪽 방향으로 몇 번 더 걸리라고 안내한다', () => {
    const q = measureQuality({ LF: 6, LH: 5, RF: 8, RH: 8 })!
    expect(sidesText(q)).toBe('왼쪽 6/8 · 오른쪽 8/8')
    expect(q.hint).toBe('다음 측정 때 왼쪽 다리가 카메라 쪽으로 오게 왼쪽 2번 더 걷게 해 주세요')
    expect(q.judgeNote).toContain('왼쪽은 쓴 걸음이 8번보다 적어')
  })

  it('한쪽 걸음이 하나도 없으면 0 으로 보고 8번을 안내한다', () => {
    const q = measureQuality({ RF: 3, RH: 3 })!
    expect(sidesText(q)).toBe('왼쪽 0/8 · 오른쪽 3/8')
    expect(q.hint).toBe('다음 측정 때 양쪽 다리가 카메라 쪽으로 오게 왼쪽 8번, 오른쪽 5번 더 걷게 해 주세요')
  })

  it('다리별 수가 없으면(시연 데이터·예전 서버) null', () => {
    expect(measureQuality(undefined)).toBeNull()
    expect(measureQuality({})).toBeNull()
  })
})
