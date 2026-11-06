import { beforeAll, describe, expect, it, vi } from 'vitest'

// 시연 모드(시제품 흉내) 처리 함수: 회원 탈퇴와 기관당 디바이스 코드 하나(192). node 환경이라 저장소를 메모리로 둔다
function memStorage(): Storage {
  const m = new Map<string, string>()
  return {
    getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, String(v)), removeItem: (k) => void m.delete(k),
    clear: () => m.clear(), key: (i) => [...m.keys()][i] ?? null, get length() { return m.size },
  }
}
vi.stubGlobal('window', { location: { origin: 'http://localhost', pathname: '/', search: '' } })
vi.stubGlobal('localStorage', memStorage())
vi.stubGlobal('sessionStorage', memStorage())

const fd = (o: Record<string, string>) => { const f = new FormData(); for (const [k, v] of Object.entries(o)) f.set(k, v); return f }

let dispatch: typeof import('./actions').dispatch
let db: typeof import('./db').db
let setLogin: typeof import('../app/session').setLogin
beforeAll(async () => {
  await import('./actions_impl')
  ;({ dispatch } = await import('./actions'))
  ;({ db } = await import('./db'))
  ;({ setLogin } = await import('../app/session'))
})

describe('회원 탈퇴 (/account/withdraw, 시연 모드)', () => {
  it('로그인 전이면 로그인 화면으로', async () => {
    setLogin(null)
    expect((await dispatch('/account/withdraw', fd({ password: 'x' }))).to).toBe('/login')
  })
  it('비밀번호가 틀리면 계정은 그대로', async () => {
    setLogin('s_demo')
    const g = await dispatch('/account/withdraw', fd({ password: 'wrong' }))
    expect(g.to).toBe('/account'); expect(g.toast).toContain('맞지 않습니다'); expect(db.staff.s_demo.active).toBe(true)
  })
  it('맞으면 계정을 중지하고 로그인 화면으로, 같은 기관 다른 계정은 그대로', async () => {
    setLogin('s_demo')
    const g = await dispatch('/account/withdraw', fd({ password: 'demo1234' }))
    expect(g.to).toBe('/login'); expect(db.staff.s_demo.active).toBe(false); expect(db.staff.s_full.active).toBe(true)
  })
  it('기관의 마지막 활성 계정은 탈퇴할 수 없다', async () => {
    setLogin('s_full')
    const g = await dispatch('/account/withdraw', fd({ password: 'demo1234' }))
    expect(g.to).toBe('/account'); expect(g.toast).toContain('마지막 계정'); expect(db.staff.s_full.active).toBe(true)
  })
})

describe('디바이스 코드: 기관마다 쓸 수 있는 코드 하나 (/admin, 시연 모드)', () => {
  it('쓸 수 있는 코드가 있으면 발급을 막는다', async () => {
    setLogin('s_admin')
    const g = await dispatch('/admin/institutions/demo/codes', fd({ note: '3호기' }))
    expect(g.toast).toContain('이미 있습니다'); expect(Object.values(db.codes).filter((c) => c.inst === 'demo').length).toBe(2)
  })
  it('회수한 뒤에는 발급된다', async () => {
    setLogin('s_admin')
    for (const id of ['c_demo', 'c_full']) expect((await dispatch(`/admin/codes/${id}`, fd({ revoke: '1' }))).toast).toContain('회수했어요')
    const g = await dispatch('/admin/institutions/demo/codes', fd({ note: '3호기' }))
    expect(g.toast).toContain('발급했어요')
    const active = Object.values(db.codes).filter((c) => c.inst === 'demo' && !c.revoked)
    expect(active.length).toBe(1); expect(active[0].note).toBe('3호기')
  })
  it('메모만 바꾸는 요청은 메모를 바꾼다', async () => {
    setLogin('s_admin')
    const g = await dispatch('/admin/codes/c_demo', fd({ note: '예전 1호기' }))
    expect(g.toast).toContain('메모'); expect(db.codes.c_demo.note).toBe('예전 1호기')
  })
  it('조회 전용(STAFF)은 발급할 수 없다', async () => {
    setLogin('s_temp')
    expect((await dispatch('/admin/institutions/demo/codes', fd({}))).toast).toContain('조회 전용')
  })
})
