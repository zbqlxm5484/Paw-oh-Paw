// 브라우저 안 저장소. prototype/proto_app/store.py 의 Store·Account 와 같은 일을 한다.
// 처음에는 시연 데이터(mocks/fixture.json)를 불러오고, 백엔드에 붙으면 backend.ts 가 API 응답으로 해당 부분을 덮어쓴다.
// 화면은 useDb() 로 바뀔 때마다 다시 그린다.
import { useSyncExternalStore } from 'react'
import fixtureRaw from '../mocks/fixture.json'
import { ANALYSIS_SEC } from '../config'
import type { Account, DeviceCode, Dog, Job, RealSession, Result, Staff } from './types'

export interface Db {
  accounts: Record<string, Account>
  staff: Record<string, Staff>
  codes: Record<string, DeviceCode>
  sessions: RealSession[]
}

const DAY = 86400000

export function isoToday(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function isoShift(s: string, days: number): string {
  const [y, m, d] = s.slice(0, 10).split('-').map(Number)
  const t = new Date(y, m - 1, d + days)
  const iso = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`
  return iso + s.slice(10)
}

/** "10월 15일" (store.kdate) */
export function kdate(iso?: string): string {
  const [, m, d] = (iso || isoToday()).split('-').map(Number)
  return `${m}월 ${d}일`
}

const ISO = /^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$/

/** 내보낸 날과 오늘의 차이만큼 날짜를 민다(매일 같은 모양). 생년(birth)·가입일(한국어 문장)은 그대로 */
function shiftDates<T>(o: T, days: number, key = ''): T {
  if (!days) return o
  if (typeof o === 'string') return (ISO.test(o) && key !== 'birth' ? isoShift(o, days) : o) as T
  if (Array.isArray(o)) return o.map((v) => shiftDates(v, days, key)) as T
  if (o && typeof o === 'object') {
    const out: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(o)) out[k] = shiftDates(v, days, k)
    return out as T
  }
  return o
}

function fromFixture(only?: string): Db {
  const fx = fixtureRaw as unknown as {
    exported_on: string
    accounts: (Omit<Account, 'jobs'> & { jobs: (Omit<Job, 'started'> & { started_ago: number })[] })[]
    staff: Staff[]
    codes: DeviceCode[]
    sessions: RealSession[]
  }
  const days = Math.round((new Date(isoToday()).getTime() - new Date(fx.exported_on).getTime()) / DAY)
  const now = Date.now()
  const accounts: Record<string, Account> = {}
  for (const a0 of fx.accounts) {
    if (only && a0.id !== only) continue
    const a = shiftDates(structuredClone(a0), days)
    for (const r of a.results) r.date = r.day ? kdate(r.day) : r.date
    accounts[a.id] = {
      ...a,
      jobs: a.jobs.map(({ started_ago, ...j }) => ({ ...j, started: now - started_ago * 1000 })),
    } as Account
  }
  return {
    accounts,
    staff: Object.fromEntries(fx.staff.map((s) => [s.id, s])),
    codes: Object.fromEntries(shiftDates(fx.codes, days).map((c) => [c.id, c])),
    sessions: fx.sessions,
  }
}

export const db: Db = fromFixture()

/** 시연 데이터의 기관 하나를 처음 상태로 새로 만든다(seed.demo_account) */
export const freshAccount = (id: string): Account => fromFixture(id).accounts[id]

// ── 바뀜 알림 ──
let version = 0
const subs = new Set<() => void>()
export function changed(): void {
  version += 1
  subs.forEach((f) => f())
}
export function useDb(): number {
  return useSyncExternalStore(
    (f) => {
      subs.add(f)
      return () => subs.delete(f)
    },
    () => version,
  )
}

// ── id ── (store.new_id: 접두어 + 숫자. 시연 데이터의 가장 큰 번호 뒤부터)
let seq = 100000
export function new_id(prefix: string): string {
  seq += 1
  return `${prefix}${seq}`
}

// ── Account 메서드 ──
export const dogOf = (a: Account, id: string | null | undefined): Dog | undefined => a.dogs.find((d) => d.id === id)
export const resultOf = (a: Account, id: string | null | undefined): Result | undefined => a.results.find((r) => r.id === id)
export const jobOf = (a: Account, id: string | null | undefined): Job | undefined => a.jobs.find((j) => j.id === id)
export const activeJobs = (a: Account): Job[] => a.jobs.filter((j) => j.result_id == null)
export const contractStatus = (a: Account): string => (a.contract_ends && a.contract_ends < isoToday() ? 'EXPIRED' : 'ACTIVE')
export const jobProgress = (j: Job): number => Math.min(j.remote ? 4.9 : 5, ((Date.now() - j.started) / 1000 / ANALYSIS_SEC) * 5)   // 백엔드 회차는 서버 완료 전까지 마지막 단계에서 기다린다

// ── Store 메서드 ──
export const getAccount = (id: string | null | undefined): Account | undefined => (id ? db.accounts[id] : undefined)
export const byLogin = (login: string): Staff | undefined => Object.values(db.staff).find((s) => s.login_id === login)
export const staffOf = (inst: string): Staff[] => Object.values(db.staff).filter((s) => s.inst === inst)
export const codesOf = (inst: string): DeviceCode[] => Object.values(db.codes).filter((c) => c.inst === inst)
export const byCode = (code: string): DeviceCode | undefined => Object.values(db.codes).find((c) => c.code === code)
export const activeCount = (codeId: string): number =>
  Object.values(db.staff).filter((s) => s.device_code === codeId && s.active).length
export function effectiveRole(s: Staff): string {
  const a = getAccount(s.inst)
  return s.role === 'CLIENT' && a && contractStatus(a) === 'EXPIRED' ? 'GUEST' : s.role
}

export const CODE_CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
/** 디바이스 코드 입력 정리: 하이픈·공백 제거, 대문자. 형식이 틀리면 빈 문자열 */
export function norm_code(raw: string): string {
  const c = [...(raw || '').toUpperCase()].filter((ch) => ch !== '-' && ch !== ' ').join('')
  return c.length === 20 && [...c].every((ch) => CODE_CHARS.includes(ch)) ? c : ''
}
export const show_code = (c: string): string => [0, 5, 10, 15].map((i) => c.slice(i, i + 5)).join('-')
