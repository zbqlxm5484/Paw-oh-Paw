// 가짜 서버(vite --mode mock): GET /sessions/{id}/report-content(285)를 시연 회차 값으로 흉내 낸다.
// 백엔드 없이 인쇄 화면(/print/reports/:rid)이 서버 내용으로 그리는 모양을 보려는 것이다. 모양은 백엔드와 합의한 응답 그대로,
// 문장은 backend/app/report/sentences.py 의 틀을 따른다(실제 서버 문장과 글자까지 같지는 않다).
// 시험용: 주소에 mock_error=REPORT_CHECK_FAILED|SESSION_NOT_DONE|NOT_FOUND 를 붙이면 그 오류로 답한다.
import {
  ApiError, registerMock, type ReportContentChange, type ReportContentCompare, type ReportContentGait, type ReportContentOut,
  type ReportContentRow, type ReportEdition,
} from '../api/client'
import { db, dogOf } from '../store/db'
import { SEX_OUT, SIZE_OUT } from '../store/backend'
import type { Account, Metrics, Result } from '../store/types'
import { base_of, sess_no } from '../views/views'
import { gaitsOf, GAIT_CODE, previousOf, TOLERANCE } from '../views/vet'
import { cardGait, pairViews, PAIRS as PAIR_CODES } from '../views/reportContent'

const LABELS: Record<string, string> = {
  rom_shoulder: '어깨 가동 범위', rom_elbow: '팔꿈치 가동 범위', rom_carpus: '앞발목 가동 범위',
  rom_hip: '고관절 가동 범위', rom_stifle: '무릎 가동 범위', rom_tarsus: '뒷발목 가동 범위',
  stride_length: '걸음 길이', stance_ratio: '입각기 비율', paw_lift: '발 들림 높이', stifle_cv: '무릎 움직임 일관성',
}
const ORDER = Object.keys(LABELS)
const UNIT = (code: string) => (code.startsWith('rom_') ? 'deg' : code === 'stance_ratio' || code === 'stifle_cv' ? 'pct' : 'pct_body')
const LABEL = (code: string, unit: string) => (LABELS[code] ?? code) + (unit === 'pct_body' ? '(몸통 길이 기준)' : '')
const GAIT_LABEL: Record<string, string> = { TROT: '속보', WALK: '평보', OTHER: '보행 유형 미판별' }
const LIMBS = ['LF', 'RF', 'LH', 'RH']
const PAIRS: [string, string, string, string][] = [['FORE', '앞다리', 'LF', 'RF'], ['HIND', '뒷다리', 'LH', 'RH']]

function fmtValue(v: number | null, unit: string): string {
  if (v == null) return '측정 불가'
  if (unit === 'deg') return `${v.toFixed(1)}°`
  if (unit === 'pct') return `${v.toFixed(1)}%`
  return `${v.toFixed(2)}%`
}
function fmtChange(d: number, unit: string): string {
  const sign = d > 0 ? '+' : d < 0 ? '-' : ''
  if (unit === 'pct') return `${sign}${Math.abs(d).toFixed(1)}%p`
  if (unit === 'pct_body') return `${sign}${Math.abs(d).toFixed(2)}%p`
  return `${sign}${fmtValue(Math.abs(d), unit)}`
}
const r2 = (v: number) => Math.round(v * 100) / 100
const r4 = (v: number) => Math.round(v * 10000) / 10000

function rowsOf(m: Metrics): ReportContentRow[] {
  const codes = ORDER.filter((c) => LIMBS.some((l) => m[l]?.[c] != null))
  return codes.map((code) => {
    const unit = UNIT(code)
    const cells: ReportContentRow['cells'] = {}
    for (const l of LIMBS) {
      if (!m[l] || !(code in m[l])) continue // 그 다리에 없는 수치(앞다리의 무릎 등)는 칸을 만들지 않는다
      const v = m[l][code]
      cells[l] = v == null ? { value: null, text: '측정 불가', reason: '반대쪽 다리가 가려졌습니다.' } : { value: v, text: fmtValue(v, unit), reason: null }
    }
    return { metric_code: code, label: LABEL(code, unit), unit, cells }
  })
}

/** 15.7 limb_compare 처럼: 쌍·수치마다 왼쪽 − 오른쪽, 대칭 지수. 대칭 지수 큰 순서 */
function compareOf(m: Metrics): ReportContentCompare[] {
  const out: ReportContentCompare[] = []
  for (const [pair, pairLabel, l, r] of PAIRS) {
    for (const code of ORDER) {
      const a = m[l]?.[code], b = m[r]?.[code]
      if (a == null && b == null) continue
      const unit = UNIT(code)
      const ok = a != null && b != null
      const diff = ok ? r4(a - b) : null
      const si = ok && a + b !== 0 ? r2((Math.abs(a - b) / ((a + b) / 2)) * 100) : null
      out.push({
        pair, pair_label: pairLabel, metric_code: code, label: LABEL(code, unit),
        left: fmtValue(a ?? null, unit), right: fmtValue(b ?? null, unit),
        diff: ok ? fmtValue(diff, unit) : '-', symmetry_index: si != null ? `${si.toFixed(1)}%` : '-',
        diff_value: diff, symmetry_value: si, comparable: ok, reason: ok ? null : '한쪽 다리를 측정하지 못했습니다.',
      })
    }
  }
  return out.sort((x, y) => (y.symmetry_value ?? -1) - (x.symmetry_value ?? -1))
}

function changesOf(now: Metrics, before: Metrics, modelChanged: boolean): ReportContentChange[] {
  const out: ReportContentChange[] = []
  for (const code of ORDER) {
    const unit = UNIT(code)
    const cells: ReportContentChange['cells'] = {}
    for (const l of LIMBS) {
      const a = before[l]?.[code], b = now[l]?.[code]
      if (a == null && b == null) continue
      if (a == null || b == null) {
        cells[l] = { previous: fmtValue(a ?? null, unit), current: fmtValue(b ?? null, unit), diff: null, change: null, change_label: null, note: a == null ? '직전 회차: 측정하지 못했습니다.' : '이번 회차: 측정하지 못했습니다.' }
        continue
      }
      const d = r4(b - a)
      const tol = TOLERANCE[code]
      const change = modelChanged || tol == null ? null : Math.abs(d) <= tol ? 'WITHIN_RANGE' : d > 0 ? 'INCREASE' : 'DECREASE'
      cells[l] = {
        previous: fmtValue(a, unit), current: fmtValue(b, unit), diff: modelChanged ? null : fmtChange(d, unit),
        change, change_label: change ? ({ INCREASE: '증가', DECREASE: '감소', WITHIN_RANGE: '범위 안' } as Record<string, string>)[change] : null, note: null,
      }
    }
    if (Object.keys(cells).length) out.push({ metric_code: code, label: LABEL(code, unit), unit, cells })
  }
  return out
}

const GLOSSARY: [string, string][] = [
  ['가동 범위', '걸을 때 관절을 접었다 펴는 각도의 폭'],
  ['대칭 지수', '왼쪽과 오른쪽 값의 차이를 두 값의 평균으로 나눈 백분율'],
  ['입각기', '한 걸음 중 발이 바닥을 딛고 있는 구간'],
  ['오차 범위', '같은 상태를 다시 재도 생길 수 있는 값의 차이'],
  ['고관절', '뒷다리가 몸통과 이어지는 엉덩이 관절'],
  ['속보', '대각선 방향의 앞발과 뒷발이 함께 바닥을 딛는 빠른 걸음'],
]

/** legs: 서버와 같은 규칙(TROT → WALK → OTHER 중 비교할 수 있는 첫 유형, 쌍마다 대칭 지수 최대, 반올림 뒤 5·10 경계, 작은 쪽이 덜 쓰는 다리).
 *  비교할 줄이 없는 쌍은 뺀다 */
function legsOf(c: ReportContentOut): NonNullable<ReportContentOut['legs']> {
  const g = cardGait(c)
  const pv = pairViews({ ...c, legs: undefined }, g)
  return PAIR_CODES.flatMap((pair) => {
    const v = pv[pair]
    if (!v.level || !v.line || !g) return []
    return [{
      pair, gait_type: g.gait_type, metric_code: v.line.metric_code, label: v.line.label, symmetry_index: v.line.symmetry_index,
      symmetry_value: v.line.symmetry_value, weak_limb: v.weak as 'LF' | 'RF' | 'LH' | 'RH' | null, level: v.level,
    }]
  })
}

export function mockReportContent(acct: Account, r: Result, edition: ReportEdition): ReportContentOut {
  const c = mockBase(acct, r, edition)
  return { ...c, legs: legsOf(c) }
}

function mockBase(acct: Account, r: Result, edition: ReportEdition): ReportContentOut {
  const d = dogOf(acct, r.dog)
  const prev = previousOf(acct, r)
  const modelChanged = !!prev && prev.model !== r.model
  const prevG = prev ? Object.fromEntries(gaitsOf(prev).map(([g, m]) => [GAIT_CODE[g] ?? 'OTHER', m])) : {}
  const gaits: ReportContentGait[] = gaitsOf(r).filter(([, m]) => m && Object.keys(m).length).map(([g, m]) => {
    const code = GAIT_CODE[g] ?? 'OTHER'
    const rows = rowsOf(m)
    const n = rows.reduce((a, x) => a + Object.keys(x.cells).length, 0)
    const measured = rows.reduce((a, x) => a + Object.values(x.cells).filter((c) => c?.value != null).length, 0)
    return {
      gait_type: code, label: GAIT_LABEL[code], notes: [`${GAIT_LABEL[code]}: 수치 ${n}개 중 ${measured}개를 측정했습니다.`],
      rows, compare: compareOf(m), changes: prevG[code] ? changesOf(m, prevG[code], modelChanged) : [],
    }
  })
  const all = acct.results.filter((x) => x.dog === r.dog)
  const idx = all.findIndex((x) => x.id === r.id)
  const history = all.slice(idx).slice(0, 8).reverse().map((x) => ({ measured_on: x.day, round: sess_no(acct, x), symmetry_score: x.st === 'fail' ? null : x.sym }))
  const baseId = d ? base_of(acct, d) : null
  const base = baseId ? all.find((x) => x.id === baseId) : undefined
  const name = d?.name ?? '-'
  const top = gaits[0]?.compare.find((x) => x.comparable)
  const summary = top
    ? [`${gaits[0].label}에서 왼쪽과 오른쪽의 차이를 비율로 볼 때 가장 큰 항목은 ${top.pair_label} ${top.label}입니다. 왼쪽 ${top.left}, 오른쪽 ${top.right}, 차이 ${top.diff}입니다.`
      + (edition === 'VET' ? ` 대칭 지수 ${top.symmetry_index}.` : '')]
    : ['왼쪽과 오른쪽을 비교할 수 있는 수치가 없어 차이를 적지 않았습니다.']
  if (top && edition === 'OWNER') {
    const tol = TOLERANCE[top.metric_code]
    summary.push(tol == null || top.diff_value == null
      ? '좌우 차이는 촬영 조건에 따라서도 달라질 수 있어, 이 수치만으로 변화를 판단하지 않습니다. 다음 측정과 같은 조건에서 비교해 보세요.'
      : Math.abs(top.diff_value) <= tol ? '이 차이는 측정 오차 범위 안에 있습니다.'
        : '이 차이는 측정 오차 범위보다 큽니다. 다음 측정에서도 같은 다리에 차이가 이어지는지 담당 수의사와 함께 봐 주세요.')
  }
  const hasChanges = gaits.some((g) => g.changes.length)
  return {
    session_id: r.id, edition, template_version: '0.5',
    session: {
      measured_on: r.day, round: sess_no(acct, r), model_name: 'pga-pose', model_version: r.model,
      weight_kg: Number.isFinite(Number(r.w)) && r.w !== '' && r.w !== '-' ? Number(r.w) : null,
      size_class: SIZE_OUT[d?.size ?? 'M'] ?? 'MEDIUM', symmetry_score: r.sym,
      symmetry_level: 100 - r.sym < 5 ? 'SIMILAR' : 100 - r.sym < 10 ? 'SLIGHT' : 'LARGE',
    },
    dog: { name, breed: d?.breed ?? null, sex: d ? SEX_OUT[d.sex] ?? null : null, birth_year: d && d.birth ? Number(d.birth) : null, focus_limb: d?.focus ?? null },
    previous: prev ? { session_id: prev.id, measured_on: prev.day, round: sess_no(acct, prev), model_changed: modelChanged } : null,
    baseline: base ? { session_id: base.id, measured_on: base.day, round: sess_no(acct, base), symmetry_score: base.sym, diff: r.sym - base.sym } : null,
    history,
    sentences: {
      title: `${name} 보행 평가 보고서`, edition_label: edition === 'VET' ? '수의사용' : '보호자용',
      intro: `${r.day}에 ${name}의 걷는 모습을 촬영해 수치를 냈습니다. 걸음 ${r.ps[0]}회를 보았고, 그중 ${r.ps[1]}회로 수치를 냈습니다(제외 ${r.ps[0] - r.ps[1]}회).`,
      summary,
      previous_note: prev && hasChanges
        ? modelChanged ? `직전 회차(${prev.day})는 분석 방식이 달라 값만 표에 함께 적고, 변화는 판단하지 않았습니다.`
          : `직전 회차(${prev.day})와 이번 회차의 값을 표에 나란히 적었습니다. 차이는 이번 값에서 직전 값을 뺀 것입니다. 값의 차이는 측정 조건에 따라서도 생길 수 있습니다.`
        : null,
      previous_gaps: [],
      caution: edition === 'OWNER'
        ? ['수치는 촬영 조건(바닥, 걷는 속도, 카메라 각도)에 따라 달라질 수 있습니다. 같은 조건에서 다시 잰 값과 비교해 주세요.', '걱정되는 변화가 있으면 담당 수의사와 상의해 주세요.']
        : ['수치는 촬영 조건(바닥, 걷는 속도, 카메라 각도)에 따라 달라질 수 있습니다. 같은 조건에서 다시 잰 값과 비교해 주세요.', '이 수치는 영상에서 추정한 값이며, 임상 판단의 보조 자료입니다.'],
      glossary: edition === 'OWNER' ? GLOSSARY.map(([term, explanation]) => ({ term, explanation })) : [],
      disclaimer: '이 보고서는 보행 평가 보조 자료이며 진단을 대신하지 않습니다.',
    },
    gaits,
  }
}

function findResult(id: string): [Account, Result] | null {
  for (const a of Object.values(db.accounts)) {
    const r = a.results.find((x) => x.id === id)
    if (r) return [a, r]
  }
  return null
}

const ERR: Record<string, [number, string]> = {
  NOT_FOUND: [404, '회차를 찾을 수 없습니다.'],
  SESSION_NOT_DONE: [409, '분석이 끝나지 않은 회차입니다.'],
  REPORT_CHECK_FAILED: [409, '보고서 검사를 통과하지 못했습니다.'],
}
const fail = (code: string) => {
  const [status, message] = ERR[code] ?? [500, '일시적인 오류가 발생했습니다.']
  return Promise.reject(new ApiError(status, { code, message, detail: null }))
}

registerMock((method, path) => {
  // 무릎 곡선용 회차 상세·촬영 각도는 시연 데이터에 없다 → 404(인쇄 화면은 그 칸을 뺀다)
  if (method === 'GET' && (/^\/sessions\/[^/?]+$/.test(path) || /^\/shots\/[^/?]+\/angles$/.test(path))) return fail('NOT_FOUND')
  const m = /^\/sessions\/([^/?]+)\/report-content\?edition=(OWNER|VET)$/.exec(path)
  if (method !== 'GET' || !m) return undefined
  const forced = new URLSearchParams(window.location.search).get('mock_error')
  if (forced) return fail(forced)
  const hit = findResult(decodeURIComponent(m[1]))
  if (!hit) return fail('NOT_FOUND')
  if (hit[1].st === 'fail') return fail('SESSION_NOT_DONE')
  return Promise.resolve(mockReportContent(hit[0], hit[1], m[2] as ReportEdition))
})
