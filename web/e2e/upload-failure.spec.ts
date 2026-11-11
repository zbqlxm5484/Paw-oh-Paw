// 업로드 실패(!171): 한 파일이 실패하면 그 파일 이름과 이유를 알리고, 고른 영상을 업로드 화면에 다시 채워 둔다.
// 이 처리는 백엔드 모드(actions_backend.ts)에만 있어, 백엔드 모드 개발 서버를 띄우고 /api 를 page.route 로 가짜 응답한다.
// 실제 백엔드·계정·비밀번호는 쓰지 않는다(시험용 가짜 토큰만 브라우저 저장소에 넣는다)
import { expect, test, type Page, type Route } from '@playwright/test'
import { API_ORIGIN, collectErrors, reactErrors, toast } from './helpers'

const INST = { id: 'inst-e2e', code: 'E2E', name: '시험 동물병원', contract_ends_at: null, contract_status: 'ACTIVE' }
const ME = { id: 'staff-e2e', login_id: 'e2e', name: '시험 담당자', email: null, role: 'CLIENT', effective_role: 'CLIENT', notif_on: true, institution: INST }
const DOG = {
  id: 'dog-e2e', name: '시험견', breed: '말티즈', weight_kg: 4.2, size_class: 'SMALL', size_class_manual: false,
  birth_year: 2020, sex: 'MALE', rehab_start_date: null, focus_limb: null, baseline_session_id: null, memo: null, version: 1,
  session_count: 0, last_measured_on: null, open_session_id: null, created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z',
}
const SESSION_ID = 'sess-e2e'

const json = (route: Route, status: number, body: unknown) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

/** 가짜 백엔드. 돌려주는 값 = 받은 요청 기록("METHOD /path") */
async function fakeBackend(page: Page): Promise<string[]> {
  const calls: string[] = []
  // /src/api/client.ts 같은 모듈 주소는 건드리지 않게 /api/v1/ 만
  await page.route((url) => url.pathname.startsWith('/api/v1/'), async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const path = url.pathname.replace(/^\/api\/v1/, '')
    const m = req.method()
    calls.push(`${m} ${path}`)
    if (m === 'GET' && path === '/auth/me') return json(route, 200, ME)
    if (m === 'GET' && path === '/dogs') return json(route, 200, { items: [DOG], total: 1, page: 1, size: 100 })
    if (m === 'GET' && path === `/dogs/${DOG.id}`) return json(route, 200, DOG)
    if (m === 'GET' && path === '/auth/me/device') return json(route, 200, { device: null })
    if (m === 'POST' && path === `/dogs/${DOG.id}/sessions`) {
      return json(route, 201, { id: SESSION_ID, dog_id: DOG.id, status: 'OPEN', measured_on: '2026-11-11', created_at: '2026-11-11T00:00:00Z' })
    }
    if (m === 'POST' && path === `/sessions/${SESSION_ID}/shots`) {
      return json(route, 400, { error: { code: 'VIDEO_UNREADABLE', message: '영상을 읽을 수 없습니다', detail: null } })
    }
    if (m === 'DELETE' && path === `/sessions/${SESSION_ID}`) return route.fulfill({ status: 204 })
    // 그 밖의 읽기(회차 목록·알림 등)는 없는 API 로 답한다(화면은 없으면 그 칸을 비워 둔다)
    return json(route, 404, { error: { code: 'NOT_FOUND', message: '없음', detail: null } })
  })
  return calls
}

test.use({ baseURL: API_ORIGIN })

test('업로드 실패: 실패한 파일 이름과 이유가 남고, 고른 영상이 다시 채워진다', async ({ page }) => {
  const errors = collectErrors(page)
  const calls = await fakeBackend(page)
  // 로그인한 상태로 시작(가짜 토큰). 앱을 켜면 /auth/me·/dogs 를 읽어 들어온다
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('e2e-init')) {
      sessionStorage.setItem('e2e-init', '1')
      localStorage.setItem('pp.web.token', 'e2e-fake-token')
      localStorage.setItem('pp.web.expires_at', new Date(Date.now() + 3600_000).toISOString())
    }
  })
  await page.goto(`/upload?dog=${DOG.id}`)
  await expect(page.getByRole('heading', { name: '보행 영상 분석' })).toBeVisible()

  const fileName = 'walk-left-01.mp4'
  await page.locator('#fileInput').setInputFiles({ name: fileName, mimeType: 'video/mp4', buffer: Buffer.from('not really a video') })
  await expect(page.locator('#shotN')).toHaveText(/^1 \//)
  await page.locator('#startBtn').click()

  // 실패한 파일 이름과 서버가 준 이유
  await expect(toast(page)).toHaveText(`'${fileName}' 올리기 실패: 영상을 읽을 수 없습니다`)
  await expect(page).toHaveURL(new RegExp(`/upload\\?dog=${DOG.id}`))
  // 이번에 연 회차는 지운다
  expect(calls).toContain(`POST /sessions/${SESSION_ID}/shots`)
  expect(calls).toContain(`DELETE /sessions/${SESSION_ID}`)
  // 고른 영상은 업로드 화면에 그대로
  await expect(page.locator('#shotN')).toHaveText(/^1 \//)
  await expect(page.locator(`[title="${fileName}"]`)).toHaveCount(1)
  expect(reactErrors(errors)).toEqual([])
})
