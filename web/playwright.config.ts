import { defineConfig, devices } from '@playwright/test'

// 웹 E2E 시나리오(npm run e2e). 백엔드·실제 계정 없이 돈다.
// - 가짜 서버 모드(vite --mode mock, 5188): 시연 데이터(mocks/fixture.json)와 '시연용 예시 기관으로 둘러보기'로 들어간다
// - 백엔드 모드(5189): 업로드 실패처럼 백엔드 응답이 있어야 하는 시나리오만. /api 는 시험 안에서 page.route 로 가짜 응답을 준다
// 브라우저는 이 PC 에 설치된 Chrome(channel: 'chrome')을 쓴다(npx playwright install 불필요)
const MOCK_PORT = 5188
const API_PORT = 5189 // e2e/helpers.ts 의 API_ORIGIN 과 같게

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  timeout: 30_000,
  expect: { timeout: 7_000 },
  use: {
    baseURL: `http://localhost:${MOCK_PORT}`,
    channel: 'chrome',
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'phone', use: { ...devices['Desktop Chrome'], channel: 'chrome', viewport: { width: 390, height: 844 }, isMobile: false, hasTouch: false } },
    { name: 'desktop', use: { ...devices['Desktop Chrome'], channel: 'chrome', viewport: { width: 1280, height: 900 } } },
  ],
  webServer: [
    {
      command: `npm run dev:mock -- --port ${MOCK_PORT} --strictPort`,
      url: `http://localhost:${MOCK_PORT}/`,
      reuseExistingServer: !process.env.CI,
      stdout: 'ignore', // 공용 정적 파일 import 경고가 많아 화면을 덮는다
      stderr: 'ignore',
      timeout: 120_000,
    },
    {
      // 프록시 대상은 쓰이지 않는다(시험이 /api 를 모두 가로챈다). 혹시 새어 나가도 닫힌 포트로 가게 둔다
      command: `npx vite --port ${API_PORT} --strictPort`,
      url: `http://localhost:${API_PORT}/`,
      env: { VITE_DEV_PROXY_TARGET: 'http://127.0.0.1:9' },
      reuseExistingServer: !process.env.CI,
      stdout: 'ignore', // 공용 정적 파일 import 경고가 많아 화면을 덮는다
      stderr: 'ignore',
      timeout: 120_000,
    },
  ],
})
