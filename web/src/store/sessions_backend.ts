// 백엔드 회차 → 화면의 분석 작업(Job)·결과(Result).
// 반려견별 측정 이력(15.8)으로 끝난 회차를 모두 읽고, 이력 API 가 없는 서버를 위해 이 브라우저에서 연 회차도 기억해 두고(localStorage)
// 반려견의 측정 중 회차(open_session_id)와 함께 서버 상태를 읽는다. 끝난 회차는 /sessions/{id}/result 로 결과를 만든다.
import { api, ApiError, type SessionResultOut } from '../api/client'
import { applyMetrics } from '../views/real'
import { changed, kdate } from './db'
import type { Account, Metrics, Result } from './types'

const KEY = 'pp.web.sessions'
const POLL_MS = 4000
const FINAL = new Set(['DONE', 'FAILED'])
export const SERVER_FAIL_MSG = '분석에 실패했습니다. 잠시 후 다시 시도해 주세요.'

/** 이 브라우저에서 연 회차 */
export interface Known {
  id: string
  inst: string
  dog: string
  started: number
  n: number
  w: string
  by: string
  /** 측정 이력에서의 순번(0 = 가장 최근). 이 브라우저에서 연 회차는 없음 */
  ord?: number
}

function load(): Known[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]') as Known[]
  } catch {
    return []
  }
}

function save(list: Known[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(list.slice(-200)))
  } catch {
    /* 저장 못 하면 이번 화면에서만 따라간다 */
  }
}

/** 회차를 열고 영상을 올린 뒤 부른다: 기억해 두고 분석 작업으로 띄운다 */
export function remember(acct: Account, k: Known): void {
  save([...load().filter((x) => x.id !== k.id), k])
  if (!acct.jobs.some((j) => j.id === k.id)) {
    acct.jobs.push({ id: k.id, dog: k.dog, n: k.n, w: k.w, started: k.started, videos: [], result_id: null, notified: false, by: k.by, remote: true })
  }
  changed()
}

// 결과 표를 고르는 순서. OTHER 는 '기타 보행'이 아니라 보행 유형 판별 전의 통과 묶음이다
const GAIT_ORDER: [string, string][] = [['TROT', '속보'], ['WALK', '평보'], ['OTHER', '보행 유형 미판별']]

function hhmm(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/** /sessions/{id}/result → 화면 결과. 유효 통과 0건(gaits 빈 배열·used 0)은 실패로 두고 제외 사유를 싣는다 */
export function toResult(o: SessionResultOut, dog: string): Result {
  const pick = GAIT_ORDER.map(([t, name]) => [o.gaits.find((g) => g.gait_type === t), name] as const).find(([g]) => g && g.metrics.length)
  const noValid = o.pass_counts.used === 0 || !pick
  const st = o.status === 'FAILED' || noValid ? 'fail' : o.shot_counts.invalid > 0 || o.notices.some((n) => n.code === 'FEW_VALID_PASSES') ? 'part' : 'ok'
  const r: Result = {
    id: o.id, dog, date: kdate(o.measured_on), time: hhmm(o.completed_at), st, w: o.weight_kg != null ? String(o.weight_kg) : '-',
    model: o.model_version ?? '-', sym: 0, rom: 0, sL: 0, sR: 0, j: [], ps: [o.pass_counts.measured, o.pass_counts.used],
    ex: o.exclude_summary.map((e) => [e.message, e.count] as [string, number]), rep: false, videos: [], day: o.measured_on,
    by: o.staff?.name ?? '', m: {}, src: `backend:${o.id}`,
    // 서버 쪽 실패(집계 오류 등)는 반려견 탓이 아니므로 촬영 안내 대신 실패 문구. 촬영 안내는 DONE·used 0 일 때만(화면 기본 문구)
    fail_msg: o.status === 'FAILED' ? o.fail_reason?.message || SERVER_FAIL_MSG : undefined,
  }
  if (st !== 'fail' && pick) {
    const mg: Record<string, Metrics> = {}
    for (const [t, name] of GAIT_ORDER) {
      const g = o.gaits.find((x) => x.gait_type === t)
      if (!g) continue
      const m: Metrics = {}
      for (const x of g.metrics) {
        if (x.limb === 'NONE' || x.value == null || !x.measurable) continue
        ;(m[x.limb] ??= {})[x.metric_code] = x.value
      }
      if (Object.keys(m).length) mg[name] = m
    }
    applyMetrics(r, mg[pick[1]] ?? {})
    // 대칭 점수는 서버 값을 그대로 쓴다(앱과 같은 숫자). 예전 서버라 필드가 없으면 위에서 화면 계산한 값
    if (o.symmetry_score !== undefined) r.sym = o.symmetry_score ?? 0
    r.gait = pick[1]
    r.mg = mg
  }
  return r
}

/** 최근 회차가 앞에 오게(측정일 → 서버 이력 순서 → 끝난 시각). 같은 날 회차를 끝난 시각으로 세면 회차 번호가 앱(이력 순서)과 달라진다.
 *  이 브라우저에서 연 회차(ord 없음)는 이력보다 새 것으로 둔다 */
function byNewest(a: Result, b: Result): number {
  if (a.day !== b.day) return (b.day || '').localeCompare(a.day || '')
  if (a.ord != null || b.ord != null) return (a.ord ?? -1) - (b.ord ?? -1)
  return (b.time || '').localeCompare(a.time || '')
}

/** 반려견별 측정 이력(15.8, 백엔드 !91)으로 끝난 회차를 모두 알아 둔다. 이 브라우저에서 연 회차만 알던 것을 보완한다.
 *  이력 API 가 아직 없는 서버(404)면 조용히 건너뛴다 */
async function historyOf(acct: Account): Promise<Known[]> {
  const out: Known[] = []
  for (const d of acct.dogs) {
    try {
      for (let page = 1; page < 20; page++) {
        const r = await api.dogSessions(d.id, page, 100)
        for (const s of r.items) {
          if (FINAL.has(s.status)) out.push({ id: s.id, inst: acct.id, dog: d.id, started: 0, n: 0, w: s.weight_kg != null ? String(s.weight_kg) : d.kg, by: '', ord: out.length })
        }
        if (page * r.size >= r.total || !r.items.length) break
      }
    } catch (e) {
      if (e instanceof ApiError && e.code === 'NOT_FOUND') return out // 이력 API 가 없는 서버(없는 주소는 404 NOT_FOUND, 11.5)
    }
  }
  return out
}

/** 기억한 회차와 측정 중 회차(withHistory 면 측정 이력의 끝난 회차까지)의 서버 상태를 읽어, 끝난 것은 결과로 바꾼다 */
export async function syncSessions(acct: Account, withHistory = false): Promise<void> {
  const known = load().filter((k) => k.inst === acct.id)
  // 측정 이력은 로그인·새로고침 때 한 번만 읽는다(진행 중 작업 폴링 때마다 반려견 수만큼 부르지 않게)
  if (withHistory) for (const h of await historyOf(acct)) if (!known.some((k) => k.id === h.id)) known.push(h)
  for (const d of acct.dogs) {
    const open = (d as { open_session_id?: string | null }).open_session_id
    if (open && !known.some((k) => k.id === open)) known.push({ id: open, inst: acct.id, dog: d.id, started: Date.now(), n: 0, w: d.kg, by: '' })
  }
  let dirty = false
  for (const k of known) {
    if (acct.results.some((r) => r.id === k.id)) continue
    try {
      const s = await api.session(k.id)
      if (!FINAL.has(s.status)) {
        const srv = { status: s.status, total: s.shots.length, done: s.shots.filter((x) => x.status === 'DONE' || x.status === 'FAILED').length }
        const job = acct.jobs.find((j) => j.id === k.id)
        if (!job) {
          acct.jobs.push({ id: k.id, dog: k.dog, n: k.n || s.shots.length, w: k.w, started: k.started, videos: [], result_id: null, notified: false, by: k.by, remote: true, srv })
          dirty = true
        } else if (!job.srv || job.srv.status !== srv.status || job.srv.done !== srv.done || job.srv.total !== srv.total) {
          job.srv = srv // 진행 막대·문구가 서버 상태를 따라가게
          dirty = true
        }
        continue
      }
      const r = toResult(await api.sessionResult(k.id), k.dog)
      if (k.ord != null) r.ord = k.ord
      acct.results = [r, ...acct.results.filter((x) => x.id !== r.id)]
      const job = acct.jobs.find((j) => j.id === k.id)
      if (job) job.result_id = r.id
      dirty = true
    } catch (e) {
      // 지운 회차·다른 기관 회차는 잊는다. 그 밖의 오류는 다음 조회 때 다시
      if (e instanceof ApiError && (e.status === 404 || e.status === 403)) {
        save(load().filter((x) => x.id !== k.id))
        acct.jobs = acct.jobs.filter((j) => j.id !== k.id)
        dirty = true
      }
    }
  }
  if (dirty) {
    acct.results.sort(byNewest)
    changed()
  }
}

let timer = 0

/** 백엔드 모드에서 앱을 켤 때 한 번 부른다. 진행 중인 백엔드 작업이 있을 때만 서버를 읽는다 */
export function startPolling(getAcct: () => Account | undefined): void {
  if (timer) return
  const tick = async () => {
    const acct = getAcct()
    if (acct && acct.jobs.some((j) => j.remote && j.result_id == null)) await syncSessions(acct).catch(() => undefined)
    timer = window.setTimeout(tick, POLL_MS)
  }
  timer = window.setTimeout(tick, POLL_MS)
}
