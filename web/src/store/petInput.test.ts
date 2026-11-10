// 반려견 폼 값 검사(11-09 QA: 체중 -3kg·2099년생이 그대로 등록됐다)
import { describe, expect, it } from 'vitest'
import { petInputError } from './actions'

describe('반려견 체중·출생 연도 검사', () => {
  it('정상 값은 통과', () => {
    expect(petInputError('28.4', '2019', 2026)).toBe('')
    expect(petInputError('3', '', 2026)).toBe('')
  })
  it('음수·0·너무 큰 체중, 숫자 아닌 체중', () => {
    for (const kg of ['-3', '0', '0.2', '150', '3kg', '']) expect(petInputError(kg, '', 2026)).toContain('체중')
  })
  it('미래·너무 오래된·네 자리가 아닌 출생 연도', () => {
    for (const b of ['2099', '2027', '1980', '19', '2O19']) expect(petInputError('5', b, 2026)).toContain('출생 연도')
  })
})
