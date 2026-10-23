/** docs/api-spec.md v1.0 · docs/openapi.yaml 의 화면용 타입. 필드 이름은 API 그대로(snake_case). */

export type SizeClass = 'SMALL' | 'MEDIUM' | 'LARGE'
export type Sex = 'MALE' | 'FEMALE' | 'MALE_NEUTERED' | 'FEMALE_SPAYED'
export type Limb = 'LF' | 'RF' | 'LH' | 'RH'
export type SessionStatus = 'MEASURING' | 'AGGREGATING' | 'DONE' | 'FAILED'
export type ReportStatus = 'PENDING' | 'GENERATING' | 'DONE' | 'FAILED'
export type StaffRole = 'ADMIN' | 'STAFF'

export interface Reason {
  code: string
  message: string
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    detail: Record<string, unknown> | null
  }
}

export interface ValidationField {
  field: string
  type: string
}

export interface Paged<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface InstitutionOut {
  id: string
  code: string
  name: string
}

export interface StaffOut {
  id: string
  login_id: string
  name: string
  role: StaffRole
  institution: InstitutionOut
}

export interface LoginIn {
  institution_code: string
  login_id: string
  password: string
}

export interface TokenOut {
  access_token: string
  token_type: string
  expires_at: string
  staff: StaffOut
}

export interface DogOut {
  id: string
  name: string
  breed: string
  weight_kg: number
  size_class: SizeClass
  size_class_manual: boolean
  birth_year: number | null
  sex: Sex | null
  rehab_start_date: string | null
  focus_limb: Limb | null
  baseline_session_id: string | null
  memo: string | null
  session_count: number
  last_measured_on: string | null
  open_session_id: string | null
  created_at: string
  updated_at: string
}

export interface DogCreate {
  name: string
  breed: string
  weight_kg: number
  size_class?: SizeClass | null
  birth_year?: number | null
  sex?: Sex | null
  rehab_start_date?: string | null
  focus_limb?: Limb | null
  memo?: string | null
}

export type DogUpdate = Partial<DogCreate> & { baseline_session_id?: string | null }

export interface SessionHistoryItem {
  id: string
  measured_on: string
  weight_kg: number | null
  status: SessionStatus
  is_baseline: boolean
  valid_passes: { LEFT: number; RIGHT: number }
  model_version: string | null
  reports: { OWNER: ReportStatus; VET: ReportStatus } | null
}
