// 분석 작업 흉내. prototype/proto_app/analysis.py 그대로.
// 실서비스: 업로드 → 분석 API(관절점 추출 · 유효 판별 · 보행 수치) → 회차 결과 저장.
// 여기서는 시작 시각으로 진행률을 계산하고, 끝나면 직전 회차를 바탕으로 결과를 만든다 (디자인의 finishAna).
import * as config from '../config'
import { activeJobs, dogOf, isoToday, jobProgress, kdate, new_id } from '../store/db'
import type { Account, Job, Result } from '../store/types'
import { floordiv, pyround } from './pyfmt'

/** seed.J: 무릎·고관절·팔꿈치 [이름, 왼, 오] */
export function J(a: [number, number], b: [number, number], c: [number, number]): [string, number, number][] {
  return [['무릎', a[0], a[1]], ['고관절', b[0], b[1]], ['팔꿈치', c[0], c[1]]]
}

export function start_job(acct: Account, dog_id: string, n: number, weight: string, videos: string[]): Job {
  const job: Job = { id: new_id('job'), dog: dog_id, n, w: weight, started: Date.now(), videos, result_id: null, notified: false, by: '' }
  acct.jobs.push(job)
  return job
}

/** 진행이 끝난 작업을 결과로 바꾼다. 새로 끝난 작업 목록을 돌려준다. */
export function finish_due_jobs(acct: Account): Job[] {
  const done: Job[] = []
  for (const job of activeJobs(acct)) {
    if (!job.remote && jobProgress(job) >= 5) {   // 백엔드 회차는 서버가 끝났다고 할 때만(sessions_backend)
      job.result_id = _make_result(acct, job).id
      done.push(job)
    }
  }
  return done
}

function hhmm(): string {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function _make_result(acct: Account, job: Job): Result {
  const dog = dogOf(acct, job.dog)
  const prev = acct.results.find((r) => r.dog === job.dog && r.st !== 'fail')
  let b_sym: number, b_rom: number, b_sL: number, b_sR: number, b_j: [string, number, number][]
  if (prev) [b_sym, b_rom, b_sL, b_sR, b_j] = [prev.sym, prev.rom, prev.sL, prev.sR, prev.j]
  else [b_sym, b_rom, b_sL, b_sR, b_j] = [88, 46, 30, 28, J([60, 55], [42, 39], [50, 48])]
  const n = job.n || config.MAX_SHOTS
  const meas = pyround(n * 1.1)
  const used = pyround(meas * 0.68)
  const exc = meas - used
  const ex = ([['뛰었음', -floordiv(-exc, 2)], ['중간에 멈춤', floordiv(exc, 2)]] as [string, number][]).filter(([, c]) => c > 0)
  const r: Result = {
    id: new_id('res'), dog: job.dog, date: kdate(), time: hhmm(), st: 'ok',
    w: job.w || (dog && dog.kg ? dog.kg : '-'), model: config.MODEL,
    sym: Math.min(98, b_sym + 2), rom: b_rom + 1, sL: b_sL, sR: Math.min(b_sL, b_sR + 1),
    j: b_j.map(([nm, left, right]) => [nm, left, Math.min(left, right + 2)] as [string, number, number]),
    ps: [meas, used], ex, rep: true, videos: job.videos, day: isoToday(), by: job.by, m: {}, src: '',
  }
  if (prev && prev.m && Object.keys(prev.m).length) {
    // 실측 수치가 붙은 직전 회차가 있으면 그 수치를 이어 쓴다(새 실측 회차를 지어내지 않는다)
    Object.assign(r, { m: prev.m, src: prev.src, sym: prev.sym, rom: prev.rom, sL: prev.sL, sR: prev.sR, j: prev.j })
  }
  acct.results.unshift(r)
  return r
}
