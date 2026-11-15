import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'

import { ApiError } from './api/client'
import { AuthProvider } from './app/auth'
import { dropLeftoverDemo } from './app/demoMode'
import { router } from './app/router'
import { listenDeepLinks } from './app/deepLinks'
import './styles/global.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      // 4xx 는 다시 불러도 같다. 네트워크·5xx 만 한 번 더
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 1,
      refetchOnWindowFocus: false,
    },
  },
})

async function enableMocking() {
  const mode = import.meta.env.VITE_MOCK
  // 앱의 체험 모드(서버 없이 둘러보기)는 없앴다. 가짜 서버는 개발용 VITE_MOCK=1 빌드에서만
  dropLeftoverDemo()
  if (mode === '1') {
    const { worker } = await import('./mocks/browser')
    await worker.start()
  } else if (mode === 'partial') {
    // 백엔드에 있는 API 는 진짜 서버로, 없는 것만 가짜로 (mocks/partial.ts)
    const { partialWorker } = await import('./mocks/browser')
    await partialWorker.start({ onUnhandledFrame: 'bypass' })
  }
}

// 안드로이드 뒤로 가기: 앱 안에서 이전 화면으로. 더 갈 곳이 없을 때만 앱을 내린다(@capacitor/app 이 없으면 바로 꺼졌다)
async function nativeBackButton() {
  const { Capacitor } = await import('@capacitor/core')
  if (!Capacitor.isNativePlatform()) return
  const { App } = await import('@capacitor/app')
  await App.addListener('backButton', ({ canGoBack }) => {
    if (canGoBack) window.history.back()
    else void App.minimizeApp()
  })
}
void nativeBackButton()

enableMocking().then(() => {
  // 링크(웹 QR)로 열리면 그 화면으로
  void listenDeepLinks((path) => void router.navigate(path))
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>
    </StrictMode>,
  )
})
