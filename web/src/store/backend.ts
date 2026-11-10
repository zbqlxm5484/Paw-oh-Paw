// 백엔드 연결. 화면은 저장소(db)만 보고, 여기서 백엔드 응답을 db 모양으로 바꿔 넣는다.
// - 가짜 서버 모드(vite --mode mock): 백엔드 없이 시연 데이터(fixture)만 쓴다. 웹 시제품과 픽셀 비교할 때 쓴다.
// - 기본 모드: 로그인·가입·내 정보·반려견·회차 시작·영상 올리기·관리자는 백엔드 develop API 를 부른다.
//   바이탈·진단 이력·메모·진료 기록(271)은 반려견 차트를 열 때 syncDogChart 가 서버에서 읽는다.
import { api, tokenStore, type DogHistoryOut, type DogOut, type NoteOut, type NoteRevisionOut, type StaffOut, type VitalOut } from '../api/client'
import { db, changed } from './db'
import type { Account, Dog, History, Note, Staff, Vital } from './types'
import { syncSessions } from './sessions_backend'

/** 백엔드에서 읽어 온 기관 id(시연 기관 demo 와 구분) */
const remote = new Set<string>()
export const isRemote = (instId: string): boolean => remote.has(instId)

export const MOCK = import.meta.env.MODE === 'mock'

const SEX_IN: Record<string, string> = { MALE: 'm', FEMALE: 'f', MALE_NEUTERED: 'mn', FEMALE_SPAYED: 'fs' }
export const SEX_OUT: Record<string, string> = { m: 'MALE', f: 'FEMALE', mn: 'MALE_NEUTERED', fs: 'FEMALE_SPAYED' }
const SIZE_IN: Record<string, string> = { SMALL: 'S', MEDIUM: 'M', LARGE: 'L' }
export const SIZE_OUT: Record<string, string> = { S: 'SMALL', M: 'MEDIUM', L: 'LARGE' }

export const STAGE_IN: Record<string, string> = { PRE: 'pre', REHAB: 'rehab', DONE: 'done' }
export const STAGE_OUT: Record<string, string> = { pre: 'PRE', rehab: 'REHAB', done: 'DONE' }
const KIND_IN: Record<string, string> = { DIAGNOSIS: '진단', SURGERY: '수술', REHAB: '재활' }
export const KIND_OUT: Record<string, string> = { 진단: 'DIAGNOSIS', 수술: 'SURGERY', 재활: 'REHAB' }
/** 메모 분류: 서버 영문 코드 ↔ 화면 이름. S·O·A·P 는 그대로 */
const CAT_IN: Record<string, string> = { CAUTION: '주의', GUARDIAN: '보호자', BOOKING: '예약', OTHER: '기타' }
export const CAT_OUT: Record<string, string> = { 주의: 'CAUTION', 보호자: 'GUARDIAN', 예약: 'BOOKING', 기타: 'OTHER', S: 'S', O: 'O', A: 'A', P: 'P' }

const s = (v: number | null | undefined): string => (v == null ? '' : String(v))
const last4 = (p: string): string => p.replace(/\D/g, '').slice(-4)
const pad2 = (n: number) => String(n).padStart(2, '0')
/** 서버 시각(UTC ISO) → 이 브라우저 시각 "YYYY-MM-DD HH:MM"(화면의 Note.at 모양) */
export function localAt(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 16).replace('T', ' ')
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}

export function toVital(v: VitalOut): Vital {
  return { day: v.measured_on, kg: s(v.weight_kg), temp: s(v.temp_c), hr: s(v.heart_rate), sbp: s(v.sbp), dbp: s(v.dbp), author: v.staff?.name ?? '' }
}
function toHistory(h: DogHistoryOut): History {
  return { id: h.id, day: h.occurred_on, kind: KIND_IN[h.kind] ?? h.kind, title: h.title, site: h.site ?? '', by: h.clinician ?? '', author: h.staff?.name ?? '' }
}
/** NoteOut → 화면 Note. revs = 고치기 전 내용들(오래된 것부터, [쓴 시각, 쓴 사람, 내용]) */
function toNote(n: NoteOut, revs: NoteRevisionOut[] = []): Note {
  const old = [...revs].reverse() // 서버는 최근 것부터
  const r: [string, string, string][] = old.map((x, i) => [localAt(i ? old[i - 1].revised_at : n.created_at), x.staff?.name ?? '', x.body])
  return {
    id: n.id, at: localAt(n.created_at), author: n.staff?.name ?? '', cat: CAT_IN[n.category] ?? n.category, text: n.body,
    important: n.important, revs: r, rid: n.session_id ?? '',
  }
}

/** DogOut → 화면용 Dog. 271 이전 서버라 칸이 없으면(동물번호·보호자·단계) 이미 이 브라우저에 있던 값을 그대로 둔다.
 *  바이탈·진단 이력·메모는 syncDogChart 가 채운다. 아직 안 읽었으면 목록의 최근 바이탈 한 줄만 둔다 */
export function toDog(o: DogOut, prev?: Dog): Dog {
  const base: Dog = {
    no: '', owner: '', phone: '', stage: 'rehab', stage_day: '', history: [], vitals: [], notes: [], images: [],
    ...prev,
  } as Dog
  const phone4 = o.owner_phone_last4 ?? undefined
  // 목록 응답은 전체 번호가 null. 이전에 상세로 읽은 번호가 뒤 4자리와 맞으면 그대로 둔다
  const phone = o.owner_phone != null ? o.owner_phone
    : o.owner_phone_last4 === undefined ? base.phone
      : base.phone && phone4 && last4(base.phone) === phone4 ? base.phone : ''
  const srv = o.badges !== undefined || o.changes !== undefined || o.last_symmetry !== undefined
    ? { badges: o.badges, changes: o.changes, last_symmetry: o.last_symmetry, dx_text: [o.last_surgery?.title, o.last_diagnosis?.title].filter(Boolean).join(' '), diag: o.last_diagnosis?.title }
    : base.srv
  return {
    ...base,
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
    no: o.chart_no !== undefined ? o.chart_no ?? '' : base.no,
    owner: o.owner_name !== undefined ? o.owner_name ?? '' : base.owner,
    phone,
    phone4: phone ? undefined : phone4 || undefined,
    stage: o.stage ? STAGE_IN[o.stage] ?? 'rehab' : base.stage,
    stage_day: o.stage !== undefined ? o.stage_changed_on ?? '' : base.stage_day,
    vitals: base.chart_loaded ? base.vitals : o.latest_vital ? [toVital(o.latest_vital)] : base.vitals,
    srv,
  }
}

/** 반려견 차트를 열 때: 상세(전체 연락처)·바이탈·진단 이력·메모를 서버에서 읽어 db 에 넣는다.
 *  예전 서버라 API 가 없으면(404 등) 그 칸은 그대로 둔다 */
export async function syncDogChart(acctId: string, dogId: string): Promise<void> {
  if (MOCK || !isRemote(acctId)) return
  const opt = <T,>(p: Promise<T>): Promise<T | null> => p.catch(() => null)
  const [o, vs, hs, ns] = await Promise.all([
    opt(api.dog(dogId)), opt(api.vitals(dogId)), opt(api.history(dogId)), opt(listAllNotes(dogId)),
  ])
  const acct = db.accounts[acctId] // 읽는 사이 syncFromBackend 가 기관 객체를 바꿨을 수 있어 다시 찾는다
  const i = acct ? acct.dogs.findIndex((d) => d.id === dogId) : -1
  if (i < 0) return
  let d = acct.dogs[i]
  if (o) d = toDog(o, d)
  if (vs) d = { ...d, vitals: vs.items.map(toVital) }
  if (hs) d = { ...d, history: hs.items.map(toHistory) }
  if (ns) {
    // 고친 적 있는 기록만 이력을 따로 읽는다
    const revs = await Promise.all(ns.map((n) => (n.revision_count ? api.noteRevisions(n.id).then((r) => r.items).catch(() => []) : Promise.resolve([]))))
    d = { ...d, notes: ns.map((n, k) => toNote(n, revs[k])) }
  }
  d.chart_loaded = !!(vs && hs && ns)
  acct.dogs[i] = d
  changed()
}

/** 홈 '오늘' 목록용: 오늘 기록이 있을 법한 반려견 차트(바이탈·메모·진료 기록)를 먼저, 나머지도 차례로 읽는다.
 *  오늘 진료 기록은 반려견마다 따로 읽어야 해서(기관 단위 '오늘 기록' API 없음) 홈을 열 때 한 번, 4마리씩 최대 60마리.
 *  오늘 회차가 있는 반려견은 GET /sessions 로, 오늘 바이탈이 있는 반려견은 목록의 latest_vital 로 먼저 고른다 */
const homeSynced = new Set<string>()
export async function syncTodayCharts(acctId: string, today: string): Promise<void> {
  if (MOCK || !isRemote(acctId) || homeSynced.has(acctId)) return
  homeSynced.add(acctId)
  const acct = db.accounts[acctId]
  if (!acct) return
  const first = new Set<string>()
  try {
    const r = await api.instSessions(1, 100)
    for (const s of r.items) if (s.measured_on === today) first.add(s.dog.id)
  } catch {
    /* 목록을 못 읽으면 순서만 달라진다 */
  }
  for (const d of acct.dogs) if (d.vitals.some((v) => v.day === today)) first.add(d.id)
  const ids = [...first, ...acct.dogs.map((d) => d.id).filter((id) => !first.has(id))]
  const todo = ids.filter((id) => !acct.dogs.find((d) => d.id === id)?.chart_loaded).slice(0, 60)
  for (let i = 0; i < todo.length; i += 4) {
    await Promise.all(todo.slice(i, i + 4).map((id) => syncDogChart(acctId, id).catch(() => undefined)))
  }
}

async function listAllNotes(dogId: string): Promise<NoteOut[]> {
  const out: NoteOut[] = []
  for (let page = 1; page < 50; page++) {
    const r = await api.notes(dogId, page, 200)
    out.push(...r.items)
    if (out.length >= r.total || !r.items.length) break
  }
  return out
}

function toStaff(s: StaffOut): Staff {
  return {
    id: s.id, login_id: s.login_id, password: '', name: s.name, inst: s.institution.id, email: s.email || '',
    role: s.role, active: true, device_code: '', joined: '', reset_token: '', reset_until: 0,
  }
}

/** 로그인한 담당자와 그 기관·반려견을 백엔드에서 읽어 db 에 넣는다. 돌려주는 값 = 담당자 id */
/** 서버 PDF 인쇄 화면(285): 그 회차의 반려견 하나만 읽는다(기관 크기와 상관없이 몇 초 안에 그리게). null = 전부 */
let onlyDog: string | null = null
export function limitToDog(dogId: string | null): void {
  onlyDog = dogId
}

export async function syncFromBackend(me?: StaffOut): Promise<string> {
  const s = me ?? (await api.me())
  const inst = s.institution
  const prev = db.accounts[inst.id]
  const base: Account = prev ?? {
    id: inst.id, login_id: '', password: '', name: inst.name, loc: '-', dev: '-', joined: '', notif_on: true,
    results: [], jobs: [], dogs: [], code: '', contract_ends: null,
  }
  // 분석 완료 알림은 담당자 설정(서버 notif_on). 예전 서버라 필드가 없으면 기존 값
  const acct: Account = { ...base, name: inst.name, code: inst.code, contract_ends: inst.contract_ends_at, notif_on: s.notif_on ?? base.notif_on }
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
    acct.dogs = dogs.filter((o) => !onlyDog || o.id === onlyDog).map((o) => toDog(o, acct.dogs.find((d) => d.id === o.id)))
    await syncSessions(acct, true).catch(() => undefined)   // 측정 이력의 끝난 회차, 이 브라우저에서 연 회차·측정 중 회차의 상태·결과
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
        revoked: !!c.revoked_at, note: c.note || '', created: c.created_at.slice(0, 10) }
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
