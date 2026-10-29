import { defineConfig } from 'vitest/config'

// 화면 표시 규칙 단위 테스트(S15P31A404-104). 화면 그리기 없이 값·문구 함수만 보므로 node 에서 돈다.
// vite.config.ts 의 PWA·프록시 설정은 테스트에 필요 없어서 따로 둔다.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
