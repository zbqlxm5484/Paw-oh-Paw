import { setupWorker } from 'msw/browser'

import { handlers } from './handlers'
import { resultHandlers } from './handlers.results'
import { partialHandlers } from './partial'

// 구체적인 경로(/sessions/:id/result 등)가 먼저 와야 /sessions/:id 에 잡히지 않는다
export const worker = setupWorker(...resultHandlers, ...handlers)

// VITE_MOCK=partial: 백엔드에 아직 없는 API 만
export const partialWorker = setupWorker(...partialHandlers)
