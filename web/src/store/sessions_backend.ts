// 백엔드 회차 → 화면의 분석 작업(Job)·결과(Result).
// 반려견별 회차 목록 API 가 아직 없어서, 이 브라우저에서 연 회차를 기억해 두고(localStorage)
// 반려견의 측정 중 회차(open_session_id)와 함께 서버 상태를 읽는다. 끝난 회차는 /sessions/{id}/result 로 결과를 만든다.
import { api, ApiError, type SessionResultOut } from '../api/client'
import { applyMetrics } from '../views/real'
import { changed, kdate } from './db'
import type { Account, Metrics, Result } from './types'

const KEY = 'pp.web.sessions'
const POLL_MS = 4000
const FINAL = new Set(['DONE', 'FAILED'])
export const SERVER_FAIL_MSG = '분석에 실패했어요. 잠시 후 다시 시도해 주세요.'

/** 이 브라우저에서 연 회차 */
export interface Known {
  id: string
  inst: string
  dog: string
  started: number
  n: number
  w: string
  by: string
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
    const m: Metrics = {}
    for (const x of pick[0]!.metrics) {
      if (x.limb === 'NONE' || x.value == null || !x.measurable) continue
      ;(m[x.limb] ??= {})[x.metric_code] = x.value
    }
    applyMetrics(r, m)
    r.gait = pick[1]
  }
  return r
}

/** 기억한 회차와 측정 중 회차의 서버 상태를 읽어, 끝난 것은 결과로 바꾼다 */
export async function syncSessions(acct: Account): Promise<void> {
  const known = load().filter((k) => k.inst === acct.id)
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
        if (!acct.jobs.some((j) => j.id === k.id)) {
          acct.jobs.push({ id: k.id, dog: k.dog, n: k.n || s.shots.length, w: k.w, started: k.started, videos: [], result_id: null, notified: false, by: k.by, remote: true })
          dirty = true
        }
        continue
      }
      const r = toResult(await api.sessionResult(k.id), k.dog)
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
  if (dirty) changed()
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
