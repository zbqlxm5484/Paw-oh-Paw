import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'

import { ApiError } from './api/client'
import { AuthProvider } from './app/auth'
import { router } from './app/router'
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
  if (mode === '1') {
    const { worker } = await import('./mocks/browser')
    await worker.start()
  } else if (mode === 'partial') {
    // 백엔드에 있는 API 는 진짜 서버로, 없는 것만 가짜로 (mocks/partial.ts)
    const { partialWorker } = await import('./mocks/browser')
    await partialWorker.start({ onUnhandledFrame: 'bypass' })
  }
}

enableMocking().then(() => {
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
