// 기준 회차 대비 변화 프로필(QA 2절, S15P31A404-285): 관절·다리마다 '이번 − 기준' 변화량을 가로 막대로,
// 오차 범위(tolerance.yaml, 서버 비교 API 의 판정)를 0 가운데 회색 띠로. 판정은 증가·감소·범위 안·값만(평가 단어 없음).
import type { CompareItemOut, CompareOut } from '../api/client'
import type { Account, Result } from '../store/types'
import { base_of } from './views'
import { GAIT_CODE, gaitsOf, JOINTS, TOLERANCE } from './vet'

export type ProfileJudge = 'INCREASE' | 'DECREASE' | 'WITHIN_RANGE' | 'VALUE_ONLY'

export interface ProfileRow {
  code: string
  joint: string
  limb: string
  side: string
  base: number
  target: number
  diff: number
  /** 오차 범위(원 단위). 판정에 쓰지 못하면(통과 수 부족·범위 없음·모델 다름) null */
  tol: number | null
  j: ProfileJudge
}

export interface ProfileView {
  baseId: string
  baseDate: string
  targetDate: string
  modelChanged: boolean
  rows: ProfileRow[]
  /** 막대 축의 한쪽 끝(원 단위). 모든 줄의 |변화량|·오차 범위보다 조금 크게 */
  scale: number
}

const SIDE: Record<string, string> = { LF: '왼앞', RF: '오른앞', LH: '왼뒤', RH: '오른뒤' }
const LIMBS_OF: Record<'F' | 'H', string[]> = { F: ['LF', 'RF'], H: ['LH', 'RH'] }
/** 가동 범위 6개만(입각기 비율 등은 단위가 달라 한 축에 놓지 않는다) */
const ROM = JOINTS.filter(([c]) => c.startsWith('rom_'))

export const JUDGE_LABEL: Record<ProfileJudge, string> = { INCREASE: '증가', DECREASE: '감소', WITHIN_RANGE: '범위 안', VALUE_ONLY: '값만' }

const r1 = (v: number) => Math.round(v * 10) / 10

/** 브라우저 계산 판정: 오차 범위가 없으면 값만, 범위보다 크면 증가·감소(경계값은 범위 안, 서버 judge.py 와 같음) */
export function judgeLocal(diff: number, tol: number | null): ProfileJudge {
  if (tol == null) return 'VALUE_ONLY'
  const d = r1(diff)
  if (d > tol) return 'INCREASE'
  if (d < -tol) return 'DECREASE'
  return 'WITHIN_RANGE'
}

/** 서버 판정 → 프로필 판정. UNKNOWN(범위 없음·통과 수 부족·모델 다름)·NOT_COMPARABLE 은 값만 */
export function judgeFromServer(j: string): ProfileJudge {
  return j === 'INCREASE' || j === 'DECREASE' || j === 'WITHIN_RANGE' ? j : 'VALUE_ONLY'
}

function scaleOf(rows: ProfileRow[]): number {
  const m = Math.max(5, ...rows.map((x) => Math.abs(x.diff)), ...rows.map((x) => x.tol ?? 0))
  return Math.ceil(m * 1.15)
}

/** 막대·띠의 위치(축 전체 0~100%, 0 은 50%) */
export function geom(v: number, scale: number): { left: number; width: number } {
  const w = Math.min(50, (Math.abs(v) / scale) * 50)
  return v >= 0 ? { left: 50, width: w } : { left: 50 - w, width: w }
}

/** 백엔드 비교 API(base=BASELINE) 응답 → 프로필. 이번 회차가 기준이면(같은 회차) null */
export function profileFromServer(o: CompareOut, gait: string): ProfileView | null {
  if (o.base.session_id === o.target.session_id) return null
  const rows: ProfileRow[] = []
  for (const [code, joint, , fh] of ROM) {
    for (const limb of LIMBS_OF[fh]) {
      const it = o.items.find((x: CompareItemOut) => x.metric_code === code && x.limb === limb && x.gait_type === gait)
      if (!it || it.base_value == null || it.target_value == null) continue
      const j = judgeFromServer(it.judgement)
      rows.push({
        code, joint, limb, side: SIDE[limb], base: it.base_value, target: it.target_value, diff: r1(it.target_value - it.base_value),
        tol: j === 'VALUE_ONLY' ? null : TOLERANCE[code] ?? null, j,
      })
    }
  }
  if (!rows.length) return null
  return { baseId: o.base.session_id, baseDate: o.base.measured_on, targetDate: o.target.measured_on, modelChanged: o.model_changed, rows, scale: scaleOf(rows) }
}

/** 시연 데이터(브라우저 회차): 반려견의 기준 회차와 같은 보행끼리 브라우저에서 계산(통과 수 조건은 알 수 없어 보지 않음) */
export function profileLocal(acct: Account, r: Result, gaitName: string): ProfileView | null {
  const dog = acct.dogs.find((x) => x.id === r.dog)
  if (!dog) return null
  const baseId = base_of(acct, dog)
  if (!baseId || baseId === r.id) return null
  const b = acct.results.find((x) => x.id === baseId)
  if (!b || b.st === 'fail') return null
  const tm = Object.fromEntries(gaitsOf(r))[gaitName]
  const bm = Object.fromEntries(gaitsOf(b))[gaitName]
  if (!tm || !bm) return null
  const rows: ProfileRow[] = []
  for (const [code, joint, , fh] of ROM) {
    for (const limb of LIMBS_OF[fh]) {
      const t = tm[limb]?.[code], bv = bm[limb]?.[code]
      if (t == null || bv == null) continue
      const diff = r1(t - bv)
      const tol = TOLERANCE[code] ?? null
      rows.push({ code, joint, limb, side: SIDE[limb], base: bv, target: t, diff, tol, j: judgeLocal(diff, tol) })
    }
  }
  if (!rows.length) return null
  return { baseId, baseDate: b.day, targetDate: r.day, modelChanged: false, rows, scale: scaleOf(rows) }
}

/** 보행 이름(속보·평보·보행 유형 미판별) → 서버 코드 */
export const gaitCode = (gaitName: string): string => GAIT_CODE[gaitName] ?? 'TROT'
