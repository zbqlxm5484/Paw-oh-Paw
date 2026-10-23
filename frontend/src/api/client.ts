import type { ApiErrorBody, ValidationField } from './types'

/** API 주소. 비어 있으면 같은 도메인의 /api/v1 (nginx 또는 vite proxy가 넘긴다). */
const BASE = `${(import.meta.env.VITE_API_BASE as string | undefined) ?? ''}/api/v1`

const TOKEN_KEY = 'pp.token'
const EXPIRES_KEY = 'pp.expires_at'

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  expiresAt(): string | null {
    try {
      return localStorage.getItem(EXPIRES_KEY)
    } catch {
      return null
    }
  },
  set(token: string, expiresAt: string) {
    try {
      localStorage.setItem(TOKEN_KEY, token)
      localStorage.setItem(EXPIRES_KEY, expiresAt)
    } catch {
      /* 저장 못 해도 이번 세션은 메모리로 간다 */
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(EXPIRES_KEY)
    } catch {
      /* ignore */
    }
  },
  /** expires_at 이 지났으면 true */
  isExpired(): boolean {
    const exp = this.expiresAt()
    return !exp || Date.parse(exp) <= Date.now()
  },
}

/** 서버 오류 `{error: {code, message, detail}}` 를 그대로 품는 예외. 화면은 message 를 보여 주고 code 로만 분기한다. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly detail: Record<string, unknown> | null

  constructor(status: number, body: ApiErrorBody['error']) {
    super(body.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.detail = body.detail
  }

  /** 422 VALIDATION_ERROR 의 틀린 입력칸 목록 */
  get fields(): ValidationField[] {
    const f = this.detail?.fields
    return Array.isArray(f) ? (f as ValidationField[]) : []
  }

  /** 로그인 화면으로 보내야 하는 오류인가 (api-spec 1.4) */
  get needsLogin(): boolean {
    return this.code === 'AUTH_REQUIRED' || this.code === 'AUTH_EXPIRED' || this.code === 'ACCOUNT_DISABLED'
  }
}

type Listener = (err: ApiError) => void
const authListeners = new Set<Listener>()
/** 401·403 으로 로그인이 풀렸을 때 알림을 받는다(AuthProvider 가 등록). */
export function onAuthLost(fn: Listener): () => void {
  authListeners.add(fn)
  return () => authListeners.delete(fn)
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  /** 로그인 등 토큰 없이 부르는 요청 */
  auth?: boolean
  signal?: AbortSignal
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true, signal } = opts
  const headers: Record<string, string> = { Accept: 'application/json' }
  let payload: BodyInit | undefined
  if (body instanceof FormData) {
    payload = body
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  if (auth) {
    const token = tokenStore.get()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload, signal })

  if (res.status === 204) return undefined as T

  const text = await res.text()
  let json: unknown = null
  if (text) {
    try {
      json = JSON.parse(text)
    } catch {
      json = null
    }
  }

  if (!res.ok) {
    const errBody = (json as ApiErrorBody | null)?.error ?? {
      code: 'INTERNAL_ERROR',
      message: '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
      detail: null,
    }
    const err = new ApiError(res.status, errBody)
    if (err.needsLogin) {
      tokenStore.clear()
      authListeners.forEach((fn) => fn(err))
    }
    throw err
  }
  return json as T
}

/** 쿼리스트링 만들기. undefined·null·'' 은 뺀다. */
export function qs(params: Record<string, string | number | undefined | null>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}
