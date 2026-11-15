import { describe, expect, it } from 'vitest'
import { MIN_PASSES, excludeSummary, excludeTerms, excludeText, measureQuality, sidesText } from './quality'

describe('measureQuality', () => {
  it('양쪽 다 기준 이상이면 안내가 없다', () => {
    const q = measureQuality({ LF: 8, LH: 9, RF: 10, RH: 8 })!
    expect(sidesText(q)).toBe(`왼쪽 9/${MIN_PASSES}, 오른쪽 10/${MIN_PASSES}`)
    expect(q.hint).toBeNull()
    expect(q.judgeNote).toBeNull()
  })

  it('한쪽이 모자라면 그쪽 방향으로 몇 번 더 걸리라고 안내한다', () => {
    const q = measureQuality({ LF: 6, LH: 5, RF: 8, RH: 8 })!
    expect(sidesText(q)).toBe('왼쪽 6/8, 오른쪽 8/8')
    expect(q.hint).toBe('다음 측정 때 왼쪽 다리가 카메라 쪽으로 오게 왼쪽 2번 더 걷게 해 주세요')
    expect(q.judgeNote).toContain('왼쪽은 쓴 걸음이 8번보다 적어')
  })

  it('한쪽 걸음이 하나도 없으면 0 으로 보고 8번을 안내한다', () => {
    const q = measureQuality({ RF: 3, RH: 3 })!
    expect(sidesText(q)).toBe('왼쪽 0/8, 오른쪽 3/8')
    expect(q.hint).toBe('다음 측정 때 양쪽 다리가 카메라 쪽으로 오게 왼쪽 8번, 오른쪽 5번 더 걷게 해 주세요')
  })

  it('다리별 수가 없으면(시연 데이터·예전 서버) null', () => {
    expect(measureQuality(undefined)).toBeNull()
    expect(measureQuality({})).toBeNull()
  })
})

describe('excludeSummary, excludeText', () => {
  it('사유별 수를 많은 순으로 묶고 끝 마침표를 뗀다', () => {
    const s = excludeSummary([['중간에 멈췄습니다.', 2], ['뛰었습니다. 천천히 걷게 해 주세요.', 3], ['몸이 가려졌습니다.', 1]])!
    expect(s.total).toBe(6)
    expect(excludeText(s)).toBe('쓰지 못한 걸음 6번: 뛰었습니다. 천천히 걷게 해 주세요 (3번), 중간에 멈췄습니다 (2번), 몸이 가려졌습니다 (1번)')
    expect(excludeText(s, '분석에 쓰지 못한 걸음')).toMatch(/^분석에 쓰지 못한 걸음 6번: /)
  })

  it('같은 문구는 합치고, 같은 수는 들어온 순서를 지킨다', () => {
    const s = excludeSummary([['중간에 멈췄습니다.', 1], ['몸이 가려졌습니다.', 2], ['중간에 멈췄습니다.', 1]])!
    expect(s.reasons).toEqual([{ msg: '중간에 멈췄습니다', n: 2 }, { msg: '몸이 가려졌습니다', n: 2 }])
    expect(s.total).toBe(4)
  })

  it('제외가 없거나 0번뿐이면 null(줄을 숨긴다)', () => {
    expect(excludeSummary([])).toBeNull()
    expect(excludeSummary(undefined)).toBeNull()
    expect(excludeSummary([['뛰었습니다.', 0]])).toBeNull()
  })

  it('보호자용: 사유 문구 속 전문 용어만 풀이한다', () => {
    expect(excludeTerms(excludeSummary([['측대보라 수치 계산에서 뺐습니다.', 2], ['보행 주기가 부족해 계산하지 못했습니다.', 1]])!))
      .toEqual(['측대보: 같은 쪽 앞발과 뒷발이 함께 움직이는 걸음', '보행 주기: 한 발이 바닥에 닿은 뒤 다시 닿을 때까지의 한 걸음'])
    expect(excludeTerms(excludeSummary([['뛰었습니다.', 2]])!)).toEqual([])
  })
})
