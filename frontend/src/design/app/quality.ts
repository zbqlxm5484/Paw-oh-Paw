// 측정 신뢰도와 남은 촬영 수(QA 11-11, 285). 다리 쪽(카메라 쪽)마다 이 회차에서 쓴 걸음 수와, 변화 판정에 필요한 수까지 몇 번 더 걸려야 하는지.
// 기준 8 = 백엔드 report/judge.py TOLERANCE_MIN_PASSES: 오차 범위 값이 통과 8개 평균에서 나와, 8회 미만이면 회차 비교·좌우 차이를 범위로 견주지 않는다.
// 웹 web/src/views/quality.ts 와 같은 코드다.

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

// ---- 쓰지 못한 걸음의 사유별 수(285) ----
// 백엔드 결과의 exclude_summary(사유 문구 message, 그 사유로 뺀 통과 수 count)를 한 줄로 묶는다. 사유 글은 서버 문구 그대로(끝 마침표만 뗀다).
// 시연(브라우저) 회차는 화면이 만든 사유가 들어오고, 없으면 줄을 숨긴다.

export type ExcludeReason = { msg: string; n: number }
export interface ExcludeSummary {
  /** 쓰지 못한 걸음(제외된 통과) 수 = 사유별 수의 합(백엔드 pass_counts.excluded 와 같다) */
  total: number
  /** 많은 순(같으면 들어온 순) */
  reasons: ExcludeReason[]
}

/** [사유 문구, 수][] → 같은 문구는 합치고 많은 순으로. 합이 0이거나 비면 null(줄을 숨긴다) */
export function excludeSummary(ex: readonly (readonly [string, number])[] | null | undefined): ExcludeSummary | null {
  if (!ex || !ex.length) return null
  const reasons: ExcludeReason[] = []
  for (const [m, c] of ex) {
    const n = Number(c)
    if (!Number.isFinite(n) || n <= 0) continue
    const msg = String(m ?? '').trim().replace(/[.。]+$/, '') || '사유를 알 수 없습니다'
    const hit = reasons.find((x) => x.msg === msg)
    if (hit) hit.n += n
    else reasons.push({ msg, n })
  }
  const total = reasons.reduce((s, x) => s + x.n, 0)
  if (!total) return null
  // sort 는 안정 정렬이라 같은 수는 들어온 순서(서버는 이미 많은 순·코드 순)를 지킨다
  return { total, reasons: reasons.sort((a, b) => b.n - a.n) }
}

/** "뛰었습니다. 천천히 걷게 해 주세요 (3번) · 중간에 멈췄습니다 (2번)". 사유 문구가 '…해 주세요'로 끝나기도 해서 수는 괄호에 둔다 */
export function excludeReasonsText(s: ExcludeSummary): string {
  return s.reasons.map((x) => `${x.msg} (${x.n}번)`).join(' · ')
}

/** "쓰지 못한 걸음 5번: 뛰었습니다. 천천히 걷게 해 주세요 (3번) · 중간에 멈췄습니다 (2번)" */
export function excludeText(s: ExcludeSummary, lead = '쓰지 못한 걸음'): string {
  return `${lead} ${s.total}번: ${excludeReasonsText(s)}`
}

/** 서버 사유 문구에 나올 수 있는 전문 용어와 보호자용 풀이(backend/app/report/terms.yaml jargon 의 explanation 그대로) */
const OWNER_TERMS: [string, string][] = [
  ['측대보', '같은 쪽 앞발과 뒷발이 함께 움직이는 걸음'],
  ['평보', '네 발이 차례로 바닥을 딛는 느린 걸음'],
  ['속보', '대각선 방향의 앞발과 뒷발이 함께 바닥을 딛는 빠른 걸음'],
  ['보행 주기', '한 발이 바닥에 닿은 뒤 다시 닿을 때까지의 한 걸음'],
  ['관절점', '영상에서 찾은 관절의 위치 점'],
  ['유효 통과', '수치 계산에 쓸 수 있는, 매트를 옆으로 곧게 지나간 걷기 한 번'],
]

/** 보호자용: 사유 문구에 들어 있는 전문 용어의 풀이("측대보: 같은 쪽 …"). 없으면 빈 배열 */
export function excludeTerms(s: ExcludeSummary): string[] {
  const all = s.reasons.map((x) => x.msg).join(' ')
  return OWNER_TERMS.filter(([t]) => new RegExp(t.split(' ').join('\\s*')).test(all)).map(([t, e]) => `${t}: ${e}`)
}
