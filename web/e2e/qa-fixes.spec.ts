// 웹 QA 결함 수정(S15P31A404-285, !171·!172·!174·!176·!185)이 화면에서 그대로 유지되는지 본다.
// 가짜 서버 모드(vite --mode mock)에서 '시연용 예시 기관으로 둘러보기'로 들어가 시연 데이터(mocks/fixture.json)로 돈다
import { expect, test, type Page } from '@playwright/test'
import { collectErrors, demoLogin, reactErrors, toast } from './helpers'

test.describe('결과 목록', () => {
  test('로그인 전후로 열어도 훅 순서 오류 없이 목록이 뜬다', async ({ page }) => {
    const errors = collectErrors(page)
    // 로그인 전: 로그인이 필요한 화면이라 로그인 화면으로 보낸다
    await page.goto('/results')
    await expect(page).toHaveURL(/\/login/)
    await demoLogin(page)
    await page.goto('/results')
    await expect(page.getByRole('heading', { name: '분석 결과' })).toBeVisible()
    // 목록 줄: 대칭 점수는 '점'
    await expect(page.getByText(/^\d+점$/).first()).toBeVisible()
    // 반려견 칩으로 거르고 다시 전체로(같은 화면에서 상태가 바뀌며 다시 그려진다)
    await page.locator('a', { hasText: '보리' }).first().click()
    await expect(page).toHaveURL(/dog=/)
    await page.locator('a', { hasText: '전체' }).first().click()
    await expect(page.getByText(/^\d+점$/).first()).toBeVisible()
    expect(reactErrors(errors)).toEqual([])
  })
})

test.describe('반려견 삭제 확인', () => {
  test('휴지통·30일 복구 문구이고 "되돌릴 수 없습니다"가 없다', async ({ page }) => {
    await demoLogin(page)
    await page.goto('/my')
    const del = page.locator('.del-btn').first()
    const name = (await del.getAttribute('data-name')) ?? ''
    const id = (await del.getAttribute('data-id')) ?? ''
    await del.click()
    const modal = page.locator('#delModal')
    await expect(modal).toBeVisible()
    await expect(modal).toContainText(`${name} 정보를 삭제하시겠습니까?`)
    await expect(modal).toContainText('휴지통으로 옮겨지고, 30일 동안은 마이페이지의 ‘반려견 복구’에서 되돌릴 수 있습니다')
    await expect(modal).not.toContainText('되돌릴 수 없습니다')
    // 삭제하면 목록에서 빠지고 알림이 뜬다
    await modal.getByRole('button', { name: '삭제' }).click()
    await expect(toast(page)).toHaveText(`${name} 정보를 삭제했습니다`)
    await expect(page.locator(`.del-btn[data-id="${id}"]`)).toHaveCount(0)
  })
})

test.describe('보고서 표기', () => {
  for (const [type, label] of [['g', '보호자용'], ['v', '수의사용']] as const) {
    test(`${label}: '템플릿 1.0'이 없고 0~100 점수는 '좌우 대칭 점수 … 점'`, async ({ page }) => {
      const errors = collectErrors(page)
      await demoLogin(page)
      await page.goto(`/results/r1?type=${type}`)
      const main = page.locator('main')
      await expect(main).toContainText(`보행 분석 보고서, ${label}`)
      await expect(main).not.toContainText('템플릿')
      await expect(main).toContainText('분석 모델') // 분석 모델 표기는 남는다
      // 맨 위 칸: '좌우 대칭 점수' 다음 줄에 'NN점'(%가 아님)
      const head = main.getByText('좌우 대칭 점수', { exact: true }).first()
      await expect(head).toBeVisible()
      await expect(main).toContainText(/좌우 대칭 점수\s*\n?\s*\d+점/)
      await expect(main).not.toContainText(/좌우 대칭 (점수|지수)\s*\d+%/)
      // 기준 회차 대비도 '점'
      await expect(main).toContainText(/기준 회차\(\d+회차, [^)]+\)보다 [+-]?\d+점/)
      expect(reactErrors(errors)).toEqual([])
    })
  }

  test('보호자용: 직전 회차는 회차 번호와 날짜로, 차이는 점으로', async ({ page }) => {
    await demoLogin(page)
    await page.goto('/results/r1?type=g')
    await expect(page.locator('main')).toContainText(/직전 회차\(\d+회차, \d+월 \d+일[^)]*\)보다 좌우 대칭 점수 [+-]?\d+점/)
  })

  // 가짜 서버·시연 기관의 경과 비교 표(views.compare_view): % 값(걸음 길이 · 등 길이 기준)끼리의 차이는 '%p'.
  // 백엔드 회차의 비교 표(views/vet.ts serverCompareRows, !171)와 같은 표기
  test('경과 비교: % 값끼리의 차이는 %p (시연 기관 경로)', async ({ page }) => {
    await demoLogin(page)
    await page.goto('/compare/d1')
    const main = page.locator('main')
    await expect(main).toContainText('걸음 길이(등 길이 기준)')
    await expect(main).not.toContainText(/[▲▼] (증가|감소) [\d.]+%(?!p)/)
  })
})

test.describe('폼 이중 제출', () => {
  /** 반려견 차트의 오늘 진료 기록 폼에 바이탈과 S 를 채운다. 돌려주는 값 = 이번에 쓴 고유한 S 문구 */
  async function fillTodayNote(page: Page): Promise<string> {
    const today = await page.evaluate(() => {
      const d = new Date()
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    })
    await page.goto(`/dogs/d1?v=${today}`)
    const form = page.locator('form[action="/dogs/d1/notes"]').filter({ has: page.locator('input[name=visit]') })
    await expect(form).toBeVisible()
    for (const [nm, v] of [['kg', '28.2'], ['temp', '38.5'], ['hr', '90'], ['sbp', '138'], ['dbp', '82']]) await form.locator(`input[name=${nm}]`).fill(v)
    const text = `이중 제출 시험 ${Date.now()}`
    await form.locator('textarea[name=s]').fill(text)
    return text
  }
  /** 그 문구로 남은 진료 기록 줄 수(방문 목록의 미리보기는 빼고, 기록 줄만 센다) */
  const noteRows = (page: Page, text: string) => page.locator('main div[id]:has(> span > b.soap-k)').filter({ has: page.getByText(text, { exact: true }) })

  test('저장 버튼을 빠르게 두 번 눌러도 기록은 한 번만 남는다', async ({ page }) => {
    await demoLogin(page)
    const text = await fillTodayNote(page)
    await page.getByRole('button', { name: '기록 남기기' }).dblclick()
    await expect(noteRows(page, text)).toHaveCount(1)
    // 화면이 다시 그려진 뒤에도 한 건
    await page.waitForTimeout(500)
    await expect(noteRows(page, text)).toHaveCount(1)
  })

  test('보내는 중에 다시 제출하면 무시하고 제출 버튼을 잠근다', async ({ page }) => {
    await demoLogin(page)
    const text = await fillTodayNote(page)
    // 같은 순간에 두 번 제출(첫 제출이 끝나기 전)
    const state = await page.evaluate(() => {
      const f = document.querySelector<HTMLInputElement>('form[action="/dogs/d1/notes"] input[name=visit]')!.form!
      f.requestSubmit()
      const busy = f.getAttribute('aria-busy')
      const locked = f.querySelector<HTMLButtonElement>('button[type=submit]')!.disabled
      f.requestSubmit()
      return { busy, locked }
    })
    expect(state).toEqual({ busy: 'true', locked: true })
    await expect(noteRows(page, text)).toHaveCount(1)
    await page.waitForTimeout(500)
    await expect(noteRows(page, text)).toHaveCount(1)
  })
})

test.describe('첫 로딩', () => {
  test('첫 동기화가 끝나기 전에는 "불러오는 중입니다"가 보이고, 끝나면 화면으로 바뀐다', async ({ page }) => {
    // 가짜 서버 모드의 첫 준비(mocks/reportContent 읽기)를 붙잡아 두고 첫 화면을 본다
    let release: () => void = () => {}
    const held = new Promise<void>((r) => (release = r))
    await page.route(/\/src\/mocks\/reportContent\.ts/, async (route) => {
      await held
      await route.continue()
    })
    await page.goto('/login', { waitUntil: 'domcontentloaded' })
    const boot = page.getByRole('status')
    await expect(boot).toHaveText('불러오는 중입니다')
    release()
    await expect(page.getByRole('heading', { name: '로그인' })).toBeVisible()
    await expect(page.locator('.boot-loading')).toHaveCount(0)
  })
})

test.describe('경과 비교 관심 다리 칩', () => {
  test('저장된 관심 다리로 열리고, 칩을 고르면 그 다리가 표 맨 위로 온다', async ({ page }) => {
    const errors = collectErrors(page)
    await demoLogin(page)
    await page.goto('/compare/d1')
    const chips = page.locator('a[aria-pressed]')
    await expect(chips).toHaveCount(5)
    await expect(chips.filter({ hasText: '저장됨' })).toHaveCount(1)
    const saved = chips.filter({ hasText: '저장됨' })
    await expect(saved).toHaveAttribute('aria-pressed', 'true')
    // 다른 다리(왼뒤)를 고른다
    await chips.filter({ hasText: /^왼뒤/ }).click()
    await expect(page).toHaveURL(/leg=LH/)
    await expect(chips.filter({ hasText: /^왼뒤/ })).toHaveAttribute('aria-pressed', 'true')
    await expect(saved).toHaveAttribute('aria-pressed', 'false')
    await expect(page.getByText('왼뒤, 관심 다리').first()).toBeVisible()
    await expect(page.getByText('오른뒤, 관심 다리')).toHaveCount(0)
    // 비교 표의 첫 줄이 고른 다리
    // 칩(a[aria-pressed])이 아닌 곳에서 처음 나오는 다리 이름
    const firstLeg = await page.evaluate(() => {
      const re = /^(왼앞|오른앞|왼뒤|오른뒤)(, 관심 다리)?$|^전체$/
      for (const el of document.querySelectorAll('main *')) {
        if (el.closest('a[aria-pressed]') || el.children.length) continue
        const t = (el.textContent ?? '').trim()
        if (re.test(t)) return t
      }
      return ''
    })
    expect(firstLeg).toBe('왼뒤, 관심 다리')
    // 기준/직전을 바꿔도 고른 다리가 유지된다
    await page.getByRole('link', { name: '직전 회차 대비' }).click()
    await expect(page).toHaveURL(/leg=LH/)
    await expect(chips.filter({ hasText: /^왼뒤/ })).toHaveAttribute('aria-pressed', 'true')
    // 정하지 않음
    await chips.filter({ hasText: '정하지 않음' }).click()
    await expect(page).toHaveURL(/leg=none/)
    await expect(page.getByText(/, 관심 다리$/)).toHaveCount(0)
    // 칩은 터치 영역 44px 이상
    const box = await chips.first().boundingBox()
    expect(box!.height).toBeGreaterThanOrEqual(44)
    expect(reactErrors(errors)).toEqual([])
  })
})
