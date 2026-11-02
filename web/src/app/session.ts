// 로그인 상태·알림(토스트)·화면 이동. prototype/proto_app/main.py 의 current_staff·current·redirect·page·finished_notices 와 같다.
import { activeJobs, db, dogOf, effectiveRole, getAccount } from '../store/db'
import { finish_due_jobs } from '../views/analysis'
import type { Account, Staff } from '../store/types'

const COOKIE = 'pp_acct' // 로그인한 담당자 id (시제품의 쿠키 이름 그대로)
const TOAST = 'pp_toast'

function read(k: string): string {
  try {
    return localStorage.getItem(k) || ''
  } catch {
    return ''
  }
}

export function currentStaff(): Staff | undefined {
  const s = db.staff[read(COOKIE)]
  return s && s.active ? s : undefined
}

export class ContractExpired extends Error {}

/** 로그인한 담당자의 기관. 계약이 끝났으면 ContractExpired(만료 안내로 보냄) */
export function current(): Account | undefined {
  const s = currentStaff()
  if (!s) return undefined
  if (effectiveRole(s) === 'GUEST') throw new ContractExpired()
  const a = getAccount(s.inst)
  if (a) finish_due_jobs(a)
  return a
}

export function setLogin(staffId: string | null): void {
  try {
    if (staffId) localStorage.setItem(COOKIE, staffId)
    else localStorage.removeItem(COOKIE)
  } catch {
    /* 저장 못 하면 이번 탭만 */
  }
}

export function setToast(msg: string): void {
  try {
    if (msg) sessionStorage.setItem(TOAST, msg)
  } catch {
    /* 무시 */
  }
}

export function takeToast(): string {
  try {
    const t = sessionStorage.getItem(TOAST) || ''
    sessionStorage.removeItem(TOAST)
    return t
  } catch {
    return ''
  }
}

/** 끝났지만 아직 알리지 않은 분석 */
export function finished_notices(acct: Account, skipJob = ''): string[] {
  const out: string[] = []
  for (const job of acct.jobs) {
    if (job.result_id && !job.notified && job.id !== skipJob) {
      job.notified = true
      const d = dogOf(acct, job.dog)
      out.push(`${d ? d.name : ''} 분석이 끝났어요`)
    }
  }
  return out
}

/** 화면 이동 결과: 이동할 주소와 알림. 폼 처리 함수(actions)가 돌려준다 */
export interface Go {
  to: string
  toast?: string
}
export const redirect = (to: string, toast = ''): Go => ({ to, toast })
export const need_login = (): Go => redirect('/login', '로그인해 주세요')

export const hasActive = (acct?: Account): boolean => !!acct && activeJobs(acct).length > 0
