// 화면이 쓰는 데이터 모양. prototype/proto_app/store.py 의 dataclass 와 필드 이름·뜻이 같다(화면 계산 로직을 그대로 옮기려고).
// 백엔드에 있는 것(로그인·반려견·회차·촬영·관리자)은 backend.ts 가 API 응답을 이 모양으로 바꿔 넣고,
// 아직 없는 것(메모·바이탈·진단 이력·영상·회차 결과)은 가짜 서버 데이터(mocks/fixture.json)에서 온다.

export interface History {
  day: string // YYYY-MM-DD
  kind: string // 진단 | 수술 | 재활
  title: string
  site: string // LF | RF | LH | RH | SP | ''
  by: string // 집도의·진단의
  author: string // 기록한 사람
}

export interface Vital {
  day: string
  kg: string
  temp: string
  hr: string
  sbp: string
  dbp: string
  author: string
}

export interface Note {
  id: string
  at: string // YYYY-MM-DD HH:MM
  author: string
  cat: string // 진료 기록 S|O|A|P, 메모 주의|보호자|예약|기타
  text: string
  important: boolean
  revs: [string, string, string][] // [at, author, text] 오래된 것부터
  rid: string
}

export interface Image {
  id: string
  day: string
  kind: string // pre | post | xray | photo
  caption: string
  path: string
  author: string
}

export interface Dog {
  id: string
  name: string
  breed: string
  birth: string
  kg: string
  sex: string
  size: string
  size_manual: boolean
  rehab: string
  focus: string | null
  memo: string
  base: string | null
  no: string
  owner: string
  phone: string
  stage: string
  stage_day: string
  history: History[]
  vitals: Vital[] // 최신이 앞
  notes: Note[] // 최신이 앞
  images: Image[]
  version: number
  /** 백엔드 반려견만: 측정 중인 회차 id */
  open_session_id?: string | null
}

export type Metrics = Record<string, Record<string, number>> // {다리: {코드: 값}}

export interface Result {
  id: string
  dog: string
  date: string // "10월 15일"
  time: string
  st: string // ok | part | fail
  w: string
  model: string
  sym: number
  rom: number
  sL: number
  sR: number
  j: [string, number, number][]
  ps: [number, number] // (측정한 통과, 사용한 통과)
  ex: [string, number][]
  rep: boolean
  videos: string[]
  day: string
  by: string
  m: Metrics
  src: string
  /** 백엔드 결과만: 수치를 낸 보행 묶음 이름(속보·평보·보행 유형 미판별) */
  gait?: string
  /** 백엔드 결과만: 분석 실패 사유 문구 */
  fail_msg?: string
  /** 백엔드 결과만: 보행 유형(평보·속보·보행 유형 미판별)별 다리 수치. m 은 그중 대표 보행 하나 */
  mg?: Record<string, Metrics>
}

export interface Job {
  id: string
  dog: string
  n: number
  w: string
  started: number // ms (Date.now 기준)
  videos: string[]
  result_id: string | null
  notified: boolean
  by: string
  /** 백엔드 회차(id = 회차 id). 진행은 서버 상태로만 끝난다 */
  remote?: boolean
}

export interface DeviceCode {
  id: string
  inst: string
  code: string
  max_accounts: number
  revoked: boolean
  note: string
  created: string
}

export interface Staff {
  id: string
  login_id: string
  password: string
  name: string
  inst: string
  email: string
  role: string // ADMIN | STAFF | CLIENT
  active: boolean
  device_code: string
  joined: string
  reset_token: string
  reset_until: number
}

export interface Account {
  id: string
  login_id: string
  password: string
  name: string
  loc: string
  dev: string
  joined: string
  dogs: Dog[]
  results: Result[] // 최신 회차가 앞
  jobs: Job[]
  notif_on: boolean
  code: string
  contract_ends: string | null
}

/** 실측 회차(demo_sessions.json 의 한 항목). 무릎 곡선·보행 속도 등 */
export interface RealSession {
  id: string
  source: string
  grade?: string
  video_names: string[]
  passes: { L: number; R: number }
  cycles: number
  walk_speed?: number
  fps?: number
  date?: string
  metrics: Metrics
  knee_curve: Record<string, number[]>
  synthetic?: string[]
  dog?: { breed: string | null; size: string | null; age: string | null }
}
