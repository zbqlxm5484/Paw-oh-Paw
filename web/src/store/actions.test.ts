import { describe, expect, it, vi } from 'vitest'

import { BACKEND, dispatch, on } from './actions'

// 시험은 node 환경이라 dispatch 가 주소를 풀 때 쓰는 window.location 만 둔다
vi.stubGlobal('window', { location: { origin: 'http://localhost', pathname: '/', search: '' } })

describe('폼 처리 함수 고르기 (actions.dispatch)', () => {
  it('백엔드 처리 함수가 등록 순서와 무관하게 먼저 불린다', async () => {
    on('/__t/order', () => ({ to: '/local' })) // 로컬(시제품) 처리 함수를 먼저 등록해도
    on('/__t/order', () => ({ to: '/backend' }), BACKEND)
    expect((await dispatch('/__t/order', new FormData())).to).toBe('/backend')
  })

  it("백엔드가 '__local__' 로 넘기면 로컬 처리 함수가 받는다", async () => {
    on('/__t/pass', () => ({ to: '/local' }))
    on('/__t/pass', () => ({ to: '__local__' }), BACKEND)
    expect((await dispatch('/__t/pass', new FormData())).to).toBe('/local')
  })
})
