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
export interface StaffOut { id: string; login_id: string; name: string; email: string | null; role: string; effective_role: string; notif_on?: boolean; institution: InstitutionOut }
export interface TokenOut { access_token: string; token_type: string; expires_at: string; staff: StaffOut }
export interface DogOut {
  id: string; name: string; breed: string; weight_kg: number; size_class: string; size_class_manual: boolean
  birth_year: number | null; sex: string | null; rehab_start_date: string | null; focus_limb: string | null
  baseline_session_id: string | null; memo: string | null; version: number
  session_count: number; last_measured_on: string | null; open_session_id: string | null; created_at: string; updated_at: string
  // 271(!130) 뒤 칸. 예전 서버면 undefined
  /** 동물번호·보호자. owner_phone 은 상세·등록·수정 응답에만 있고 목록은 null(뒤 4자리는 owner_phone_last4) */
  chart_no?: string | null; owner_name?: string | null; owner_phone?: string | null; owner_phone_last4?: string | null
  /** PRE·REHAB·DONE. stage_changed_on 은 서버가 적는다 */
  stage?: 'PRE' | 'REHAB' | 'DONE'; stage_changed_on?: string | null
  latest_vital?: VitalOut | null
  last_surgery?: HistorySummaryOut | null; last_diagnosis?: HistorySummaryOut | null
  badges?: DogBadgeOut[]; changes?: DogChangeOut[]; last_symmetry?: number | null
}
export interface HistorySummaryOut { occurred_on: string; title: string; site: string | null }
/** 홈 특이사항 배지. 글은 화면이 만든다 */
export interface DogBadgeOut { code: 'SURGERY' | 'DIAGNOSIS' | 'IMPORTANT_NOTE' | string; title: string | null; site: string | null; on: string }
/** 최근 변동(기본 7일). delta 는 GAIT_* 에서만 */
export interface DogChangeOut { code: 'SURGERY_ADDED' | 'IMPORTANT_NOTE' | 'RESHOOT_NEEDED' | 'GAIT_BETTER' | 'GAIT_WORSE' | string; on: string; delta: number | null }
export interface StaffRef { id: string; name: string }
/** 바이탈(하루 한 줄). 재지 않은 값은 null */
export interface VitalOut {
  id: string; measured_on: string; weight_kg: number | null; temp_c: number | null; heart_rate: number | null; sbp: number | null; dbp: number | null
  staff: StaffRef | null; session_id: string | null; created_at: string; updated_at: string
}
export interface VitalIn { weight_kg?: number | null; temp_c?: number | null; heart_rate?: number | null; sbp?: number | null; dbp?: number | null }
/** 진단 이력(진단·수술·재활) */
export interface DogHistoryOut {
  id: string; occurred_on: string; kind: 'DIAGNOSIS' | 'SURGERY' | 'REHAB'; title: string; site: string | null; clinician: string | null
  staff: StaffRef | null; created_at: string
}
export interface HistoryIn { occurred_on?: string; kind?: string; title?: string; site?: string | null; clinician?: string | null; stage?: string }
/** 메모(CAUTION·GUARDIAN·BOOKING·OTHER)·진료 기록(S·O·A·P) */
export interface NoteOut {
  id: string; dog_id: string; session_id: string | null; category: string; body: string; important: boolean
  staff: StaffRef | null; revision_count: number; created_at: string; updated_at: string
}
export interface NoteRevisionOut { id: string; body: string; category: string; important: boolean; staff: StaffRef | null; revised_at: string }
export interface Paged<T> { items: T[]; total: number; page: number; size: number }
export interface ReasonOut { code: string; message: string }
/** 촬영의 통과 한 개(api-spec 5절). 3D 걸음 곡선을 만들 촬영을 고를 때 쓴다 */
export interface PassOut { pass_no: number; camera_side: 'LEFT' | 'RIGHT' | string; gait_type: string; is_valid: boolean; start_frame: number; end_frame: number }
export interface ShotOut { id: string; seq_no: number; status: string; fail_reason: ReasonOut | null; validity: string | null; uploaded_at: string; analyzed_at: string | null; video_status?: string; passes?: PassOut[] }
export type JointCode = 'shoulder' | 'elbow' | 'carpus' | 'hip' | 'stifle' | 'tarsus'
/** GET /shots/{id}/angles 통과 한 개: angles 의 i번째 값은 start_frame + i 프레임의 각도(°), 못 찾은 프레임은 null. 다리는 camera_side 쪽 */
export interface AnglesPass { pass_no: number; camera_side: 'LEFT' | 'RIGHT' | string; gait_type: string; start_frame: number; angles: Record<JointCode, (number | null)[]> }
/** GET /shots/{id}/angles(15.6). 줄 것이 없으면 passes 가 빈 배열 */
export interface AnglesOut { shot_id: string; fps: number; passes: AnglesPass[] }
/** GET /shots/{id}. video_url 은 결과 영상이 준비됐을 때만(서명 주소) */
export interface ShotDetailOut extends ShotOut { video_url: string | null }
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
  /** 대칭 점수 0~100(100 − 평균 대칭 지수, 앱과 같은 서버 값). 예전 서버면 undefined */
  symmetry_score?: number | null
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
/** 192 뒤 remaining_accounts 는 없다(기관당 코드 하나, 계정 수 상한 없음) */
export interface DeviceCodeVerifyOut { institution: { id: string; name: string }; remaining_accounts?: number }
export interface InstitutionAdminOut extends InstitutionOut { staff_count: number; device_code_count: number; created_at: string }
export interface DeviceCodeOut { id: string; code: string; institution_id: string; max_accounts?: number; active_accounts: number; revoked_at: string | null; note: string | null; created_at: string }
export interface StaffAdminOut { id: string; login_id: string; name: string; email: string | null; role: string; is_active: boolean; withdrawn_at?: string | null; device_code_id: string | null; created_at: string }
/** 가입 약관 동의(192). 필수 셋은 true 여야 서버가 받는다, marketing 만 선택 */
export interface TermsIn { version: string; service: boolean; privacy: boolean; device_location: boolean; marketing: boolean }

// ── 호출(지금 develop 에 있는 것만) ──
export const api = {
  login: (login_id: string, password: string) => request<TokenOut>('/auth/login', { method: 'POST', body: { login_id, password }, auth: false }),
  me: () => request<StaffOut>('/auth/me'),
  updateMe: (body: { name?: string; email?: string; notif_on?: boolean }) => request<StaffOut>('/auth/me', { method: 'PATCH', body }),
  /** 회원 탈퇴(192): 계정 중지. 400 PASSWORD_MISMATCH, 기관의 마지막 활성 계정이면 409 LAST_ACCOUNT */
  withdraw: (password: string) => request<void>('/auth/me', { method: 'DELETE', body: { password } }),
  changePassword: (current_password: string, new_password: string) =>
    request<StaffOut>('/auth/password', { method: 'PATCH', body: { current_password, new_password } }),
  verifyCode: (code: string) => request<DeviceCodeVerifyOut>('/auth/device-codes/verify', { method: 'POST', body: { code }, auth: false }),
  signup: (body: { code: string; login_id: string; password: string; name: string; email: string; terms?: TermsIn }) =>
    request<TokenOut>('/auth/signup', { method: 'POST', body, auth: false }),
  resetRequest: (login_id: string) => request<void>('/auth/password-reset/request', { method: 'POST', body: { login_id }, auth: false }),
  resetConfirm: (token: string, new_password: string) =>
    request<void>('/auth/password-reset/confirm', { method: 'POST', body: { token, new_password }, auth: false }),
  dogs: (page = 1, size = 100) => request<Paged<DogOut>>(`/dogs?page=${page}&size=${size}`),
  dog: (id: string) => request<DogOut>(`/dogs/${id}`),
  createDog: (body: Record<string, unknown>) => request<DogOut>('/dogs', { method: 'POST', body }),
  updateDog: (id: string, body: Record<string, unknown>) => request<DogOut>(`/dogs/${id}`, { method: 'PATCH', body }),
  /** 휴지통으로 보냄(서버가 정한 기간 뒤 영구 삭제). 회차·영상도 같이 숨는다 */
  deleteDog: (id: string) => request<void>(`/dogs/${id}`, { method: 'DELETE' }),
  /** 기관의 모든 회차, 최신순(BE-33) */
  instSessions: (page = 1, size = 100) => request<{ items: { id: string; measured_on: string; status: string; dog: { id: string; name: string } }[]; total: number }>(`/sessions?page=${page}&size=${size}`),
  startSession: (dogId: string, body: { measured_on?: string; weight_kg?: number }) =>
    request<SessionOut>(`/dogs/${dogId}/sessions`, { method: 'POST', body }),
  session: (id: string) => request<SessionDetailOut>(`/sessions/${id}`),
  shot: (id: string) => request<ShotDetailOut>(`/shots/${id}`),
  /** 통과별 프레임 관절 각도(15.6). 3D 보기의 측정 걸음 곡선 */
  angles: (id: string) => request<AnglesOut>(`/shots/${id}/angles`),
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
  // ── 차트 자료(271): 바이탈·진단 이력·메모·진료 기록 ──
  /** 바이탈 목록(최신 날짜가 앞, 전부) */
  vitals: (dogId: string) => request<{ items: VitalOut[] }>(`/dogs/${dogId}/vitals`),
  /** 그날 바이탈 저장. 있으면 보낸 값만 바꾼다(지우는 API 는 없다) */
  putVital: (dogId: string, day: string, body: VitalIn) => request<VitalOut>(`/dogs/${dogId}/vitals/${day}`, { method: 'PUT', body }),
  /** 진단 이력(오래된 것부터) */
  history: (dogId: string) => request<{ items: DogHistoryOut[] }>(`/dogs/${dogId}/history`),
  addHistory: (dogId: string, body: HistoryIn) => request<DogHistoryOut>(`/dogs/${dogId}/history`, { method: 'POST', body }),
  updateHistory: (dogId: string, id: string, body: HistoryIn) => request<DogHistoryOut>(`/dogs/${dogId}/history/${id}`, { method: 'PATCH', body }),
  deleteHistory: (dogId: string, id: string) => request<void>(`/dogs/${dogId}/history/${id}`, { method: 'DELETE' }),
  /** 메모·진료 기록(쓴 시각이 늦은 것부터). size 는 1~200 */
  notes: (dogId: string, page = 1, size = 200) => request<Paged<NoteOut>>(`/dogs/${dogId}/notes?page=${page}&size=${size}`),
  addNote: (dogId: string, body: { category: string; body: string; important?: boolean; session_id?: string }) =>
    request<NoteOut>(`/dogs/${dogId}/notes`, { method: 'POST', body }),
  /** SOAP 여러 칸을 같은 시각으로(1~8건) */
  addNotes: (dogId: string, body: { session_id?: string; notes: { category: string; body: string; important?: boolean }[] }) =>
    request<{ items: NoteOut[] }>(`/dogs/${dogId}/notes/batch`, { method: 'POST', body }),
  updateNote: (id: string, body: { body?: string; category?: string; important?: boolean }) => request<NoteOut>(`/notes/${id}`, { method: 'PATCH', body }),
  noteRevisions: (id: string) => request<{ items: NoteRevisionOut[] }>(`/notes/${id}/revisions`),
  sessionReports: (sessionId: string) => request<SessionReportsOut>(`/sessions/${sessionId}/reports`),
  regenerateReport: (reportId: string) => request<ReportOut>(`/reports/${reportId}/regenerate`, { method: 'POST' }),
  institutions: () => request<{ items: InstitutionAdminOut[] }>('/admin/institutions'),
  createInstitution: (body: { name: string; code?: string; contract_ends_at?: string | null }) =>
    request<InstitutionAdminOut>('/admin/institutions', { method: 'POST', body }),
  updateInstitution: (id: string, body: { name?: string; contract_ends_at?: string | null }) =>
    request<InstitutionAdminOut>(`/admin/institutions/${id}`, { method: 'PATCH', body }),
  deviceCodes: (instId: string) => request<{ items: DeviceCodeOut[] }>(`/admin/institutions/${instId}/device-codes`),
  /** 기관에 쓸 수 있는 코드가 이미 있으면 409 DEVICE_CODE_EXISTS(192) */
  createDeviceCode: (instId: string, body: { note?: string }) =>
    request<DeviceCodeOut>(`/admin/institutions/${instId}/device-codes`, { method: 'POST', body }),
  updateDeviceCode: (id: string, body: { note?: string | null }) =>
    request<DeviceCodeOut>(`/admin/device-codes/${id}`, { method: 'PATCH', body }),
  revokeDeviceCode: (id: string) => request<DeviceCodeOut>(`/admin/device-codes/${id}/revoke`, { method: 'POST' }),
  institutionStaff: (instId: string) => request<{ items: StaffAdminOut[] }>(`/admin/institutions/${instId}/staff`),
  updateStaff: (id: string, body: { is_active: boolean }) => request<StaffAdminOut>(`/admin/staff/${id}`, { method: 'PATCH', body }),
}
