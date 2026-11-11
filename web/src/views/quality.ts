// 측정 신뢰도와 남은 촬영 수(QA 11-11, 285). 다리 쪽(카메라 쪽)마다 이 회차에서 쓴 걸음 수와, 변화 판정에 필요한 수까지 몇 번 더 걸려야 하는지.
// 기준 8 = 백엔드 report/judge.py TOLERANCE_MIN_PASSES: 오차 범위 값이 통과 8개 평균에서 나와, 8회 미만이면 회차 비교·좌우 차이를 범위로 견주지 않는다.
// 앱 frontend/src/design/app/quality.ts 와 같은 코드다.

/** 변화 판정(오차 범위로 견주기)에 필요한 쪽마다의 걸음 수(백엔드 TOLERANCE_MIN_PASSES) */
export const MIN_PASSES = 8

export type SideCount = { side: '왼쪽' | '오른쪽'; n: number | null; need: number }

export interface Quality {
  sides: SideCount[]
  /** 기준보다 적은 쪽이 있으면 다음 측정 안내(보호자도 읽는 쉬운 말). 없으면 null */
  hint: string | null
  /** 기준보다 적은 쪽이 있으면 변화 판정이 '값만'으로 나오는 이유. 없으면 null */
  judgeNote: string | null
}

const LEFT = ['LF', 'LH']
const RIGHT = ['RF', 'RH']

/** 다리(LF·RF·LH·RH)별 걸음 수(n_passes) → 쪽(왼쪽 = 카메라에 왼쪽이 보인 걸음)마다 가장 많이 쓴 수. 그 쪽 수치가 하나도 없으면 null */
function sideCount(np: Record<string, number | null | undefined>, limbs: string[]): number | null {
  const ns = limbs.map((l) => np[l]).filter((n): n is number => typeof n === 'number')
  return ns.length ? Math.max(...ns) : null
}

export function measureQuality(np: Record<string, number | null | undefined> | undefined | null): Quality | null {
  if (!np || !Object.keys(np).length) return null
  const sides: SideCount[] = ([['왼쪽', LEFT], ['오른쪽', RIGHT]] as const).map(([side, limbs]) => {
    const n = sideCount(np, limbs)
    return { side, n, need: Math.max(0, MIN_PASSES - (n ?? 0)) }
  })
  const short = sides.filter((s) => s.need > 0)
  if (!short.length) return { sides, hint: null, judgeNote: null }
  const parts = short.map((s) => `${s.side} ${s.need}번`)
  const hint = `다음 측정 때 ${short.length === 2 ? '양쪽' : short[0].side} 다리가 카메라 쪽으로 오게 ${parts.join(', ')} 더 걷게 해 주세요`
  const judgeNote = `${short.map((s) => s.side).join('·')}은 쓴 걸음이 ${MIN_PASSES}번보다 적어, 지난 측정과 견줄 때 변화는 판단하지 않고 값만 적어요`
  return { sides, hint, judgeNote }
}

/** "왼쪽 6/8 · 오른쪽 8/8" (그 쪽 걸음이 없으면 0) */
export function sidesText(q: Quality): string {
  return q.sides.map((s) => `${s.side} ${s.n ?? 0}/${MIN_PASSES}`).join(' · ')
}
