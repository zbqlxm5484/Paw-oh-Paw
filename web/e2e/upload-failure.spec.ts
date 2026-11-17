// 첨부하는 즉시 올리기(314)와 업로드 실패(!171).
// 서버 기관은 영상을 칸에 넣는 순간 회차를 열고 뒤에서 올린다. '분석 시작'은 이미 올라간 회차를 끝내기만 한다.
// 영상 하나가 검사에 걸리면 그 파일 이름과 이유를 알리고 그 영상만 뺀다.
// 이 처리는 백엔드 모드에만 있어, 백엔드 모드 개발 서버를 띄우고 /api 를 page.route 로 가짜 응답한다.
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
const SESSION = {
  id: SESSION_ID, dog_id: DOG.id, staff: { id: ME.id, name: ME.name }, measured_on: '2026-11-11', weight_kg: null, size_class: 'SMALL',
  status: 'MEASURING', fail_reason: null, model_name: null, model_version: null, created_at: '2026-11-11T00:00:00Z',
}

const json = (route: Route, status: number, body: unknown) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

/** 가짜 백엔드. 돌려주는 값 = 받은 요청 기록("METHOD /path").
 *  failUpload: 영상 업로드를 400 으로 거절한다. delayMs: 영상 하나를 받는 데 걸리는 시간 */
async function fakeBackend(page: Page, opts: { failUpload?: boolean; delayMs?: number } = {}): Promise<string[]> {
  const calls: string[] = []
  const shots: { id: string; seq_no: number; status: string; fail_reason: null; validity: null; uploaded_at: string; analyzed_at: null; video_status: string; passes: never[] }[] = []
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
    if (m === 'POST' && path === `/dogs/${DOG.id}/sessions`) return json(route, 201, SESSION)
    if (m === 'GET' && path === `/sessions/${SESSION_ID}`) {
      return json(route, 200, { ...SESSION, progress: { LEFT: { valid_passes: 0, recommended: 8 }, RIGHT: { valid_passes: 0, recommended: 8 } }, notices: [], shots })
    }
    if (m === 'POST' && path === `/sessions/${SESSION_ID}/shots`) {
      if (opts.delayMs) await new Promise((ok) => setTimeout(ok, opts.delayMs))
      if (opts.failUpload) return json(route, 400, { error: { code: 'VIDEO_UNREADABLE', message: '영상을 읽을 수 없습니다', detail: null } })
      const shot = { id: `shot-${shots.length + 1}`, seq_no: shots.length + 1, status: 'UPLOADED', fail_reason: null, validity: null, uploaded_at: '2026-11-11T00:00:00Z', analyzed_at: null, video_status: 'PENDING', passes: [] as never[] }
      shots.push(shot)
      return json(route, 201, { ...shot, warnings: [] })
    }
    if (m === 'POST' && path === `/sessions/${SESSION_ID}/complete`) return json(route, 200, { ...SESSION, status: 'ANALYZING' })
    if (m === 'DELETE' && path === `/sessions/${SESSION_ID}`) return route.fulfill({ status: 204 })
    // 그 밖의 읽기(회차 목록·알림 등)는 없는 API 로 답한다(화면은 없으면 그 칸을 비워 둔다)
    return json(route, 404, { error: { code: 'NOT_FOUND', message: '없음', detail: null } })
  })
  return calls
}

/** 로그인한 상태로 업로드 화면을 연다(가짜 토큰). 앱을 켜면 /auth/me·/dogs 를 읽어 들어온다 */
async function openUpload(page: Page): Promise<void> {
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('e2e-init')) {
      sessionStorage.setItem('e2e-init', '1')
      localStorage.setItem('pp.web.token', 'e2e-fake-token')
      localStorage.setItem('pp.web.expires_at', new Date(Date.now() + 3600_000).toISOString())
    }
  })
  await page.goto(`/upload?dog=${DOG.id}`)
  await expect(page.getByRole('heading', { name: '보행 영상 분석' })).toBeVisible()
}

const video = (name: string) => ({ name, mimeType: 'video/mp4', buffer: Buffer.from('not really a video') })
const uploads = (calls: string[]) => calls.filter((c) => c === `POST /sessions/${SESSION_ID}/shots`).length

test.use({ baseURL: API_ORIGIN })

test('첨부하는 즉시 올린다: 분석 시작을 누르기 전에 영상이 올라가 있고, 누르면 바로 분석 화면으로 간다', async ({ page }) => {
  const errors = collectErrors(page)
  const calls = await fakeBackend(page)
  await openUpload(page)

  await page.locator('#fileInput').setInputFiles([video('a.mp4'), video('b.mp4'), video('c.mp4')])
  await expect(page.locator('#shotN')).toHaveText(/^3 \//)
  // 누르지 않아도 회차를 열고 3개를 올린다
  await expect.poll(() => uploads(calls)).toBe(3)
  expect(calls).toContain(`POST /dogs/${DOG.id}/sessions`)
  expect(calls).not.toContain(`POST /sessions/${SESSION_ID}/complete`)
  // 올리는 동안에도 칸 수는 그대로 3
  await expect(page.locator('#shotN')).toHaveText(/^3 \//)
  // 영상을 올리기 시작하면 체중은 고정된다
  await expect(page.locator('#sessW')).toHaveAttribute('readonly', '')

  await page.locator('#startBtn').click()
  await expect(page).toHaveURL(new RegExp(`/analyzing/${SESSION_ID}`))
  expect(calls).toContain(`POST /sessions/${SESSION_ID}/complete`)
  // 다시 올리지 않고, 연 회차를 지우지도 않는다
  expect(uploads(calls)).toBe(3)
  expect(calls).not.toContain(`DELETE /sessions/${SESSION_ID}`)
  expect(reactErrors(errors)).toEqual([])
})

test('다 올라가기 전에 분석 시작을 누르면 진행을 보여 주고, 다 올린 뒤 스스로 넘어간다', async ({ page }) => {
  const errors = collectErrors(page)
  const calls = await fakeBackend(page, { delayMs: 500 })
  await openUpload(page)

  await page.locator('#fileInput').setInputFiles([video('a.mp4'), video('b.mp4'), video('c.mp4')])
  await expect(page.locator('#shotN')).toHaveText(/^3 \//)
  await page.locator('#startBtn').click()
  await expect(page.getByRole('status').filter({ hasText: '영상 올리는 중' })).toContainText('/ 3')
  // 아직 다 안 올라갔으므로 회차를 끝내지 않았다
  expect(calls).not.toContain(`POST /sessions/${SESSION_ID}/complete`)

  await expect(page).toHaveURL(new RegExp(`/analyzing/${SESSION_ID}`))
  expect(uploads(calls)).toBe(3)
  expect(calls).toContain(`POST /sessions/${SESSION_ID}/complete`)
  expect(reactErrors(errors)).toEqual([])
})

test('업로드 실패: 실패한 파일 이름과 이유를 알리고 그 영상만 뺀다. 화면을 떠나면 연 회차를 지운다', async ({ page }) => {
  const errors = collectErrors(page)
  const calls = await fakeBackend(page, { failUpload: true })
  await openUpload(page)

  const fileName = 'walk-left-01.mp4'
  await page.locator('#fileInput').setInputFiles(video(fileName))
  // 실패한 파일 이름과 서버가 준 이유
  await expect(toast(page)).toHaveText(`'${fileName}' 올리기 실패: 영상을 읽을 수 없습니다`)
  expect(calls).toContain(`POST /sessions/${SESSION_ID}/shots`)
  // 검사에 걸린 영상은 칸에서 빠진다(다시 올려도 같은 이유로 걸린다)
  await expect(page.locator('#shotN')).toHaveText(/^0 \//)
  await expect(page.locator(`[title="${fileName}"]`)).toHaveCount(0)
  await expect(page).toHaveURL(new RegExp(`/upload\\?dog=${DOG.id}`))

  // 영상 없이 떠나면 이번에 연 빈 회차는 지운다(그 반려견이 '측정 중'에 갇히지 않게)
  // 화면 안 이동(앱 메뉴)으로 떠난다. 새로고침·탭 닫기는 정리할 틈이 없어 회차가 남고, 다음에 이어 올리게 된다
  await page.locator('a[href$="/home"]').first().click()
  await expect(page).toHaveURL(/\/home/)
  await expect.poll(() => calls.includes(`DELETE /sessions/${SESSION_ID}`)).toBe(true)
  expect(reactErrors(errors)).toEqual([])
})
