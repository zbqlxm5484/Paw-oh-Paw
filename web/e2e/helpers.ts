import { expect, type Page } from '@playwright/test'

/** 백엔드 모드 개발 서버(playwright.config.ts 의 API_PORT) */
export const API_ORIGIN = 'http://localhost:5198'

/** 콘솔 오류·잡히지 않은 예외를 모은다. React 훅 순서 오류 같은 것이 여기 남는다 */
export function collectErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text())
  })
  page.on('pageerror', (e) => errors.push(String(e)))
  return errors
}

/** React 가 남기는 오류(훅 순서·렌더 중 예외 등)만 고른다. 영상·이미지 로딩 실패 같은 자원 오류는 뺀다 */
export function reactErrors(errors: string[]): string[] {
  return errors.filter((e) => /react|hook|rendered (more|fewer)|minified react error|uncaught|typeerror|referenceerror/i.test(e))
}

/** 가짜 서버 모드: 로그인 화면의 '시연용 예시 기관으로 둘러보기'로 시연 기관에 들어간다(비밀번호 없음) */
export async function demoLogin(page: Page): Promise<void> {
  await page.goto('/login')
  await page.getByRole('button', { name: '시연용 예시 기관으로 둘러보기' }).click()
  await expect(page).toHaveURL(/\/home/)
}

/** 화면 아래 알림(토스트) 글 */
export const toast = (page: Page) => page.locator('#toastMsg')
