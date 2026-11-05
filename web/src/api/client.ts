// 백엔드 API 호출. frontend/src/api/client.ts(모바일 앱)와 같은 규칙: /api/v1, Bearer 토큰, 오류 {error: {code, message, detail}}.
const BASE = `${(import.meta.env.VITE_API_BASE as string | undefined) ?? ''}/api/v1`

const TOKEN_KEY = 'pp.web.token'
const EXPIRES_KEY = 'pp.web.expires_at'

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token: string, expiresAt: string): void {
    try {
      localStorage.setItem(TOKEN_KEY, token)
      localStorage.setItem(EXPIRES_KEY, expiresAt)
    } catch {
      /* 저장 못 해도 이번 탭은 쓴다 */
    }
  },
  clear(): void {
    try {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(EXPIRES_KEY)
    } catch {
      /* 무시 */
    }
  },
  isExpired(): boolean {
    try {
      const exp = localStorage.getItem(EXPIRES_KEY)
      return !exp || Date.parse(exp) <= Date.now()
    } catch {
      return true
    }
  },
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly detail: Record<string, unknown> | null
  constructor(status: number, body: { code: string; message: string; detail: Record<string, unknown> | null }) {
    super(body.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.detail = body.detail
  }
}

export async function request<T>(path: string, opts: { method?: string; body?: unknown; auth?: boolean } = {}): Promise<T> {
  const { method = 'GET', body, auth = true } = opts
  const headers: Record<string, string> = { Accept: 'application/json' }
  let payload: BodyInit | undefined
  if (body instanceof FormData) payload = body
  else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  if (auth) {
    const t = tokenStore.get()
    if (t) headers.Authorization = `Bearer ${t}`
  }
  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload })
  if (res.status === 204) return undefined as T
  const text = await res.text()
  let json: unknown = null
  try {
    json = text ? JSON.parse(text) : null
  } catch {
    json = null
  }
  if (!res.ok) {
    const e = (json as { error?: ApiError } | null)?.error as unknown as { code: string; message: string; detail: Record<string, unknown> | null } | undefined
    throw new ApiError(res.status, e ?? { code: 'INTERNAL_ERROR', message: '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.', detail: null })
  }
  return json as T
}

// ── 응답 모양(backend/app/schemas, 백엔드 명세 15.3) ──
export interface InstitutionOut { id: string; code: string; name: string; contract_ends_at: string | null; contract_status: string }
export interface StaffOut { id: string; login_id: string; name: string; email: string | null; role: string; effective_role: string; institution: InstitutionOut }
export interface TokenOut { access_token: string; token_type: string; expires_at: string; staff: StaffOut }
export interface DogOut {
  id: string; name: string; breed: string; weight_kg: number; size_class: string; size_class_manual: boolean
  birth_year: number | null; sex: string | null; rehab_start_date: string | null; focus_limb: string | null
  baseline_session_id: string | null; memo: string | null; version: number
  session_count: number; last_measured_on: string | null; open_session_id: string | null; created_at: string; updated_at: string
}
export interface Paged<T> { items: T[]; total: number; page: number; size: number }
export interface ReasonOut { code: string; message: string }
export interface ShotOut { id: string; seq_no: number; status: string; fail_reason: ReasonOut | null; validity: string | null; uploaded_at: string; analyzed_at: string | null }
export interface SessionOut {
  id: string; dog_id: string; staff: { id: string; name: string }; measured_on: string; weight_kg: number | null
  size_class: string; status: string; fail_reason: ReasonOut | null; model_name: string | null; model_version: string | null; created_at: string
}
export interface SessionDetailOut extends SessionOut {
  progress: { LEFT: { valid_passes: number; recommended: number }; RIGHT: { valid_passes: number; recommended: number } }
  notices: ReasonOut[]
  shots: ShotOut[]
}
export interface MetricOut { metric_code: string; limb: string; value: number | null; unit: string; measurable: boolean; unmeasurable_reason: ReasonOut | null; n_passes: number }
export interface GaitResultOut { gait_type: string; metrics: MetricOut[]; limb_compare: unknown[] }
/** GET /sessions/{id}/result. 유효 통과 0건이면 gaits 는 빈 배열, pass_counts.used 는 0 */
export interface SessionResultOut extends SessionOut {
  completed_at: string | null
  pass_counts: { measured: number; used: number; excluded: number }
  shot_counts: { total: number; failed: number; invalid: number }
  exclude_summary: (ReasonOut & { count: number })[]
  notices: ReasonOut[]
  gaits: GaitResultOut[]
}
/** 보고서 판본 1개. file_url·download_url 은 status 가 DONE 일 때만 있다(서명 붙은 주소, 로그인 토큰 없이 열린다) */
export interface ReportOut {
  id: string; session_id: string; edition: 'OWNER' | 'VET' | string; status: 'PENDING' | 'GENERATING' | 'DONE' | 'FAILED' | string
  fail_reason: ReasonOut | null; generation_ms: number | null; template_version: string; model_version: string | null; updated_at: string
  file_url: string | null; download_url: string | null; url_expires_at: string | null
}
/** GET /sessions/{id}/reports. reports 는 OWNER, VET 순서이고 회차가 DONE 이 되기 전에는 비어 있다 */
export interface SessionReportsOut { session_id: string; session_status: string; reports: ReportOut[] }
/** 서버가 준 파일 주소(/api/v1/...)를 이 웹에서 열 주소로. S3 처럼 이미 절대 주소면 그대로 */
export const fileHref = (u: string): string => (/^https?:\/\//.test(u) ? u : `${(import.meta.env.VITE_API_BASE as string | undefined) ?? ''}${u}`)
/** GET /dogs/{id}/sessions 한 줄(15.8 측정 이력) */
export interface SessionHistoryItem {
  id: string; measured_on: string; weight_kg: number | null; status: string; is_baseline: boolean
  valid_passes: { LEFT: number; RIGHT: number }; model_version: string | null; reports: { OWNER: string | null; VET: string | null }
}
/** GET /dogs/{id}/compare 항목(15.8). judgement = INCREASE·DECREASE·WITHIN_RANGE·RANGE_NOT_SET·UNKNOWN·NOT_COMPARABLE */
export interface CompareItemOut {
  metric_code: string; limb: string; gait_type: string; unit: string
  base_value: number | null; target_value: number | null; diff: number | null; judgement: string; note: ReasonOut | null
}
export interface CompareOut {
  dog_id: string
  base: { session_id: string; measured_on: string; model_version: string | null; kind: string }
  target: { session_id: string; measured_on: string; model_version: string | null }
  model_changed: boolean
  items: CompareItemOut[]
}
export interface DeviceCodeVerifyOut { institution: { id: string; name: string }; remaining_accounts: number }
export interface InstitutionAdminOut extends InstitutionOut { staff_count: number; device_code_count: number; created_at: string }
export interface DeviceCodeOut { id: string; code: string; institution_id: string; max_accounts: number; active_accounts: number; revoked_at: string | null; note: string | null; created_at: string }
export interface StaffAdminOut { id: string; login_id: string; name: string; email: string | null; role: string; is_active: boolean; device_code_id: string | null; created_at: string }

// ── 호출(지금 develop 에 있는 것만) ──
export const api = {
  login: (login_id: string, password: string) => request<TokenOut>('/auth/login', { method: 'POST', body: { login_id, password }, auth: false }),
  me: () => request<StaffOut>('/auth/me'),
  updateMe: (body: { name?: string; email?: string }) => request<StaffOut>('/auth/me', { method: 'PATCH', body }),
  changePassword: (current_password: string, new_password: string) =>
    request<StaffOut>('/auth/password', { method: 'PATCH', body: { current_password, new_password } }),
  verifyCode: (code: string) => request<DeviceCodeVerifyOut>('/auth/device-codes/verify', { method: 'POST', body: { code }, auth: false }),
  signup: (body: { code: string; login_id: string; password: string; name: string; email: string }) =>
    request<TokenOut>('/auth/signup', { method: 'POST', body, auth: false }),
  resetRequest: (login_id: string) => request<void>('/auth/password-reset/request', { method: 'POST', body: { login_id }, auth: false }),
  resetConfirm: (token: string, new_password: string) =>
    request<void>('/auth/password-reset/confirm', { method: 'POST', body: { token, new_password }, auth: false }),
  dogs: (page = 1, size = 100) => request<Paged<DogOut>>(`/dogs?page=${page}&size=${size}`),
  dog: (id: string) => request<DogOut>(`/dogs/${id}`),
  createDog: (body: Record<string, unknown>) => request<DogOut>('/dogs', { method: 'POST', body }),
  updateDog: (id: string, body: Record<string, unknown>) => request<DogOut>(`/dogs/${id}`, { method: 'PATCH', body }),
  startSession: (dogId: string, body: { measured_on?: string; weight_kg?: number }) =>
    request<SessionOut>(`/dogs/${dogId}/sessions`, { method: 'POST', body }),
  session: (id: string) => request<SessionDetailOut>(`/sessions/${id}`),
  cancelSession: (id: string) => request<void>(`/sessions/${id}`, { method: 'DELETE' }),
  completeSession: (id: string) => request<SessionOut>(`/sessions/${id}/complete`, { method: 'POST' }),
  deleteShot: (id: string) => request<void>(`/shots/${id}`, { method: 'DELETE' }),
  retryShot: (id: string) => request<ShotOut>(`/shots/${id}/retry`, { method: 'POST' }),
  sessionResult: (id: string) => request<SessionResultOut>(`/sessions/${id}/result`),
  uploadShot: (sessionId: string, file: File) => {
    const fd = new FormData()
    fd.append('file', file, file.name)
    return request<ShotOut>(`/sessions/${sessionId}/shots`, { method: 'POST', body: fd })
  },
  /** 측정 이력(15.8, 백엔드 !91). 아직 없는 서버면 404 */
  dogSessions: (dogId: string, page = 1, size = 100) => request<Paged<SessionHistoryItem>>(`/dogs/${dogId}/sessions?page=${page}&size=${size}`),
  /** 회차 비교(15.8). base = BASELINE·PREVIOUS·회차 id, target 을 빼면 최근 DONE 회차 */
  compare: (dogId: string, base: string, target?: string, gait?: string) =>
    request<CompareOut>(`/dogs/${dogId}/compare?base=${encodeURIComponent(base)}${target ? `&target=${target}` : ''}${gait ? `&gait_type=${gait}` : ''}`),
  sessionReports: (sessionId: string) => request<SessionReportsOut>(`/sessions/${sessionId}/reports`),
  regenerateReport: (reportId: string) => request<ReportOut>(`/reports/${reportId}/regenerate`, { method: 'POST' }),
  institutions: () => request<{ items: InstitutionAdminOut[] }>('/admin/institutions'),
  createInstitution: (body: { name: string; code?: string; contract_ends_at?: string | null }) =>
    request<InstitutionAdminOut>('/admin/institutions', { method: 'POST', body }),
  updateInstitution: (id: string, body: { name?: string; contract_ends_at?: string | null }) =>
    request<InstitutionAdminOut>(`/admin/institutions/${id}`, { method: 'PATCH', body }),
  deviceCodes: (instId: string) => request<{ items: DeviceCodeOut[] }>(`/admin/institutions/${instId}/device-codes`),
  createDeviceCode: (instId: string, body: { max_accounts?: number; note?: string }) =>
    request<DeviceCodeOut>(`/admin/institutions/${instId}/device-codes`, { method: 'POST', body }),
  updateDeviceCode: (id: string, body: { max_accounts?: number; note?: string }) =>
    request<DeviceCodeOut>(`/admin/device-codes/${id}`, { method: 'PATCH', body }),
  revokeDeviceCode: (id: string) => request<DeviceCodeOut>(`/admin/device-codes/${id}/revoke`, { method: 'POST' }),
  institutionStaff: (instId: string) => request<{ items: StaffAdminOut[] }>(`/admin/institutions/${instId}/staff`),
  updateStaff: (id: string, body: { is_active: boolean }) => request<StaffAdminOut>(`/admin/staff/${id}`, { method: 'PATCH', body }),
}
