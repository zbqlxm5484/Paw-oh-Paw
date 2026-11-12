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

/** 가짜 서버 모드(vite --mode mock)에서 백엔드 대신 응답하는 처리 함수. undefined 를 돌려주면 그 주소는 맡지 않는다 */
export type MockRoute = (method: string, path: string) => Promise<unknown> | undefined
const mockRoutes: MockRoute[] = []
export const registerMock = (route: MockRoute): void => {
  mockRoutes.push(route)
}

/** token 을 주면 저장된 로그인 토큰 대신 그 토큰을 Bearer 로 보낸다(서버 PDF 워커의 인쇄 토큰) */
export async function request<T>(path: string, opts: { method?: string; body?: unknown; auth?: boolean; token?: string | null } = {}): Promise<T> {
  const { method = 'GET', body, auth = true, token } = opts
  for (const route of mockRoutes) {
    const hit = route(method, path)
    if (hit !== undefined) return (await hit) as T
  }
  const headers: Record<string, string> = { Accept: 'application/json' }
  let payload: BodyInit | undefined
  if (body instanceof FormData) payload = body
  else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  if (auth) {
    const t = token || tokenStore.get()
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
  /** 기관의 그날 기록(GET /daily-records)에서만 온다 */
  dog_id?: string
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
  /** 방문일(YYYY-MM-DD, 271). 예전 서버면 없다 */
  visited_on?: string
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
/** GET /dogs/{id}/trends(15.8): 수치 하나·보행 하나의 회차별 값. 다리마다 series 하나 */
export interface TrendsOut {
  dog_id: string; metric_code: string; unit: string; gait_type: string
  series: { limb: string; points: { session_id: string; measured_on: string; value: number | null; measurable: boolean }[] }[]
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

// ── 보고서 내용(GET /sessions/{id}/report-content, 285). 서버가 문장·표·수치를 만들고 KPI-30(숫자 대조)·KPI-31(금지 표현)
//    검사를 통과한 것만 준다. 인쇄 화면(/print/reports/:rid)은 이 값으로 그리기만 한다. `?` 칸은 아직 확정 전이라 없을 수 있다 ──
export type ReportEdition = 'OWNER' | 'VET'
export type LimbCode = 'LF' | 'RF' | 'LH' | 'RH'
export type PairCode = 'FORE' | 'HIND'
export type LegLevel = 'SIMILAR' | 'SLIGHT' | 'LARGE'
export interface ReportContentSession {
  measured_on: string; round: number; model_name: string | null; model_version: string | null
  weight_kg: number | null; size_class: string | null; symmetry_score: number | null
  /** 100 − 점수에 다리 단계와 같은 경계. 칸이 없으면 화면이 같은 규칙으로 정한다 */
  symmetry_level?: LegLevel | string | null
}
export interface ReportContentDog { name: string; breed: string | null; sex: string | null; birth_year: number | null; focus_limb: LimbCode | string | null }
export interface ReportContentPrevious {
  session_id: string; measured_on: string; round: number; model_changed: boolean
  /** "2회차, 2026년 11월 10일", 이번 회차와 같은 날이면 만든 시각까지(백엔드 v1.52, 문장 속 직전 회차 글과 같음). 옛 서버는 없을 수 있다 */
  label?: string
}
export interface ReportContentBaseline {
  session_id: string; measured_on: string; round: number; symmetry_score: number | null
  /** 이번 − 기준(%p). 한쪽이라도 없으면 null. 예전 서버라 칸이 없으면 화면이 symmetry_score − baseline.symmetry_score */
  diff?: number | null
}
/** 이 회차 포함 최대 8개, 오래된 순. 실패 회차는 symmetry_score null */
export interface ReportContentHistory { measured_on: string; round: number; symmetry_score: number | null }
/** 다리 쌍 하나의 색 단계와 덜 쓰는 다리. 비교할 수 있는 대상 수치가 없는 쌍은 빠진다.
 *  gait_type = 서버가 고른 보행 유형(TROT → WALK → OTHER 중 대상 수치를 비교할 수 있는 첫 유형). level 경계는 소수 첫째 자리로 반올림한 대칭 지수로 가른다 */
export interface ReportContentLeg {
  pair: PairCode; gait_type: string; metric_code: string; label: string
  /** 화면에 찍는 글("18.2%") */
  symmetry_index: string
  symmetry_value: number | null; weak_limb: LimbCode | null; level: LegLevel
}
export interface ReportContentSentences {
  title: string; edition_label: string; intro: string; summary: string[]
  previous_note: string | null; previous_gaps: string[]; caution: string[]
  glossary: { term: string; explanation: string }[]; disclaimer: string
}
export interface ReportContentCell { value: number | null; text: string; reason: string | null }
export interface ReportContentRow { metric_code: string; label: string; unit: string; cells: Partial<Record<string, ReportContentCell>> }
export interface ReportContentCompare {
  pair: PairCode | string; pair_label: string; metric_code: string; label: string
  left: string; right: string; diff: string; symmetry_index: string
  diff_value: number | null; symmetry_value: number | null; comparable: boolean; reason: string | null
}
export interface ReportContentChangeCell { previous: string; current: string; diff: string | null; change: string | null; change_label: string | null; note: string | null }
export interface ReportContentChange { metric_code: string; label: string; unit: string; cells: Partial<Record<string, ReportContentChangeCell>> }
export interface ReportContentGait {
  gait_type: string; label: string; notes: string[]
  rows: ReportContentRow[]; compare: ReportContentCompare[]; changes: ReportContentChange[]
}
export interface ReportContentOut {
  session_id: string; edition: ReportEdition; template_version: string
  session: ReportContentSession; dog: ReportContentDog
  previous: ReportContentPrevious | null; baseline: ReportContentBaseline | null
  history: ReportContentHistory[]
  legs?: ReportContentLeg[] | null
  sentences: ReportContentSentences
  gaits: ReportContentGait[]
}

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
  signup: (body: { code: string; login_id: string; password: string; name: string; email: string; terms: TermsIn }) =>
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
  /** token: 인쇄 토큰(서버 PDF 워커). 없으면 로그인 토큰 */
  session: (id: string, token?: string | null) => request<SessionDetailOut>(`/sessions/${id}`, { token }),
  shot: (id: string) => request<ShotDetailOut>(`/shots/${id}`),
  /** 통과별 프레임 관절 각도(15.6). 3D 보기의 측정 걸음 곡선 */
  angles: (id: string, token?: string | null) => request<AnglesOut>(`/shots/${id}/angles`, { token }),
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
  trends: (dogId: string, metric: string, gait: string) =>
    request<TrendsOut>(`/dogs/${dogId}/trends?metric_code=${encodeURIComponent(metric)}&gait_type=${gait}`),
  compare: (dogId: string, base: string, target?: string, gait?: string) =>
    request<CompareOut>(`/dogs/${dogId}/compare?base=${encodeURIComponent(base)}${target ? `&target=${target}` : ''}${gait ? `&gait_type=${gait}` : ''}`),
  // ── 차트 자료(271): 바이탈·진단 이력·메모·진료 기록 ──
  /** 바이탈 목록(최신 날짜가 앞, 전부) */
  vitals: (dogId: string) => request<{ items: VitalOut[] }>(`/dogs/${dogId}/vitals`),
  /** 그날 바이탈 저장. 있으면 보낸 값만 바꾼다 */
  putVital: (dogId: string, day: string, body: VitalIn) => request<VitalOut>(`/dogs/${dogId}/vitals/${day}`, { method: 'PUT', body }),
  /** 그날 바이탈 줄을 통째로 지운다(271). 없으면 404 */
  deleteVital: (dogId: string, day: string) => request<void>(`/dogs/${dogId}/vitals/${day}`, { method: 'DELETE' }),
  /** 진단 이력(오래된 것부터) */
  history: (dogId: string) => request<{ items: DogHistoryOut[] }>(`/dogs/${dogId}/history`),
  addHistory: (dogId: string, body: HistoryIn) => request<DogHistoryOut>(`/dogs/${dogId}/history`, { method: 'POST', body }),
  updateHistory: (dogId: string, id: string, body: HistoryIn) => request<DogHistoryOut>(`/dogs/${dogId}/history/${id}`, { method: 'PATCH', body }),
  deleteHistory: (dogId: string, id: string) => request<void>(`/dogs/${dogId}/history/${id}`, { method: 'DELETE' }),
  /** 메모·진료 기록(쓴 시각이 늦은 것부터). size 는 1~200 */
  notes: (dogId: string, page = 1, size = 200) => request<Paged<NoteOut>>(`/dogs/${dogId}/notes?page=${page}&size=${size}`),
  addNote: (dogId: string, body: { category: string; body: string; important?: boolean; session_id?: string; visited_on?: string }) =>
    request<NoteOut>(`/dogs/${dogId}/notes`, { method: 'POST', body }),
  /** SOAP 여러 칸을 같은 시각으로(1~8건) */
  addNotes: (dogId: string, body: { session_id?: string; visited_on?: string; notes: { category: string; body: string; important?: boolean }[] }) =>
    request<{ items: NoteOut[] }>(`/dogs/${dogId}/notes/batch`, { method: 'POST', body }),
  updateNote: (id: string, body: { body?: string; category?: string; important?: boolean }) => request<NoteOut>(`/notes/${id}`, { method: 'PATCH', body }),
  noteRevisions: (id: string) => request<{ items: NoteRevisionOut[] }>(`/notes/${id}/revisions`),
  /** 메모·진료 기록 한 건과 그 수정 이력을 지운다(271) */
  deleteNote: (id: string) => request<void>(`/notes/${id}`, { method: 'DELETE' }),
  /** 기관의 그날 기록(271): 그날 바이탈·메모(방문일)·회차. date 를 빼면 오늘 */
  dailyRecords: (date?: string) => request<{ date: string; vitals: VitalOut[]; notes: NoteOut[]; sessions: { id: string; dog?: { id: string } | null; dog_id?: string }[] }>(`/daily-records${date ? `?date=${date}` : ''}`),
  /** 내 기관의 측정 기기(271): 가린 코드와 발급 시각. 없으면 device 가 null */
  myDevice: () => request<{ device: { code_masked: string; issued_at: string } | null }>('/auth/me/device'),
  sessionReports: (sessionId: string) => request<SessionReportsOut>(`/sessions/${sessionId}/reports`),
  /** 보고서 내용(285). token 이 있으면 인쇄 토큰으로(로그인 없이), 없으면 저장된 로그인 토큰. 404 NOT_FOUND, 409 SESSION_NOT_DONE·REPORT_CHECK_FAILED */
  reportContent: (sessionId: string, edition: ReportEdition, token?: string | null) =>
    request<ReportContentOut>(`/sessions/${sessionId}/report-content?edition=${edition}`, { token }),
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
