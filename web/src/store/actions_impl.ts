// 폼 처리 함수 등록. prototype/proto_app/main.py 의 @app.post 함수들을 같은 주소·같은 알림 문구로 옮긴다.
// 쿠키 pp_acct → setLogin, 업로드 파일 저장 → URL.createObjectURL(file).
import * as config from '../config'
import {
  ContractExpired,
  current,
  currentStaff,
  finished_notices,
  need_login,
  redirect,
  setLogin,
  type Go,
} from '../app/session'
import { start_job } from '../views/analysis'
import { f, on, petInputError } from './actions'
import {
  activeJobs,
  byCode,
  byLogin,
  CODE_CHARS,
  contractStatus,
  db,
  dogOf,
  effectiveRole,
  getAccount,
  isoToday,
  jobOf,
  jobProgress,
  jobStep,
  new_id,
  norm_code,
  resultOf,
  show_code,
} from './db'
import { DEMO_STAFF, resetDemo } from './demo'
import type { Account, DeviceCode, Dog, History, Note, Staff, Vital } from './types'

type Params = Record<string, string>

// ── 공통 ──
const VIDEO_EXT = ['.mp4', '.mov', '.m4v'] // config.VIDEO_EXT

/** Form("기본값"): FastAPI 는 빈 문자열도 기본값으로 바꾼다 */
const F = (fd: FormData, k: string, dflt = ''): string => f(fd, k) || dflt

/** Form(3) 같은 정수 칸. 숫자가 아니면 기본값(시제품은 422) */
function I(fd: FormData, k: string, dflt: number): number {
  const v = F(fd, k)
  return /^\s*[+-]?\d+\s*$/.test(v) ? parseInt(v, 10) : dflt
}

/** 파이썬 len(str): 코드 포인트 수 */
const plen = (s: string): number => [...s].length

/** 파이썬 round: 짝수 반올림 */
function pyround(x: number): number {
  const r = Math.round(x)
  return Math.abs(x % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r
}

const pad = (n: number): string => String(n).padStart(2, '0')

function _now(): string {
  const d = new Date()
  return `${isoToday()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 계약 만료(ContractExpired) → /expired (main.py 의 exception_handler) */
function post(pattern: string, h: (p: Params, fd: FormData) => Go | Promise<Go>): void {
  on(pattern, async (p, fd) => {
    try {
      return await h(p, fd)
    } catch (e) {
      if (e instanceof ContractExpired) return redirect('/expired')
      throw e
    }
  })
}

const login_as = (url: string, s: Staff, toast = ''): Go => {
  setLogin(s.id)
  return redirect(url, toast)
}

function randChoice(chars: string, n: number): string {
  const b = crypto.getRandomValues(new Uint32Array(n))
  return Array.from(b, (x) => chars[x % chars.length]).join('')
}

/** secrets.token_hex(n) */
const token_hex = (n: number): string => Array.from(crypto.getRandomValues(new Uint8Array(n)), (x) => x.toString(16).padStart(2, '0')).join('')

/** secrets.token_urlsafe(n) */
function token_urlsafe(n: number): string {
  const b = crypto.getRandomValues(new Uint8Array(n))
  return btoa(String.fromCharCode(...b)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** hashlib.sha256(token).hexdigest(). 안전한 주소가 아니라 subtle 이 없으면 원문 그대로 */
async function sha256(s: string): Promise<string> {
  if (!crypto.subtle) return s
  const h = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s))
  return Array.from(new Uint8Array(h), (x) => x.toString(16).padStart(2, '0')).join('')
}

const urlencode = (q: Record<string, string>): string => new URLSearchParams(q).toString()

// ── 로그인 전 ──
post('/login', (_p, fd) => {
  // 아이디 + 비밀번호(기관 코드 없음). 틀리면 무엇이 틀렸는지 알려 주지 않는다
  const login_id = f(fd, 'login_id'), password = f(fd, 'password')
  const s = byLogin(login_id)
  if (!s || s.password !== password) return redirect('/login', '아이디 또는 비밀번호가 맞지 않습니다.')
  if (!s.active) return redirect('/login', '사용이 중지된 계정입니다. 기관 담당자에게 문의해 주세요.')
  if (s.role === 'ADMIN' || s.role === 'STAFF') return login_as('/admin', s)
  if (effectiveRole(s) === 'GUEST') return login_as('/expired', s) // 로그인은 되고 만료 안내만 보인다
  return login_as('/home', s)
})

post('/login/demo', () => {
  // 둘러보기: 데모 기관 담당자로 들어간다(예시 데이터를 처음 상태로)
  resetDemo()
  return login_as('/home', db.staff[DEMO_STAFF])
})

/** (DeviceCode, 기관, 오류 문구, 상태). 없음·회수·형식 오류·계약 만료는 같은 문구로 답한다 */
function _verify(code: string): [DeviceCode | null, Account | null, string, number] {
  const c = byCode(norm_code(code))
  const acct = c ? getAccount(c.inst) : undefined
  if (!c || c.revoked || !acct || contractStatus(acct) === 'EXPIRED') return [null, null, '유효한 디바이스 코드가 아닙니다.', 404]
  // 192: 코드 하나로 만들 수 있는 계정 수에 상한이 없다
  return [c, acct, '', 200]
}

/** POST /api/device-codes/verify. 오류면 {error} (시제품은 404·409 상태 코드도 같이) */
export function api_device_code_verify(code: string):
  | { error: string }
  | { institution: { id: string; name: string } } {
  const [c, acct, err] = _verify(code)
  if (err || !c || !acct) return { error: err }
  return { institution: { id: acct.id, name: acct.name } }
}

const LOGIN_RE = /^[a-z0-9._-]{4,50}$/
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

const check_pw = (pw: string): boolean => plen(pw) >= 8 && new TextEncoder().encode(pw).length <= 72

const nameEmailOk = (name: string, email: string): boolean =>
  1 <= plen(name) && plen(name) <= 50 && 5 <= plen(email) && plen(email) <= 254 && EMAIL_RE.test(email)

post('/signup', (_p, fd) => {
  const code = f(fd, 'code'), login_id = f(fd, 'login_id'), pw = f(fd, 'pw'), pw2 = f(fd, 'pw2')
  if (!(f(fd, 't0') && f(fd, 't1') && f(fd, 't2'))) return redirect('/signup', '필수 약관에 동의해 주세요')
  const [c, acct, err] = _verify(code) // 화면에서 확인했어도 다시 검사한다
  if (err || !c || !acct) return redirect('/signup', err)
  const email = f(fd, 'email').trim().toLowerCase(), name = f(fd, 'name').trim()
  if (!LOGIN_RE.test(login_id)) return redirect('/signup', '아이디는 영문 소문자·숫자·.·_·- 로 4~50자입니다')
  if (!check_pw(pw)) return redirect('/signup', '비밀번호는 8자 이상입니다')
  if (pw !== pw2) return redirect('/signup', '비밀번호가 서로 다릅니다')
  if (!nameEmailOk(name, email)) return redirect('/signup', '이름과 이메일을 확인해 주세요')
  if (byLogin(login_id)) return redirect('/signup', '이미 사용 중인 아이디입니다.')
  const t = new Date()
  const s: Staff = {
    id: new_id('s'), login_id, password: pw, name, inst: acct.id, email, role: 'CLIENT', active: true,
    device_code: c.id, joined: `${t.getFullYear()}년 ${t.getMonth() + 1}월 ${t.getDate()}일`, reset_token: '', reset_until: 0,
  }
  db.staff[s.id] = s
  return login_as('/home', s, `${acct.name} 담당자로 가입했습니다`)
})

// ── 비밀번호 찾기·재설정 (메일 서버가 없어 링크를 화면에 보여 준다) ──
post('/forgot', async (_p, fd) => {
  const s = byLogin(f(fd, 'login_id'))
  const q: Record<string, string> = { sent: '1' }
  if (s && s.active && s.email) {
    const token = token_urlsafe(32)
    s.reset_token = await sha256(token) // 해시만 저장, 새로 요청하면 이전 토큰은 무효
    s.reset_until = Date.now() / 1000 + 30 * 60
    q.link = `/reset-password?token=${token}`
  }
  return redirect('/forgot?' + urlencode(q)) // 계정이 있든 없든 같은 안내(아이디 탐색 방지)
})

post('/reset-password', async (_p, fd) => {
  const token = f(fd, 'token'), pw = f(fd, 'pw'), pw2 = f(fd, 'pw2')
  const h = await sha256(token)
  const s = Object.values(db.staff).find((x) => x.reset_token && x.reset_token === h && x.active)
  if (!s || s.reset_until < Date.now() / 1000)
    return redirect('/forgot', '재설정 링크가 유효하지 않거나 만료되었습니다. 다시 요청해 주세요.')
  if (!check_pw(pw) || pw !== pw2) return redirect('/reset-password?' + urlencode({ token }), '8자 이상, 두 칸이 같게 입력해 주세요')
  s.password = pw
  s.reset_token = ''
  s.reset_until = 0
  return redirect('/login', '비밀번호를 바꿨습니다. 새 비밀번호로 로그인해 주세요')
})

// ── 내 정보: 이름·이메일 수정, 비밀번호 변경 ──
post('/account/profile', (_p, fd) => {
  if (!current()) return need_login()
  const s = currentStaff()!
  const email = f(fd, 'email').trim().toLowerCase(), name = f(fd, 'name').trim()
  if (!nameEmailOk(name, email)) return redirect('/account', '이름과 이메일을 확인해 주세요')
  s.name = name
  s.email = email
  return redirect('/account', '저장했습니다')
})

post('/account/withdraw', (_p, fd) => {
  if (!current()) return need_login()
  const s = currentStaff()!
  if (s.password !== f(fd, 'password')) return redirect('/account', '현재 비밀번호가 맞지 않습니다.')
  if (!Object.values(db.staff).some((x) => x.inst === s.inst && x.active && x.id !== s.id)) return redirect('/account', '기관의 마지막 계정이라 탈퇴할 수 없습니다. 관리자에게 문의해 주세요.')
  s.active = false
  setLogin(null)
  return redirect('/login', '탈퇴했습니다. 그동안 이용해 주셔서 감사합니다')
})

post('/account/password', (_p, fd) => {
  if (!current()) return need_login()
  const s = currentStaff()!
  const current_pw = f(fd, 'current_pw'), pw = f(fd, 'pw'), pw2 = f(fd, 'pw2')
  if (s.password !== current_pw) return redirect('/account', '현재 비밀번호가 맞지 않습니다.')
  if (!check_pw(pw) || pw !== pw2 || pw === current_pw) return redirect('/account', '새 비밀번호는 8자 이상, 현재와 다르게 입력해 주세요')
  s.password = pw
  return redirect('/account', '비밀번호를 바꿨습니다')
})

// ── 크림오프 관리 (ADMIN 은 전부, STAFF 는 보기만) ──
function admin_write(): Staff | undefined {
  const s = currentStaff()
  return s && s.role === 'ADMIN' ? s : undefined
}

post('/admin/institutions', (_p, fd) => {
  const name = f(fd, 'name'), ends = f(fd, 'ends')
  if (!admin_write()) return redirect('/admin', '조회 전용 계정입니다')
  if (!(1 <= plen(name.trim()) && plen(name.trim()) <= 100)) return redirect('/admin', '기관명을 입력해 주세요')
  const a: Account = {
    id: new_id('i'), login_id: '', password: '', name: name.trim(), loc: '-', dev: '-', joined: '2026년 10월 2일',
    dogs: [], results: [], jobs: [], notif_on: true, code: 'INST-' + token_hex(3).toUpperCase(), contract_ends: ends || null,
  }
  db.accounts[a.id] = a
  return redirect('/admin', `${name.trim()} 기관을 만들었습니다`)
})

post('/admin/institutions/:inst', (p, fd) => {
  const ends = f(fd, 'ends')
  const a = getAccount(p.inst)
  if (!admin_write() || !a) return redirect('/admin', '조회 전용 계정입니다')
  a.contract_ends = ends || null
  return redirect('/admin', `${a.name} 계약 종료일을 ${!ends ? '없음' : ends}(으)로 바꿨습니다`)
})

post('/admin/institutions/:inst/codes', (p, fd) => {
  const note = f(fd, 'note')
  const a = getAccount(p.inst)
  if (!admin_write() || !a) return redirect('/admin', '조회 전용 계정입니다')
  // 기관마다 쓸 수 있는 코드는 하나(192). 회수한 뒤 발급한다
  if (Object.values(db.codes).some((x) => x.inst === p.inst && !x.revoked)) return redirect('/admin', '이 기관에는 쓸 수 있는 디바이스 코드가 이미 있습니다. 회수한 뒤 새로 발급해 주세요.')
  const code = randChoice(CODE_CHARS, 20)
  const c: DeviceCode = {
    id: new_id('c'), inst: p.inst, code, revoked: false,
    note: [...note].slice(0, 100).join(''), created: isoToday(),
  }
  db.codes[c.id] = c
  return redirect('/admin', `코드를 발급했어요: ${show_code(code)}`)
})

post('/admin/codes/:cid', (p, fd) => {
  const revoke = f(fd, 'revoke')
  const c = db.codes[p.cid]
  if (!admin_write() || !c) return redirect('/admin', '조회 전용 계정입니다')
  if (revoke) {
    c.revoked = true
    return redirect('/admin', '코드를 회수했습니다. 기존 계정은 그대로 쓸 수 있습니다')
  }
  c.note = [...f(fd, 'note')].slice(0, 100).join('')
  return redirect('/admin', '메모를 바꿨습니다')
})

post('/admin/staff/:sid', (p) => {
  const me = admin_write()
  const t = db.staff[p.sid]
  if (!me || !t) return redirect('/admin', '조회 전용 계정입니다')
  if (t.id === me.id) return redirect('/admin', '자기 계정은 중지할 수 없습니다.')
  t.active = !t.active
  return redirect('/admin', `${t.name} 계정을 ${t.active ? '다시 열었습니다' : '중지했습니다'}`)
})

post('/logout', () => {
  setLogin(null)
  return redirect('/')
})

// ── 반려견 차트: 메모·바이탈·진단 이력 ──
post('/dogs/:dog_id/notes', (p, fd) => {
  // 메모 쓰기·고치기. 공용 계정이라 작성자는 사람이 적는다. 고치면 이전 내용을 revs 에 남기고 지우지 않는다
  const acct = current()
  if (!acct) return need_login()
  const dog_id = p.dog_id
  const note_id = f(fd, 'note_id'), next_url = f(fd, 'next_url'), rid = f(fd, 'rid'), important = f(fd, 'important')
  const visit = f(fd, 'visit')
  const d = dogOf(acct, dog_id)
  const back = next_url.startsWith('/results/') || next_url.startsWith('/dogs/') ? next_url : `/dogs/${dog_id}` // 쓴 화면으로 돌아간다
  if (!d) return redirect('/home')
  const author = f(fd, 'author').trim(), text = f(fd, 'text').trim() // 작성자는 로그인한 사람 이름이 기본, 고칠 수 있다
  const soap = (['S', 'O', 'A', 'P'] as const)
    .map((k) => [k, f(fd, k.toLowerCase()).trim()] as [string, string])
    .filter(([, v]) => v)
  if (visit && !note_id) {
    // 오늘 방문 기록: 바이탈은 방문마다 반드시 잰다(11-02). 오늘 이미 잰 값이 있으면 바꾼다
    const vals = ['kg', 'temp', 'hr', 'sbp', 'dbp'].map((k) => f(fd, k).trim())
    if (!vals.every(Boolean)) return redirect(back, '바이탈(체중·체온·심박·혈압)을 모두 적어 주세요')
    const today = isoToday()
    d.vitals = d.vitals.filter((x) => x.day !== today)
    const [kg, temp, hr, sbp, dbp] = vals
    d.vitals.unshift({ day: today, kg, temp, hr, sbp, dbp, author })
    d.kg = vals[0]
    if (!soap.length) return redirect(back, '바이탈을 기록했습니다')
  }
  if (soap.length && !note_id) {
    // SOAP 칸으로 쓴 진료 기록: 채운 칸마다 한 줄, 같은 시각으로 묶인다
    const r = resultOf(acct, rid)
    const at = _now()
    soap.forEach(([k, v], i) => {
      d.notes.unshift(mkNote(at, author, k, v, !!important && i === 0, r && r.dog === d.id ? r.id : ''))
    })
    return redirect(back, '기록을 남겼습니다')
  }
  if (!text) return redirect(back, '내용을 적어 주세요')
  let cat = F(fd, 'cat', 'O')
  cat = config.NOTE_CAT.includes(cat) ? cat : '기타'
  const n = d.notes.find((x) => x.id === note_id)
  if (n) {
    if (n.text !== text) {
      n.revs.push([n.at, n.author, n.text])
      n.at = _now()
      n.author = author
      n.text = text
    }
    return redirect(back, '고쳤습니다. 이전 내용은 이력에 남습니다')
  }
  const r = resultOf(acct, rid)
  d.notes.unshift(mkNote(_now(), author, cat, text, !!important, r && r.dog === d.id ? r.id : ''))
  return redirect(back, cat in config.MEMO_CAT ? '메모를 남겼습니다' : '기록을 남겼습니다')
})

const mkNote = (at: string, author: string, cat: string, text: string, important: boolean, rid: string): Note => ({
  id: new_id('note'), at, author, cat, text, important, revs: [], rid,
})

function _vital_from_form(day: string, kg: string, temp: string, hr: string, sbp: string, dbp: string, author: string): Vital | null {
  const vals = [kg, temp, hr, sbp, dbp].map((x) => x.trim())
  if (!vals.some(Boolean)) return null
  return { day: day || isoToday(), kg: vals[0], temp: vals[1], hr: vals[2], sbp: vals[3], dbp: vals[4], author: author.trim() }
}

post('/dogs/:dog_id/vitals', (p, fd) => {
  const acct = current()
  if (!acct) return need_login()
  const day = f(fd, 'day'), author = f(fd, 'author'), next_url = f(fd, 'next_url')
  const d = dogOf(acct, p.dog_id)
  const back = next_url.startsWith('/dogs/') ? next_url : `/dogs/${p.dog_id}?v=${day || isoToday()}`
  if (!d) return redirect('/home')
  if (!author.trim()) return redirect(back, '작성자를 적어 주세요')
  const v = _vital_from_form(day, f(fd, 'kg'), f(fd, 'temp'), f(fd, 'hr'), f(fd, 'sbp'), f(fd, 'dbp'), author)
  if (!v) return redirect(back, '값을 하나 이상 적어 주세요')
  const same = d.vitals.find((x) => x.day === v.day)
  if (same) {
    // 그날 줄이 이미 있으면 적은 값만 바꾼다(서버 PUT /vitals/{날짜} 와 같게)
    for (const k of ['kg', 'temp', 'hr', 'sbp', 'dbp'] as const) if (v[k]) same[k] = v[k]
    same.author = v.author
  } else d.vitals.unshift(v)
  d.vitals.sort((a, b) => (a.day < b.day ? 1 : a.day > b.day ? -1 : 0))
  if (v.kg && d.vitals[0].day === v.day) d.kg = v.kg
  return redirect(back, '바이탈을 기록했습니다')
})

post('/dogs/:dog_id/history', (p, fd) => {
  // 진단·수술·재활 단계 기록. 단계(stage)를 고르면 반려견 단계도 바뀐다
  const acct = current()
  if (!acct) return need_login()
  const title = f(fd, 'title'), site = f(fd, 'site'), by = f(fd, 'by'), stage = f(fd, 'stage'), author = f(fd, 'author')
  const d = dogOf(acct, p.dog_id)
  const back = `/dogs/${p.dog_id}?tab=dx`
  if (!d) return redirect('/home')
  if (!(author.trim() && title.trim())) return redirect(back, '작성자와 내용을 적어 주세요')
  const day = f(fd, 'day') || isoToday()
  let kind = F(fd, 'kind', '진단')
  kind = ['진단', '수술', '재활'].includes(kind) ? kind : '진단'
  const h: History = { day, kind, title: title.trim(), site: site in config.SITE ? site : '', by: by.trim(), author: author.trim() }
  d.history.push(h)
  d.history.sort((a, b) => (a.day < b.day ? -1 : a.day > b.day ? 1 : 0))
  if (stage in config.STAGE && stage !== d.stage) {
    d.stage = stage
    d.stage_day = day
  }
  if (kind === '재활' && !d.rehab) d.rehab = day
  return redirect(back, '진단 이력에 남겼습니다')
})

post('/dogs/:dog_id/history/:hid', (p, fd) => {
  const acct = current()
  if (!acct) return need_login()
  const d = dogOf(acct, p.dog_id)
  const back = `/dogs/${p.dog_id}?tab=dx`
  if (!d) return redirect('/home')
  const i = d.history.findIndex((h, k) => (h.id || `i${k}`) === p.hid)
  if (i < 0) return redirect(back, '기록을 찾을 수 없습니다')
  if (f(fd, 'delete')) {
    d.history.splice(i, 1)
    return redirect(back, '진단 이력에서 지웠습니다')
  }
  const title = f(fd, 'title').trim()
  if (!title) return redirect(`${back}&hedit=${encodeURIComponent(p.hid)}`, '내용을 적어 주세요')
  const kind = f(fd, 'kind'), site = f(fd, 'site')
  Object.assign(d.history[i], {
    day: f(fd, 'day') || d.history[i].day, kind: ['진단', '수술', '재활'].includes(kind) ? kind : d.history[i].kind,
    title, site: site in config.SITE ? site : '', by: f(fd, 'by').trim(),
  })
  d.history.sort((a, b) => (a.day < b.day ? -1 : a.day > b.day ? 1 : 0))
  return redirect(back, '진단 이력을 고쳤습니다')
})

// ── 반려견 등록·수정·삭제·기준 회차 ──
function _pet_from_form(fd: FormData) {
  const sex = F(fd, 'sex', 'm'), size = f(fd, 'size'), focus = f(fd, 'focus')
  return {
    name: f(fd, 'name').trim(), breed: f(fd, 'breed').trim(), kg: f(fd, 'kg').trim(), birth: f(fd, 'birth').trim(),
    sex: sex in config.SEX ? sex : 'm', size: size in config.SIZE ? size : '',
    rehab: f(fd, 'rehab'), focus: focus in config.LIMB ? focus : null, memo: f(fd, 'memo').trim(),
  }
}

/** 동물번호·보호자·단계: 폼에 칸이 있을 때만 바꾼다. 단계가 바뀌면 바뀐 날을 오늘로 */
function _chart_from_form(fd: FormData, d?: Dog): Partial<Dog> {
  const out: Partial<Dog> = {}
  if (fd.has('no')) out.no = f(fd, 'no').trim()
  if (fd.has('owner')) out.owner = f(fd, 'owner').trim()
  if (fd.has('phone')) out.phone = f(fd, 'phone').trim()
  const stage = f(fd, 'stage')
  if (stage in config.STAGE && (!d || stage !== d.stage)) {
    out.stage = stage
    out.stage_day = isoToday()
  }
  return out
}

post('/dogs', (_p, fd) => {
  const acct = current()
  if (!acct) return need_login()
  const dog_id = f(fd, 'dog_id'), next_url = F(fd, 'next_url', '/home'), version = f(fd, 'version')
  const p0 = _pet_from_form(fd)
  if (!(p0.name && p0.breed && p0.kg)) return redirect(next_url, '이름·견종·체중을 입력해 주세요')
  const bad = petInputError(p0.kg, p0.birth)
  if (bad) return redirect(next_url, bad)
  const manual = !!p0.size
  const data = { ...p0, size: p0.size || config.auto_size(p0.breed, p0.kg), size_manual: manual }
  let d = dogOf(acct, dog_id)
  if (d) {
    if (version && /^\d+$/.test(version) && parseInt(version, 10) !== d.version)
      // 다른 담당자가 먼저 고쳤다
      return redirect(next_url, '다른 담당자가 먼저 수정했습니다. 화면을 새로 불러온 뒤 다시 시도해 주세요.')
    Object.assign(d, data, _chart_from_form(fd, d))
    d.version += 1
    return redirect(next_url, '저장했습니다')
  }
  const nd: Dog = {
    id: new_id('p'), ...data, base: null, no: '', owner: '', phone: '', stage: 'rehab', stage_day: '',
    history: [], vitals: [], notes: [], images: [], version: 0,
  }
  Object.assign(nd, _chart_from_form(fd))
  nd.stage_day = '' // 등록할 때 고른 단계는 바뀐 것이 아니다(서버도 stage_changed_on = null)
  d = nd
  acct.dogs.push(d)
  const sep = next_url.includes('?') ? '&' : '?'
  if (next_url.startsWith('/upload') || next_url.startsWith('/my')) return redirect(`${next_url}${sep}dog=${d.id}`, `${d.name} 등록을 마쳤습니다`)
  return redirect(`/dogs/${d.id}`, `${d.name} 등록을 마쳤습니다`)
})

post('/dogs/:dog_id/delete', (p) => {
  const acct = current()
  if (!acct) return need_login()
  const d = dogOf(acct, p.dog_id)
  if (!d) return redirect('/my')
  acct.dogs = acct.dogs.filter((x) => x.id !== p.dog_id)
  acct.results = acct.results.filter((r) => r.dog !== p.dog_id)
  acct.jobs = acct.jobs.filter((j) => j.dog !== p.dog_id)
  return redirect('/my', `${d.name} 정보를 삭제했습니다`)
})

post('/dogs/:dog_id/base', (p, fd) => {
  const acct = current()
  if (!acct) return need_login()
  const d = dogOf(acct, p.dog_id), r = resultOf(acct, f(fd, 'rid'))
  if (d && r && r.st !== 'fail') {
    d.base = r.id
    return redirect(`/dogs/${p.dog_id}`, `${r.date} 회차를 기준으로 정했습니다`)
  }
  return redirect(`/dogs/${p.dog_id}`)
})

// ── 영상 업로드 · 분석 ──
/** Path(name).suffix.lower() */
function suffix(name: string): string {
  const base = name.split(/[\\/]/).pop() || ''
  const i = base.lastIndexOf('.')
  return i > 0 && i < base.length - 1 ? base.slice(i).toLowerCase() : ''
}

post('/analyze', (_p, fd) => {
  const acct = current()
  if (!acct) return need_login()
  const dog = f(fd, 'dog'), weight = f(fd, 'weight'), author = f(fd, 'author')
  if (!dogOf(acct, dog)) return redirect('/upload', '반려견을 골라 주세요')
  const saved: string[] = []
  const files = fd.getAll('files').filter((x): x is File => x instanceof File)
  for (const file of files.slice(0, config.MAX_SHOTS)) {
    if (!file.name) continue
    const ext = suffix(file.name)
    if (!VIDEO_EXT.includes(ext) && !(file.type || '').startsWith('video/'))
      return redirect(`/upload?dog=${dog}`, '영상 파일(MP4 · MOV)만 올릴 수 있습니다')
    saved.push(URL.createObjectURL(file)) // 시제품은 uploads/ 에 저장한 주소
  }
  const n = saved.length || Math.max(0, Math.min(I(fd, 'demo_count', 0), config.MAX_SHOTS))
  if (!n) return redirect(`/upload?dog=${dog}`, '보행 영상을 1개 이상 올려 주세요')
  const job = start_job(acct, dog, n, weight.trim(), saved)
  job.by = author.trim()
  const v = _vital_from_form('', weight, f(fd, 'temp'), f(fd, 'hr'), f(fd, 'sbp'), f(fd, 'dbp'), author) // 측정하면서 잰 바이탈은 차트에 바로 남긴다
  if (v) {
    const d = dogOf(acct, dog)!
    d.vitals.unshift(v)
    d.kg = v.kg || d.kg
  }
  return redirect(`/analyzing/${job.id}`)
})

/** GET /api/jobs/{job_id}. 없으면 {error: 'not found'}(시제품은 404) */
export function api_job(job_id: string):
  | { error: string }
  | { pct: number; step: string; done: boolean; url: string | null } {
  const acct = current()
  const job = acct ? jobOf(acct, job_id) : undefined
  if (!job) return { error: 'not found' }
  const p = jobProgress(job)
  if (job.result_id) job.notified = true
  return {
    pct: pyround((p / 5) * 100), step: jobStep(job, config.STEPS), done: !!job.result_id,
    url: job.result_id ? `/results/${job.result_id}` : null,
  }
}

/** GET /api/notices. 다른 화면에 있을 때 분석이 끝나면 알림을 띄우려고 부른다 */
export function api_notices(): { active: number; notices: string[] } {
  const acct = current()
  if (!acct) return { active: 0, notices: [] }
  return { active: activeJobs(acct).length, notices: finished_notices(acct) }
}

// ── 마이페이지 ──
post('/my/notif', () => {
  const acct = current()
  if (!acct) return need_login()
  acct.notif_on = !acct.notif_on
  return redirect('/my')
})
