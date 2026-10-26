import { setupWorker } from 'msw/browser'

import { handlers } from './handlers'
import { resultHandlers } from './handlers.results'

// 구체적인 경로(/sessions/:id/result 등)가 먼저 와야 /sessions/:id 에 잡히지 않는다
export const worker = setupWorker(...resultHandlers, ...handlers)
