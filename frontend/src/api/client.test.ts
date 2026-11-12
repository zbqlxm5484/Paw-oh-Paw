import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, onAuthLost, qs, request, tokenStore } from './client'

function memoryStorage() {
  const m = new Map<string, string>()
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v), removeItem: (k: string) => void m.delete(k) }
}

function respond(status: number, body?: unknown) {
  return vi.fn(async () => new Response(body === undefined ? null : typeof body === 'string' ? body : JSON.stringify(body), { status }))
}

const err = (status: number, code: string, detail: Record<string, unknown> | null = null) => ({ status, body: { error: { code, message: `${code} 문구`, detail } } })

beforeEach(() => {
  vi.stubGlobal('localStorage', memoryStorage())
  tokenStore.set('tok', '2099-01-01T00:00:00Z')
})
afterEach(() => vi.unstubAllGlobals())

describe('API 오류 형식 분기 (api-spec 1.3·1.4)', () => {
  it.each([
    [401, 'AUTH_REQUIRED'],
    [401, 'AUTH_EXPIRED'],
    [403, 'ACCOUNT_DISABLED'],
  ])('%i %s 면 토큰을 지우고 로그인으로 보낸다', async (status, code) => {
    const e = err(status, code)
    vi.stubGlobal('fetch', respond(e.status, e.body))
    const lost = vi.fn()
    const off = onAuthLost(lost)
    await expect(request('/dogs')).rejects.toMatchObject({ status, code, message: `${code} 문구` })
    expect(tokenStore.get()).toBeNull()
    expect(lost).toHaveBeenCalledOnce()
    off()
  })

  it('다른 403(권한 없음)은 로그인을 풀지 않는다', async () => {
    const e = err(403, 'FORBIDDEN')
    vi.stubGlobal('fetch', respond(e.status, e.body))
    const lost = vi.fn()
    const off = onAuthLost(lost)
    await expect(request('/dogs/x')).rejects.toBeInstanceOf(ApiError)
    expect(tokenStore.get()).toBe('tok')
    expect(lost).not.toHaveBeenCalled()
    off()
  })

  it('422 는 틀린 입력칸 목록을 fields 로 꺼낼 수 있다', async () => {
    const fields = [{ field: 'weight_kg', message: '체중을 입력해 주세요' }, { field: 'name', message: '이름이 너무 길어요' }]
    const e = err(422, 'VALIDATION_ERROR', { fields })
    vi.stubGlobal('fetch', respond(e.status, e.body))
    const caught = await request('/dogs', { method: 'POST', body: {} }).catch((x: unknown) => x)
    expect(caught).toBeInstanceOf(ApiError)
    const a = caught as ApiError
    expect(a.needsLogin).toBe(false)
    expect(a.fields.map((f) => f.field)).toEqual(['weight_kg', 'name'])
  })

  it('fields 가 없거나 모양이 다르면 빈 목록', () => {
    expect(new ApiError(422, { code: 'VALIDATION_ERROR', message: 'm', detail: null }).fields).toEqual([])
    expect(new ApiError(422, { code: 'VALIDATION_ERROR', message: 'm', detail: { fields: 'x' } }).fields).toEqual([])
  })

  it('오류 본문이 JSON 이 아니면 공통 문구로 바꾼다', async () => {
    vi.stubGlobal('fetch', respond(502, '<html>Bad Gateway</html>'))
    await expect(request('/dogs')).rejects.toMatchObject({ status: 502, code: 'INTERNAL_ERROR', message: '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.' })
  })
})

describe('요청 모양', () => {
  it('토큰을 Bearer 로 붙이고, auth:false 면 붙이지 않는다', async () => {
    const f = respond(200, { ok: 1 })
    vi.stubGlobal('fetch', f)
    await request('/dogs')
    await request('/auth/login', { method: 'POST', body: { a: 1 }, auth: false })
    const h0 = (f.mock.calls[0] as unknown as [string, RequestInit])[1].headers as Record<string, string>
    const h1 = (f.mock.calls[1] as unknown as [string, RequestInit])[1].headers as Record<string, string>
    expect(h0.Authorization).toBe('Bearer tok')
    expect(h1.Authorization).toBeUndefined()
    expect(h1['Content-Type']).toBe('application/json')
  })

  it('204 는 undefined', async () => {
    vi.stubGlobal('fetch', respond(204))
    await expect(request('/sessions/x', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('쿼리스트링은 빈 값을 뺀다', () => {
    expect(qs({ q: '콩', page: 1, size: undefined, x: null, y: '' })).toBe(`?q=${encodeURIComponent('콩')}&page=1`)
    expect(qs({})).toBe('')
  })

  it('만료 시각이 지났으면 isExpired', () => {
    tokenStore.set('t', '2000-01-01T00:00:00Z')
    expect(tokenStore.isExpired()).toBe(true)
  })
})
