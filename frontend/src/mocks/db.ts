/**
 * MSW 가짜 서버의 메모리 DB. 디자인 v5 의 목업(DOGS·RES)을 API 모양(api-spec)으로 옮긴 것이다.
 * 새로고침하면 초기값으로 돌아간다. 백엔드가 붙으면 쓰지 않는다.
 */
import type { DogOut, SessionHistoryItem, StaffOut } from '../api/types'

export const MOCK_STAFF: StaffOut = {
  id: 'a1b2c3d4-0000-4000-8000-000000000001',
  login_id: 'kim01',
  name: '김담당',
  role: 'STAFF',
  institution: { id: 'a1b2c3d4-0000-4000-8000-0000000000aa', code: 'HANBIT', name: '한빛동물병원' },
}

const now = '2026-10-22T01:00:00Z'

function uuid(n: number, prefix = 'd'): string {
  return `${prefix}0000000-0000-4000-8000-${String(n).padStart(12, '0')}`
}

export interface MockSession extends SessionHistoryItem {
  dog_id: string
}

/** 디자인 RES 를 회차로 바꾼 것. 날짜는 2026년 기준. */
export const sessions: MockSession[] = [
  // 보리(d1): 8/20, 9/3, 9/18, 10/1, 10/14
  { id: uuid(8, 's'), dog_id: uuid(1), measured_on: '2026-08-20', weight_kg: 29.4, status: 'DONE', is_baseline: true, valid_passes: { LEFT: 5, RIGHT: 5 }, model_version: 'v0', reports: { OWNER: 'DONE', VET: 'DONE' } },
  { id: uuid(7, 's'), dog_id: uuid(1), measured_on: '2026-09-03', weight_kg: 28.9, status: 'DONE', is_baseline: false, valid_passes: { LEFT: 6, RIGHT: 6 }, model_version: 'v1', reports: { OWNER: 'FAILED', VET: 'FAILED' } },
  { id: uuid(6, 's'), dog_id: uuid(1), measured_on: '2026-09-18', weight_kg: 28.6, status: 'DONE', is_baseline: false, valid_passes: { LEFT: 4, RIGHT: 4 }, model_version: 'v1', reports: { OWNER: 'DONE', VET: 'DONE' } },
  { id: uuid(4, 's'), dog_id: uuid(1), measured_on: '2026-10-01', weight_kg: 28.3, status: 'DONE', is_baseline: false, valid_passes: { LEFT: 6, RIGHT: 5 }, model_version: 'v1', reports: { OWNER: 'DONE', VET: 'DONE' } },
  { id: uuid(1, 's'), dog_id: uuid(1), measured_on: '2026-10-14', weight_kg: 28.1, status: 'DONE', is_baseline: false, valid_passes: { LEFT: 6, RIGHT: 6 }, model_version: 'v1', reports: { OWNER: 'DONE', VET: 'DONE' } },
  // 콩이(d2): 9/28, 그리고 지금 측정 중
  { id: uuid(5, 's'), dog_id: uuid(2), measured_on: '2026-09-28', weight_kg: 3.2, status: 'DONE', is_baseline: true, valid_passes: { LEFT: 7, RIGHT: 6 }, model_version: 'v1', reports: { OWNER: 'DONE', VET: 'DONE' } },
  { id: uuid(9, 's'), dog_id: uuid(2), measured_on: '2026-10-22', weight_kg: 3.1, status: 'MEASURING', is_baseline: false, valid_passes: { LEFT: 2, RIGHT: 0 }, model_version: null, reports: null },
  // 두부(d3): 10/15 일부 유효
  { id: uuid(2, 's'), dog_id: uuid(3), measured_on: '2026-10-15', weight_kg: 11.0, status: 'DONE', is_baseline: true, valid_passes: { LEFT: 4, RIGHT: 3 }, model_version: 'v1', reports: { OWNER: 'DONE', VET: 'GENERATING' } },
  // 탄이(d4): 10/15 실패
  { id: uuid(3, 's'), dog_id: uuid(4), measured_on: '2026-10-15', weight_kg: 19.6, status: 'FAILED', is_baseline: false, valid_passes: { LEFT: 0, RIGHT: 0 }, model_version: 'v1', reports: null },
]

type DogRow = Omit<DogOut, 'session_count' | 'last_measured_on' | 'open_session_id'>

export const dogs: DogRow[] = [
  { id: uuid(1), name: '보리', breed: '골든 리트리버', weight_kg: 28.4, size_class: 'LARGE', size_class_manual: false, birth_year: 2019, sex: 'FEMALE_SPAYED', rehab_start_date: '2026-08-18', focus_limb: 'RH', baseline_session_id: null, memo: 'TPLO 수술 후 재활 9주차. 오른뒤 체중 부하 관찰 중', created_at: now, updated_at: now },
  { id: uuid(2), name: '콩이', breed: '말티즈', weight_kg: 3.2, size_class: 'SMALL', size_class_manual: false, birth_year: 2022, sex: 'FEMALE', rehab_start_date: null, focus_limb: null, baseline_session_id: null, memo: null, created_at: now, updated_at: now },
  { id: uuid(3), name: '두부', breed: '비글', weight_kg: 11.2, size_class: 'MEDIUM', size_class_manual: false, birth_year: 2021, sex: 'MALE_NEUTERED', rehab_start_date: '2026-10-01', focus_limb: 'LF', baseline_session_id: null, memo: null, created_at: now, updated_at: now },
  { id: uuid(4), name: '탄이', breed: '진돗개', weight_kg: 19.8, size_class: 'MEDIUM', size_class_manual: false, birth_year: 2017, sex: 'MALE', rehab_start_date: null, focus_limb: null, baseline_session_id: null, memo: null, created_at: now, updated_at: now },
]

export function classifySize(weightKg: number): DogOut['size_class'] {
  if (weightKg < 10) return 'SMALL'
  if (weightKg < 25) return 'MEDIUM'
  return 'LARGE'
}

/** DogOut 으로 조립: 회차 수, 마지막 측정일, 측정 중 회차 */
export function toDogOut(row: DogRow): DogOut {
  const mine = sessions.filter((s) => s.dog_id === row.id)
  const done = mine.filter((s) => s.status !== 'MEASURING')
  const last = [...done].sort((a, b) => b.measured_on.localeCompare(a.measured_on))[0]
  const open = mine.find((s) => s.status === 'MEASURING')
  return { ...row, session_count: mine.length, last_measured_on: last?.measured_on ?? null, open_session_id: open?.id ?? null }
}

/** 기준 회차: 담당자가 지정한 것, 없으면 가장 이른 DONE 회차 (api-spec DogOut) */
export function historyOf(dogId: string): SessionHistoryItem[] {
  const dog = dogs.find((d) => d.id === dogId)
  const mine = sessions.filter((s) => s.dog_id === dogId)
  const doneAsc = mine.filter((s) => s.status === 'DONE').sort((a, b) => a.measured_on.localeCompare(b.measured_on))
  const baselineId = dog?.baseline_session_id ?? doneAsc[0]?.id ?? null
  return mine
    .sort((a, b) => b.measured_on.localeCompare(a.measured_on))
    .map(({ dog_id: _dog, ...s }) => ({ ...s, is_baseline: s.id === baselineId }))
}

export function newId(): string {
  return crypto.randomUUID ? crypto.randomUUID() : uuid(Date.now() % 1_000_000_000, 'n')
}
