import { describe, expect, it } from 'vitest'
import { CONTACT, legNote, ownerAdvice } from './ownerSummary'

describe('ownerSummary', () => {
  it('legNote: 비교 값 없음·범위 안·달라진 관절', () => {
    expect(legNote({ code: 'LF', joints: [], compared: false })).toBe('비교할 값 없음')
    expect(legNote({ code: 'LF', joints: [], compared: true })).toBe('범위 안')
    expect(legNote({ code: 'LF', joints: [], compared: true, short: true })).toBe('걸음 수 부족(8번 미만), 값만 비교')
    expect(legNote({ code: 'RH', joints: [{ n: '무릎', dir: '증가', d: 9.4 }, { n: '고관절', dir: '증가', d: 6.6 }], compared: true })).toBe('무릎 증가 · 고관절 증가')
  })
  it('ownerAdvice: 기존 안내를 할 일·지켜볼 것·연락 기준으로 나눔', () => {
    const a = ownerAdvice({ weak: true, summary: '', what: '', look: ['보기'], help: ['돕기'], urgent: [] })
    expect(a.todo).toEqual(['돕기'])
    expect(a.watch).toEqual(['보기'])
    expect(a.contact).toBe(CONTACT)
  })
  it('연락 기준은 관찰한 모습만 적는다(진단·통증 표현 없음)', () => {
    for (const s of CONTACT) expect(s).not.toMatch(/아프|통증|절뚝|파행|진단|질환|좋아|나빠|악화|호전/)
  })
})
