/** docs/api-spec.md v1.0 · docs/openapi.yaml 의 화면용 타입. 필드 이름은 API 그대로(snake_case). */

export type SizeClass = 'SMALL' | 'MEDIUM' | 'LARGE'
export type Sex = 'MALE' | 'FEMALE' | 'MALE_NEUTERED' | 'FEMALE_SPAYED'
export type Limb = 'LF' | 'RF' | 'LH' | 'RH'
export type SessionStatus = 'MEASURING' | 'AGGREGATING' | 'DONE' | 'FAILED'
export type ReportStatus = 'PENDING' | 'GENERATING' | 'DONE' | 'FAILED'
/** 저장되는 역할. ADMIN·STAFF = 크림오프, CLIENT = 기관 담당자(회원가입 명세 v0.3) */
export type StaffRole = 'ADMIN' | 'STAFF' | 'CLIENT'
/** 요청 때 계산하는 역할. 계약이 끝난 CLIENT 는 GUEST */
export type EffectiveRole = StaffRole | 'GUEST'

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
  contract_ends_at?: string | null
  contract_status?: 'ACTIVE' | 'EXPIRED'
}

export interface StaffOut {
  id: string
  login_id: string
  name: string
  role: StaffRole
  /** 화면은 role 이 아니라 이 값으로 나눈다(GUEST 면 계약 만료 안내). 예전 서버는 안 보낼 수 있다 */
  effective_role?: EffectiveRole
  /** 알림 설정(192). 예전 서버는 안 보낼 수 있다 */
  notif_on?: boolean
  email?: string | null
  institution: InstitutionOut
}

/** 로그인은 아이디 + 비밀번호(기관 코드 없음, 회원가입 명세 v0.3) */
export interface LoginIn {
  login_id: string
  password: string
}

export interface DeviceCodeVerifyOut {
  institution: { id: string; name: string }
  /** 백엔드 192(기관당 코드 하나, 계정 수 제한 없음) 뒤에는 응답에 없다 */
  remaining_accounts?: number
}

/** 가입 약관 동의(192). 필수 셋은 true 여야 서버가 받는다, marketing 만 선택 */
export interface TermsIn {
  version: string
  service: boolean
  privacy: boolean
  device_location: boolean
  marketing: boolean
}

export interface SignupIn {
  code: string
  login_id: string
  password: string
  name: string
  email: string
  /** 약관 동의. 백엔드 v1.58 부터 필수(없으면 422) */
  terms: TermsIn
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
  /** 낙관적 잠금. 수정할 때 읽은 값을 보내고, 어긋나면 409 DOG_MODIFIED */
  version: number
  created_at: string
  updated_at: string
  /** 가장 최근 날짜의 바이탈 한 줄(그날 안 잰 값은 null). 체중은 weight_kg 를 쓴다 */
  latest_vital?: VitalOut | null
  /** 가장 최근 수술·진단(목록 요약) */
  last_surgery?: HistorySummary | null
  last_diagnosis?: HistorySummary | null
  /** 홈 특이사항 배지(271). 글은 화면이 만든다. 예전 서버면 undefined */
  badges?: DogBadge[]
  /** 최근 7일 변동(271). on 이 늦은 순서. 예전 서버면 undefined */
  changes?: DogChange[]
  /** 가장 최근 완료 회차의 대칭 점수(271) */
  last_symmetry?: number | null
}

export interface DogBadge {
  code: 'SURGERY' | 'DIAGNOSIS' | 'IMPORTANT_NOTE'
  title: string | null
  site: string | null
  on: string
}

export interface DogChange {
  code: 'SURGERY_ADDED' | 'IMPORTANT_NOTE' | 'RESHOOT_NEEDED' | 'GAIT_BETTER' | 'GAIT_WORSE'
  on: string
  /** GAIT_* 에서만 점수 차(이번 − 앞) */
  delta: number | null
}

/** 진료 정보(11-09 백엔드 조영운): 바이탈·진단/수술 이력 */
export interface StaffRef {
  id: string
  name: string
}
export interface VitalOut {
  id: string
  measured_on: string
  weight_kg: number | null
  temp_c: number | null
  heart_rate: number | null
  sbp: number | null
  dbp: number | null
  staff: StaffRef | null
  session_id: string | null
  created_at: string
  updated_at: string
}
export type HistoryKind = 'DIAGNOSIS' | 'SURGERY' | 'REHAB'
export type HistorySite = 'LF' | 'RF' | 'LH' | 'RH' | 'SP'
export interface DogHistoryOut {
  id: string
  occurred_on: string
  kind: HistoryKind
  title: string
  site: HistorySite | null
  clinician: string | null
  staff: StaffRef | null
  created_at: string
}
export interface HistorySummary {
  occurred_on: string
  title: string
  site: HistorySite | null
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

/** PATCH /dogs/{id}. version 은 필수(읽었을 때의 값, 없으면 422, 다르면 409 DOG_MODIFIED) */
export type DogUpdate = Partial<DogCreate> & { baseline_session_id?: string | null; version: number }

export interface SessionHistoryItem {
  id: string
  measured_on: string
  weight_kg: number | null
  status: SessionStatus
  is_baseline: boolean
  valid_passes: { LEFT: number; RIGHT: number }
  model_version: string | null
  reports: { OWNER: ReportStatus; VET: ReportStatus } | null
  /** 대칭 점수 0~100(271, 100 − 평균 대칭 지수). 완료 전이거나 계산할 쌍이 없으면 null, 예전 서버면 undefined */
  symmetry_score?: number | null
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

/* ---------- 촬영 상세·각도 (api-spec 6절) ---------- */

export interface ShotDetailOut extends ShotOut {
  width: number | null
  height: number | null
  fps: number | null
  duration_sec: number | null
  bitrate_kbps: number | null
  codec: string | null
  model_name: string | null
  model_version: string | null
  submitted_at: string | null
  video_ready_at: string | null
  /** video_status 가 READY 일 때만. 서명 주소, 토큰 없이 <video src> 에 넣는다 */
  video_url: string | null
  url_expires_at: string | null
}

export type JointCode = 'shoulder' | 'elbow' | 'carpus' | 'hip' | 'stifle' | 'tarsus'

export interface AnglesPass {
  pass_no: number
  camera_side: CameraSide
  gait_type: GaitType
  start_frame: number
  angles: Record<JointCode, (number | null)[]>
}

export interface AnglesOut {
  shot_id: string
  fps: number
  passes: AnglesPass[]
}

/* ---------- 회차 결과 (api-spec 7절) ---------- */

export type MetricLimb = Limb | 'NONE'
export type Pair = 'FORE' | 'HIND'
export type Unit = 'deg' | 'pct' | 'pct_body' | 'body_per_sec' | 'count'

export interface MetricOut {
  metric_code: string
  limb: MetricLimb
  value: number | null
  unit: Unit
  measurable: boolean
  unmeasurable_reason: Reason | null
  n_passes: number
}

export interface LimbCompareOut {
  pair: Pair
  metric_code: string
  unit: Unit
  left: number | null
  right: number | null
  /** 왼쪽 − 오른쪽 */
  diff: number | null
  /** 좌우 차이 비율(%). 클수록 차이가 크다. 큰 순서로 정렬돼 온다 */
  symmetry_index: number | null
  comparable: boolean
  reason: Reason | null
}

export interface GaitResultOut {
  gait_type: GaitType
  metrics: MetricOut[]
  limb_compare: LimbCompareOut[]
}

export interface SessionResultOut extends SessionOut {
  pass_counts: { measured: number; used: number; excluded: number }
  shot_counts: { total: number; failed: number; invalid: number }
  /** 대칭 점수(271). 화면은 이 값을 그대로 쓴다. 예전 서버면 undefined */
  symmetry_score?: number | null
  exclude_summary: (Reason & { count: number })[]
  notices: Reason[]
  gaits: GaitResultOut[]
}

/* ---------- 보고서 ---------- */

export type Edition = 'OWNER' | 'VET'

export interface ReportOut {
  id: string
  session_id: string
  edition: Edition
  status: ReportStatus
  fail_reason: Reason | null
  generation_ms: number | null
  template_version: string | null
  model_version: string | null
  updated_at: string
  file_url: string | null
  download_url: string | null
  url_expires_at: string | null
}

export interface ReportsOut {
  session_id: string
  session_status: SessionStatus
  reports: ReportOut[]
}

/* ---------- 비교·추이 (api-spec 8절) ---------- */

export type Judgement = 'INCREASE' | 'DECREASE' | 'WITHIN_RANGE' | 'UNKNOWN' | 'NOT_COMPARABLE'
export type BaseKind = 'BASELINE' | 'PREVIOUS' | 'SESSION'

export interface CompareItem {
  metric_code: string
  limb: MetricLimb
  gait_type: GaitType
  unit: Unit
  base_value: number | null
  target_value: number | null
  /** target − base */
  diff: number | null
  judgement: Judgement
  note: Reason | null
}

export interface CompareOut {
  dog_id: string
  base: { session_id: string; measured_on: string; model_version: string | null; kind: BaseKind }
  target: { session_id: string; measured_on: string; model_version: string | null }
  model_changed: boolean
  items: CompareItem[]
}

export interface TrendPoint {
  session_id: string
  measured_on: string
  value: number | null
  measurable: boolean
  unmeasurable_reason: Reason | null
  model_version: string | null
}

export interface TrendsOut {
  dog_id: string
  metric_code: string
  unit: Unit
  gait_type: GaitType
  series: { limb: MetricLimb; points: TrendPoint[] }[]
  lr_diff: { pair: Pair; points: { session_id: string; measured_on: string; diff: number; symmetry_index: number | null }[] }[]
}
