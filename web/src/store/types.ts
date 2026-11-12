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
  /** 백엔드 이력만: 서버 id(고치기·지우기) */
  id?: string
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
  /** 방문일(YYYY-MM-DD). 없으면 쓴 시각(at)의 날짜 */
  day?: string
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
  /** 백엔드 반려견만: 목록에서 온 보호자 연락처 뒤 4자리(목록 응답에는 전체 번호가 없다) */
  phone4?: string
  /** 백엔드 반려견만(271): 서버가 계산한 홈 배지·최근 변동·최근 대칭 점수. 예전 서버면 없음 → 화면이 이 브라우저의 기록으로 계산 */
  srv?: {
    badges?: { code: string; title: string | null; site: string | null; on: string }[]
    changes?: { code: string; on: string; delta: number | null }[]
    last_symmetry?: number | null
    /** 검색용 최근 수술·진단 이름(차트를 열기 전에도 찾게) */
    dx_text?: string
    /** 최근 진단 이름(홈 병명 칸) */
    diag?: string
  }
  /** 백엔드 반려견만: 바이탈·진단 이력·메모를 서버에서 읽어 왔으면 true(아니면 목록의 최근 바이탈 한 줄만 있다) */
  chart_loaded?: boolean
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
  /** 백엔드 결과만: 대표 보행 묶음의 다리(LF·RF·LH·RH)별 쓴 걸음 수(n_passes 최댓값). 측정 신뢰도·남은 촬영 수(views/quality.ts) */
  np?: Record<string, number>
  /** 백엔드 결과만: 측정 이력(15.8)에서의 순번(0 = 가장 최근). 같은 측정일 회차의 순서를 서버·앱과 맞추는 데 쓴다 */
  ord?: number
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
  /** 백엔드 회차의 지금 서버 상태(폴링 때마다 갱신): 회차 상태, 촬영 수, 분석이 끝난(DONE·FAILED) 촬영 수 */
  srv?: { status: string; total: number; done: number }
  /** 시연 데이터에 처음부터 있던 분석 중 작업: 진행 화면 견본으로 두고 끝내지 않는다 */
  hold?: boolean
}

export interface DeviceCode {
  id: string
  inst: string
  code: string
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
