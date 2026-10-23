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

/* ---------- 회차 측정 (api-spec 6절, 명세 v1.5: SessionOut.size_class) ---------- */

export type ShotStatus = 'UPLOADED' | 'SUBMITTED' | 'ANALYZING' | 'DONE' | 'FAILED'
export type Validity = 'VALID' | 'PARTIAL' | 'INVALID'
export type VideoStatus = 'PENDING' | 'READY' | 'FAILED'
export type CameraSide = 'LEFT' | 'RIGHT'
export type GaitType = 'WALK' | 'TROT' | 'PACE' | 'OTHER'

export interface SessionCreate {
  measured_on?: string
  weight_kg?: number | null
}

export interface SessionOut {
  id: string
  dog_id: string
  staff: { id: string; name: string }
  measured_on: string
  weight_kg: number | null
  /** 회차를 시작한 시점의 체급. 반려견의 지금 체급과 다를 수 있다 */
  size_class: SizeClass
  status: SessionStatus
  fail_reason: Reason | null
  model_name: string | null
  model_version: string | null
  completed_at: string | null
  aggregated_at: string | null
  created_at: string
}

export interface PassOut {
  pass_no: number
  camera_side: CameraSide
  gait_type: GaitType
  is_valid: boolean
  exclude_reason: Reason | null
  start_frame: number
  end_frame: number
}

export interface ShotOut {
  id: string
  seq_no: number
  status: ShotStatus
  fail_reason: Reason | null
  validity: Validity | null
  validity_reason: Reason | null
  video_status: VideoStatus
  below_min_spec: boolean
  passes: PassOut[]
  uploaded_at: string
  analyzed_at: string | null
}

export interface ShotUploadOut extends ShotOut {
  warnings: Reason[]
}

export interface SideProgress {
  valid_passes: number
  recommended: number
}

export interface SessionDetailOut extends SessionOut {
  dog: { id: string; name: string; breed: string; weight_kg: number; size_class: SizeClass }
  progress: { LEFT: SideProgress; RIGHT: SideProgress }
  notices: Reason[]
  /** 최신이 위(seq_no 내림차순) */
  shots: ShotOut[]
}
