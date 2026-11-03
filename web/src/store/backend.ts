// 백엔드 연결. 화면은 저장소(db)만 보고, 여기서 백엔드 응답을 db 모양으로 바꿔 넣는다.
// - 가짜 서버 모드(vite --mode mock): 백엔드 없이 시연 데이터(fixture)만 쓴다. 웹 시제품과 픽셀 비교할 때 쓴다.
// - 기본 모드: 로그인·가입·내 정보·반려견·회차 시작·영상 올리기·관리자는 백엔드 develop API 를 부른다.
//   백엔드에 아직 없는 메모·바이탈·진단 이력·영상·회차 결과는 이 브라우저 저장소에만 둔다(백엔드 요청 문서 1~9절).
import { api, tokenStore, type DogOut, type StaffOut } from '../api/client'
import { db, changed } from './db'
import type { Account, Dog, Staff } from './types'
import { syncSessions } from './sessions_backend'

/** 백엔드에서 읽어 온 기관 id(시연 기관 demo 와 구분) */
const remote = new Set<string>()
export const isRemote = (instId: string): boolean => remote.has(instId)

export const MOCK = import.meta.env.MODE === 'mock'

const SEX_IN: Record<string, string> = { MALE: 'm', FEMALE: 'f', MALE_NEUTERED: 'mn', FEMALE_SPAYED: 'fs' }
export const SEX_OUT: Record<string, string> = { m: 'MALE', f: 'FEMALE', mn: 'MALE_NEUTERED', fs: 'FEMALE_SPAYED' }
const SIZE_IN: Record<string, string> = { SMALL: 'S', MEDIUM: 'M', LARGE: 'L' }
export const SIZE_OUT: Record<string, string> = { S: 'SMALL', M: 'MEDIUM', L: 'LARGE' }

/** DogOut → 화면용 Dog. 백엔드에 없는 칸(동물번호·보호자·단계·기록들)은 이미 이 브라우저에 있던 값을 그대로 둔다 */
export function toDog(o: DogOut, prev?: Dog): Dog {
  return {
    no: '', owner: '', phone: '', stage: 'rehab', stage_day: '', history: [], vitals: [], notes: [], images: [],
    ...prev,
    id: o.id,
    name: o.name,
    breed: o.breed,
    birth: o.birth_year ? String(o.birth_year) : '',
    kg: String(o.weight_kg),
    sex: SEX_IN[o.sex || ''] || 'm',
    size: SIZE_IN[o.size_class] || 'M',
    size_manual: o.size_class_manual,
    rehab: o.rehab_start_date || '',
    focus: o.focus_limb,
    memo: o.memo || '',
    base: o.baseline_session_id,
    version: o.version,
    open_session_id: o.open_session_id,
  }
}

function toStaff(s: StaffOut): Staff {
  return {
    id: s.id, login_id: s.login_id, password: '', name: s.name, inst: s.institution.id, email: s.email || '',
    role: s.role, active: true, device_code: '', joined: '', reset_token: '', reset_until: 0,
  }
}

/** 로그인한 담당자와 그 기관·반려견을 백엔드에서 읽어 db 에 넣는다. 돌려주는 값 = 담당자 id */
export async function syncFromBackend(me?: StaffOut): Promise<string> {
  const s = me ?? (await api.me())
  const inst = s.institution
  const prev = db.accounts[inst.id]
  const base: Account = prev ?? {
    id: inst.id, login_id: '', password: '', name: inst.name, loc: '-', dev: '-', joined: '', notif_on: true,
    results: [], jobs: [], dogs: [], code: '', contract_ends: null,
  }
  const acct: Account = { ...base, name: inst.name, code: inst.code, contract_ends: inst.contract_ends_at }
  db.accounts[inst.id] = acct
  remote.add(inst.id)
  const st = toStaff(s)
  db.staff[st.id] = st
  if (s.effective_role !== 'GUEST' && (s.role === 'CLIENT')) {
    const dogs: DogOut[] = []
    for (let page = 1; page < 50; page++) {
      const r = await api.dogs(page, 100)
      dogs.push(...r.items)
      if (dogs.length >= r.total || !r.items.length) break
    }
    acct.dogs = dogs.map((o) => toDog(o, acct.dogs.find((d) => d.id === o.id)))
    await syncSessions(acct).catch(() => undefined)   // 이 브라우저에서 연 회차·측정 중 회차의 상태·결과
  }
  changed()
  return st.id
}

/** 앱을 켰을 때: 저장된 토큰이 살아 있으면 다시 읽는다. 돌려주는 값 = 담당자 id(없으면 null) */
export async function restore(): Promise<string | null> {
  if (MOCK || !tokenStore.get() || tokenStore.isExpired()) return null
  try {
    const me = await api.me()
    const sid = await syncFromBackend(me)
    if (me.role === 'ADMIN' || me.role === 'STAFF') await syncAdmin() // 새로고침해도 관리 화면에 백엔드 기관이 남게(로그인 때와 같다)
    return sid
  } catch {
    tokenStore.clear()
    return null
  }
}

/** 크림오프 관리 화면: 기관·디바이스 코드·담당자를 백엔드에서 읽어 db 에 넣는다 */
export async function syncAdmin(): Promise<void> {
  const insts = (await api.institutions()).items
  for (const i of insts) {
    const prev = db.accounts[i.id]
    db.accounts[i.id] = {
      ...(prev ?? { id: i.id, login_id: '', password: '', loc: '-', dev: '-', notif_on: true, results: [], jobs: [], dogs: [] }),
      name: i.name, code: i.code, contract_ends: i.contract_ends_at, joined: kjoined(i.created_at),
    } as Account
    remote.add(i.id)
    for (const c of (await api.deviceCodes(i.id)).items) {
      db.codes[c.id] = { id: c.id, inst: i.id, code: c.code.replace(/-/g, ''),  // 서버 표기의 하이픈은 빼고 저장(show_code 가 다시 넣는다)
        max_accounts: c.max_accounts, revoked: !!c.revoked_at, note: c.note || '', created: c.created_at.slice(0, 10) }
    }
    for (const s of (await api.institutionStaff(i.id)).items) {
      db.staff[s.id] = {
        ...(db.staff[s.id] ?? { password: '', reset_token: '', reset_until: 0 }),
        id: s.id, login_id: s.login_id, name: s.name, inst: i.id, email: s.email || '', role: s.role, active: s.is_active,
        device_code: s.device_code_id || '', joined: kjoined(s.created_at),
      } as Staff
    }
  }
  changed()
}

/** "2026년 10월 2일" (시제품의 가입일 표기) */
function kjoined(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`
}

export { api, tokenStore }
