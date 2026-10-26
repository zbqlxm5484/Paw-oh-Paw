/**
 * MSW 가짜 서버의 메모리 DB. 디자인 v5 의 목업(DOGS·RES)을 API 모양(api-spec)으로 옮긴 것이다.
 * 새로고침하면 초기값으로 돌아간다. 백엔드가 붙으면 쓰지 않는다.
 */
import type { CameraSide, DogOut, PassOut, Reason, SessionDetailOut, SessionHistoryItem, SessionOut, ShotOut, SizeClass, StaffOut } from '../api/types'

export const MOCK_STAFF: StaffOut = {
  id: 'a1b2c3d4-0000-4000-8000-000000000001',
  login_id: 'kim01',
  name: '김담당',
  role: 'STAFF',
  institution: { id: 'a1b2c3d4-0000-4000-8000-0000000000aa', code: 'HANBIT', name: '한빛동물병원' },
}

const now = '2026-10-22T01:00:00Z'
export const RECOMMENDED_PASSES = 8

function uuid(n: number, prefix = 'd'): string {
  return `${prefix}0000000-0000-4000-8000-${String(n).padStart(12, '0')}`
}

/* ---------- 사유 문구 (api-spec 11절) ---------- */
export const REASONS: Record<string, string> = {
  ANALYSIS_FAILED: '분석에 실패했습니다.',
  ANALYSIS_TIMEOUT: '분석이 너무 오래 걸려 중단했습니다.',
  AGGREGATION_FAILED: '회차 수치를 계산하지 못했습니다.',
  NO_VALID_PASS: '쓸 수 있는 통과가 없습니다. 다시 찍어 주세요.',
  FEW_VALID_PASSES: '쓸 수 있는 통과가 일부만 있습니다.',
  MAT_NOT_FOUND: '측정 구간(매트)을 찾지 못했습니다. 매트가 화면에 다 보이게 다시 찍어 주세요.',
  RUNNING: '뛰었습니다. 천천히 걷게 해 주세요.',
  STOPPED: '중간에 멈췄습니다.',
  SITTING: '중간에 앉거나 엎드렸습니다.',
  TURNED: '중간에 돌아섰습니다.',
  OCCLUDED: '몸이 가려졌습니다.',
  GAIT_PACE: '측대보라 수치 계산에서 뺐습니다.',
  GAIT_OTHER: '평보·속보가 아니라 수치 계산에서 뺐습니다.',
  NO_PASS_FOR_LIMB: '이 다리를 잴 유효 통과가 없습니다. 반대 방향으로도 걷게 해 주세요.',
  NOT_ENOUGH_CYCLES: '보행 주기가 부족해 계산하지 못했습니다.',
  LOW_CONFIDENCE: '관절점 인식이 불안정해 계산하지 못했습니다.',
  REPORT_CHECK_FAILED: '보고서 검사를 통과하지 못해 내보내지 않았습니다.',
  REPORT_FAILED: '보고서를 만들지 못했습니다.',
  VIDEO_RENDER_FAILED: '결과 영상을 만들지 못했습니다. 판정 결과는 그대로 볼 수 있습니다.',
  BELOW_MIN_SPEC: '최저 사양(640×360, 30fps, 4 Mbps)보다 낮은 영상입니다. 결과가 부정확할 수 있습니다.',
  ASPECT_NOT_16_9: '화면 비율이 16:9가 아닙니다. 결과가 부정확할 수 있습니다.',
  RECOMMENDED_MET: '방향별 권장 통과 수를 채웠습니다. 측정을 끝내도 됩니다.',
  ONE_SIDE_ONLY: '좌우 비교: 측정 조건상 비교할 수 없습니다. 반대 방향으로도 걷게 해 주세요.',
}
export const reason = (code: string): Reason => ({ code, message: REASONS[code] ?? code })

/* ---------- 회차·촬영 ---------- */
export interface MockShot extends ShotOut {
  session_id: string
}

export interface MockSession extends SessionOut {
  shots: MockShot[]
  /** 완료된 견본 회차의 방향별 유효 통과 수(촬영 없이 숫자만) */
  seed_valid?: { LEFT: number; RIGHT: number }
  reports: SessionHistoryItem['reports']
  is_baseline_seed?: boolean
}

const staffBrief = { id: MOCK_STAFF.id, name: MOCK_STAFF.name }

function seedDone(n: number, dogId: string, measured_on: string, weight: number, size: SizeClass, valid: { LEFT: number; RIGHT: number }, model: string, reports: MockSession['reports'], status: SessionOut['status'] = 'DONE'): MockSession {
  return {
    id: uuid(n, 's'), dog_id: dogId, staff: staffBrief, measured_on, weight_kg: weight, size_class: size, status,
    fail_reason: status === 'FAILED' ? reason('AGGREGATION_FAILED') : null,
    model_name: status === 'DONE' ? 'pga-pose' : null, model_version: status === 'DONE' ? model : null,
    completed_at: `${measured_on}T05:00:00Z`, aggregated_at: status === 'DONE' ? `${measured_on}T05:01:00Z` : null, created_at: `${measured_on}T04:30:00Z`,
    shots: [], seed_valid: valid, reports,
  }
}

const bothDone = { OWNER: 'DONE', VET: 'DONE' } as const

/** 디자인 RES 를 회차로 바꾼 것. 날짜는 2026년 기준. */
export const sessions: MockSession[] = [
  // 보리(d1): 8/20, 9/3, 9/18, 10/1, 10/14
  seedDone(8, uuid(1), '2026-08-20', 29.4, 'LARGE', { LEFT: 5, RIGHT: 5 }, 'v0', bothDone),
  seedDone(7, uuid(1), '2026-09-03', 28.9, 'LARGE', { LEFT: 6, RIGHT: 6 }, 'v1', { OWNER: 'FAILED', VET: 'FAILED' }),
  seedDone(6, uuid(1), '2026-09-18', 28.6, 'LARGE', { LEFT: 4, RIGHT: 4 }, 'v1', bothDone),
  seedDone(4, uuid(1), '2026-10-01', 28.3, 'LARGE', { LEFT: 6, RIGHT: 5 }, 'v1', bothDone),
  seedDone(1, uuid(1), '2026-10-14', 28.1, 'LARGE', { LEFT: 6, RIGHT: 6 }, 'v1', bothDone),
  // 콩이(d2): 9/28 완료, 그리고 지금 측정 중(촬영 2건)
  seedDone(5, uuid(2), '2026-09-28', 3.2, 'SMALL', { LEFT: 7, RIGHT: 6 }, 'v1', bothDone),
  {
    id: uuid(9, 's'), dog_id: uuid(2), staff: staffBrief, measured_on: '2026-10-23', weight_kg: 3.1, size_class: 'SMALL', status: 'MEASURING',
    fail_reason: null, model_name: null, model_version: null, completed_at: null, aggregated_at: null, created_at: '2026-10-23T00:10:00Z', reports: null,
    shots: [
      { session_id: uuid(9, 's'), id: uuid(902, 'h'), seq_no: 2, status: 'ANALYZING', fail_reason: null, validity: null, validity_reason: null, video_status: 'PENDING', below_min_spec: false, passes: [], uploaded_at: '2026-10-23T00:14:02Z', analyzed_at: null },
      { session_id: uuid(9, 's'), id: uuid(901, 'h'), seq_no: 1, status: 'DONE', fail_reason: null, validity: 'PARTIAL', validity_reason: reason('FEW_VALID_PASSES'), video_status: 'READY', below_min_spec: false,
        passes: [
          { pass_no: 1, camera_side: 'LEFT', gait_type: 'TROT', is_valid: true, exclude_reason: null, start_frame: 30, end_frame: 171 },
          { pass_no: 2, camera_side: 'LEFT', gait_type: 'OTHER', is_valid: false, exclude_reason: reason('RUNNING'), start_frame: 190, end_frame: 260 },
          { pass_no: 3, camera_side: 'LEFT', gait_type: 'TROT', is_valid: true, exclude_reason: null, start_frame: 280, end_frame: 400 },
        ],
        uploaded_at: '2026-10-23T00:12:02Z', analyzed_at: '2026-10-23T00:12:31Z' },
    ],
  },
  // 두부(d3): 10/15 완료
  seedDone(2, uuid(3), '2026-10-15', 11.0, 'MEDIUM', { LEFT: 4, RIGHT: 3 }, 'v1', { OWNER: 'DONE', VET: 'GENERATING' }),
  // 탄이(d4): 10/15 실패
  seedDone(3, uuid(4), '2026-10-15', 19.6, 'MEDIUM', { LEFT: 0, RIGHT: 0 }, 'v1', null, 'FAILED'),
]

type DogRow = Omit<DogOut, 'session_count' | 'last_measured_on' | 'open_session_id'>

export const dogs: DogRow[] = [
  { id: uuid(1), name: '보리', breed: '골든 리트리버', weight_kg: 28.4, size_class: 'LARGE', size_class_manual: false, birth_year: 2019, sex: 'FEMALE_SPAYED', rehab_start_date: '2026-08-18', focus_limb: 'RH', baseline_session_id: null, memo: 'TPLO 수술 후 재활 9주차. 오른뒤 체중 부하 관찰 중', created_at: now, updated_at: now },
  { id: uuid(2), name: '콩이', breed: '말티즈', weight_kg: 3.2, size_class: 'SMALL', size_class_manual: false, birth_year: 2022, sex: 'FEMALE', rehab_start_date: null, focus_limb: null, baseline_session_id: null, memo: null, created_at: now, updated_at: now },
  { id: uuid(3), name: '두부', breed: '비글', weight_kg: 11.2, size_class: 'MEDIUM', size_class_manual: false, birth_year: 2021, sex: 'MALE_NEUTERED', rehab_start_date: '2026-10-01', focus_limb: 'LF', baseline_session_id: null, memo: null, created_at: now, updated_at: now },
  { id: uuid(4), name: '탄이', breed: '진돗개', weight_kg: 19.8, size_class: 'MEDIUM', size_class_manual: false, birth_year: 2017, sex: 'MALE', rehab_start_date: null, focus_limb: null, baseline_session_id: null, memo: null, created_at: now, updated_at: now },
]

export function classifySize(weightKg: number): SizeClass {
  if (weightKg < 10) return 'SMALL'
  if (weightKg < 25) return 'MEDIUM'
  return 'LARGE'
}

export function findDog(id: string | readonly string[] | undefined) {
  return dogs.find((d) => d.id === id)
}

/** DogOut 으로 조립: 회차 수, 마지막 측정일, 측정 중 회차 */
export function toDogOut(row: DogRow): DogOut {
  const mine = sessions.filter((s) => s.dog_id === row.id)
  const done = mine.filter((s) => s.status !== 'MEASURING')
  const last = [...done].sort((a, b) => b.measured_on.localeCompare(a.measured_on))[0]
  const open = mine.find((s) => s.status === 'MEASURING')
  return { ...row, session_count: mine.length, last_measured_on: last?.measured_on ?? null, open_session_id: open?.id ?? null }
}

/** 방향별 유효 통과 수 */
export function validPasses(s: MockSession): { LEFT: number; RIGHT: number } {
  if (s.seed_valid) return s.seed_valid
  const out = { LEFT: 0, RIGHT: 0 }
  for (const sh of s.shots) for (const p of sh.passes) if (p.is_valid) out[p.camera_side] += 1
  return out
}

/** 기준 회차: 담당자가 지정한 것, 없으면 가장 이른 DONE 회차 (api-spec DogOut) */
export function historyOf(dogId: string): SessionHistoryItem[] {
  const dog = findDog(dogId)
  const mine = sessions.filter((s) => s.dog_id === dogId)
  const doneAsc = mine.filter((s) => s.status === 'DONE').sort((a, b) => a.measured_on.localeCompare(b.measured_on))
  const baselineId = dog?.baseline_session_id ?? doneAsc[0]?.id ?? null
  return mine
    .sort((a, b) => b.measured_on.localeCompare(a.measured_on) || b.created_at.localeCompare(a.created_at))
    .map((s) => ({ id: s.id, measured_on: s.measured_on, weight_kg: s.weight_kg, status: s.status, is_baseline: s.id === baselineId, valid_passes: validPasses(s), model_version: s.model_version, reports: s.reports }))
}

export function toSessionOut(s: MockSession): SessionOut {
  const { shots: _shots, seed_valid: _sv, reports: _r, is_baseline_seed: _b, ...out } = s
  return out
}

export function toSessionDetail(s: MockSession): SessionDetailOut {
  const dog = findDog(s.dog_id)!
  const vp = validPasses(s)
  const notices: Reason[] = []
  if (vp.LEFT >= RECOMMENDED_PASSES && vp.RIGHT >= RECOMMENDED_PASSES) notices.push(reason('RECOMMENDED_MET'))
  else if ((vp.LEFT > 0) !== (vp.RIGHT > 0)) notices.push(reason('ONE_SIDE_ONLY'))
  return {
    ...toSessionOut(s),
    dog: { id: dog.id, name: dog.name, breed: dog.breed, weight_kg: dog.weight_kg, size_class: dog.size_class },
    progress: { LEFT: { valid_passes: vp.LEFT, recommended: RECOMMENDED_PASSES }, RIGHT: { valid_passes: vp.RIGHT, recommended: RECOMMENDED_PASSES } },
    notices,
    shots: [...s.shots].sort((a, b) => b.seq_no - a.seq_no).map(({ session_id: _sid, ...sh }) => sh),
  }
}

export function newId(): string {
  return crypto.randomUUID ? crypto.randomUUID() : uuid(Date.now() % 1_000_000_000, 'n')
}

/* ---------- 분석 흉내: 업로드 → 분석 요청 → 분석 중 → 완료/실패 ---------- */
let sideToggle: CameraSide = 'LEFT'

/** 파일 이름에 fail 이 들어 있으면 실패, run 이면 무효(뛰었음), 나머지는 유효·일부 유효가 섞인 통과를 만든다. */
export function simulateAnalysis(shot: MockShot, fileName: string) {
  const name = fileName.toLowerCase()
  const t = (ms: number, fn: () => void) => window.setTimeout(fn, ms)
  t(1200, () => { if (shot.status === 'UPLOADED') shot.status = 'SUBMITTED' })
  t(2600, () => { if (shot.status === 'SUBMITTED') shot.status = 'ANALYZING' })
  t(6000, () => {
    if (shot.status !== 'ANALYZING') return
    if (name.includes('fail')) {
      shot.status = 'FAILED'
      shot.fail_reason = reason('ANALYSIS_FAILED')
      return
    }
    shot.status = 'DONE'
    shot.analyzed_at = new Date().toISOString()
    const side: CameraSide = sideToggle
    sideToggle = sideToggle === 'LEFT' ? 'RIGHT' : 'LEFT'
    const passes: PassOut[] = []
    if (name.includes('run')) {
      passes.push({ pass_no: 1, camera_side: side, gait_type: 'OTHER', is_valid: false, exclude_reason: reason('RUNNING'), start_frame: 20, end_frame: 140 })
      shot.validity = 'INVALID'
      shot.validity_reason = reason('NO_VALID_PASS')
    } else {
      const n = 2 + Math.floor(Math.random() * 2)
      for (let i = 0; i < n; i++) {
        const bad = i === 1 && Math.random() < 0.5
        passes.push({ pass_no: i + 1, camera_side: side, gait_type: bad ? 'OTHER' : 'TROT', is_valid: !bad, exclude_reason: bad ? reason('STOPPED') : null, start_frame: 30 + i * 150, end_frame: 150 + i * 150 })
      }
      const anyBad = passes.some((p) => !p.is_valid)
      shot.validity = anyBad ? 'PARTIAL' : 'VALID'
      shot.validity_reason = anyBad ? reason('FEW_VALID_PASSES') : null
    }
    shot.passes = passes
    t(2500, () => { if (shot.status === 'DONE') shot.video_status = 'READY' })
  })
}

/** 측정 종료 → 집계 → 완료(유효 통과가 하나도 없으면 실패) */
export function simulateAggregation(s: MockSession) {
  window.setTimeout(() => {
    if (s.status !== 'AGGREGATING') return
    const vp = validPasses(s)
    if (vp.LEFT + vp.RIGHT === 0) {
      s.status = 'FAILED'
      s.fail_reason = reason('AGGREGATION_FAILED')
      return
    }
    s.status = 'DONE'
    s.model_name = 'pga-pose'
    s.model_version = 'v1'
    s.aggregated_at = new Date().toISOString()
    s.reports = { OWNER: 'PENDING', VET: 'PENDING' }
    window.setTimeout(() => { if (s.reports) s.reports = { OWNER: 'DONE', VET: 'DONE' } }, 4000)
  }, 4500)
}
