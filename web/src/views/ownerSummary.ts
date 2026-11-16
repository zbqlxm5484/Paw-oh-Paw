// 보호자용 요약 정리(QA 2절 3-4): 기준 회차 대비 달라진 다리 표시, 다음 방문까지 할 일과 병원 연락 기준.
// 판정은 수의사용 '지난 측정과 비교'와 같은 규칙(관절 가동 범위, 오차 범위 TOLERANCE)이다. 비교 상대는 기준 회차,
// 이 회차가 기준 회차이면 직전 유효 회차. 화면 문구는 진단·통증·좋아짐/나빠짐 단정을 하지 않는다(백엔드 terms.yaml forbidden).
import { dogOf } from '../store/db'
import type { Account, Result } from '../store/types'
import { base_of } from './views'
import { MIN_PASSES } from './quality'
import { gaitsOf, JOINTS, previousOf, TOLERANCE } from './vet'
import type { OwnerGuide } from './views'

export type LegCode = 'LF' | 'RF' | 'LH' | 'RH'
export const LEG_NAME: Record<LegCode, string> = { LF: '왼앞', RF: '오른앞', LH: '왼뒤', RH: '오른뒤' }

export interface LegChange {
  code: LegCode
  /** 오차 범위를 넘게 달라진 관절(증가·감소). 비어 있으면 범위 안 */
  joints: { n: string; dir: '증가' | '감소'; d: number }[]
  /** 비교할 값이 하나라도 있었는지 */
  compared: boolean
  /** 두 회차 중 한쪽이라도 이 다리의 쓴 걸음이 MIN_PASSES 보다 적어 변화를 판단하지 않았으면 true(백엔드 judge.usable_tolerance 와 같은 규칙) */
  short?: boolean
}

export interface OwnerChange {
  /** 비교한 회차의 날짜(MM.DD)와 이름(기준 회차·직전 회차) */
  baseLabel: string
  baseDate: string
  legs: LegChange[]
  /** 분석 방식이 달라 변화를 판단하지 않았으면 true */
  modelChanged: boolean
}

const r1 = (v: number) => Math.round(v * 10) / 10
const val = (m: Record<string, Record<string, number | null | undefined>> | undefined, code: string, limb: string): number | null => {
  const v = m?.[limb]?.[code]
  return v === undefined || v === null ? null : v
}

/** 이 회차를 기준 회차(이 회차가 기준이면 직전 유효 회차)와 견줘 다리마다 오차 범위를 넘게 달라진 관절. 견줄 회차가 없으면 null */
export function ownerChange(acct: Account, r: Result, gait: string): OwnerChange | null {
  if (r.st === 'fail') return null
  const d = dogOf(acct, r.dog)
  const baseId = d ? base_of(acct, d) : null
  let base: Result | null = baseId && baseId !== r.id ? acct.results.find((x) => x.id === baseId) ?? null : null
  let baseLabel = '기준 회차'
  // 기준 회차가 이 회차보다 나중이면(지난 회차 화면을 보는 중) 직전 회차와 견준다
  if (base && (base.day || '') > (r.day || '')) base = null
  if (!base) {
    base = previousOf(acct, r)
    baseLabel = '직전 회차'
  }
  if (!base) return null
  const tm = Object.fromEntries(gaitsOf(r))[gait]
  const bm = Object.fromEntries(gaitsOf(base))[gait]
  if (!tm || !bm) return null
  const modelChanged = !!(base.model && r.model && base.model !== r.model)
  // 걸음 수(np)는 백엔드 결과에만 있다. 있으면 두 회차 모두 그 다리가 MIN_PASSES 이상일 때만 변화를 판단한다(모르면 부족으로 본다)
  const hasNp = !!(r.np || base.np)
  const shortOf = (code: LegCode) => hasNp && ((r.np?.[code] ?? 0) < MIN_PASSES || (base!.np?.[code] ?? 0) < MIN_PASSES)
  const legs: LegChange[] = (['LF', 'RF', 'LH', 'RH'] as LegCode[]).map((code) => {
    const fh = code[1]
    const joints: LegChange['joints'] = []
    let compared = false
    const short = shortOf(code)
    for (const [mc, n, , part] of JOINTS) {
      if (part !== fh) continue
      const b = val(bm, mc, code), t = val(tm, mc, code)
      if (b == null || t == null) continue
      compared = true
      const tol = TOLERANCE[mc]
      const dd = r1(t - b)
      if (modelChanged || short || tol == null || Math.abs(dd) <= tol) continue
      joints.push({ n, dir: dd > 0 ? '증가' : '감소', d: dd })
    }
    return { code, joints, compared, short }
  })
  if (!legs.some((x) => x.compared)) return null
  const day = base.day || ''
  return { baseLabel, baseDate: day ? `${day.slice(5, 7)}.${day.slice(8, 10)}` : base.date, legs, modelChanged }
}

/** 다리 한 칸의 짧은 설명 */
export function legNote(x: LegChange): string {
  if (!x.compared) return '비교할 값 없음'
  if (x.short) return `걸음 수 부족(${MIN_PASSES}번 미만), 값만 비교`
  if (!x.joints.length) return '범위 안'
  return x.joints.map((j) => `${j.n} ${j.dir}`).join(', ')
}

export interface OwnerAdvice {
  /** 다음 방문까지 집에서 해 볼 것 */
  todo: string[]
  /** 다음 방문까지 지켜볼 모습 */
  watch: string[]
  /** 이럴 때는 병원에 연락하세요(관찰 기준만) */
  contact: string[]
}

/** 병원에 연락할 때: 의학적 판단 없이 집에서 보이는 모습만 */
export const CONTACT: string[] = [
  '평소와 다르게 한쪽 다리를 들고 걷거나, 디디지 않으려고 할 때',
  '산책이나 계단을 평소보다 피하거나, 금방 멈추려고 할 때',
  '다리를 만지면 싫어하거나, 붓거나 따뜻하게 느껴질 때',
  '며칠 사이에 걷는 모습이 눈에 띄게 달라졌을 때',
]

/** owner_guide(기존 안내 문장)를 '할 일·지켜볼 것'과 '병원 연락 기준'으로 나눈다. 기존 문장을 그대로 쓴다 */
export function ownerAdvice(og: OwnerGuide): OwnerAdvice {
  return { todo: og.help, watch: og.look, contact: CONTACT }
}
