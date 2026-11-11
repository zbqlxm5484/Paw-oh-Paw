// 웹 보고서 문구를 백엔드 보고서 검사 목록(backend/app/report/terms.yaml)에 대 본다.
// 웹 보고서(=인쇄 PDF)는 브라우저가 문장을 만들어 백엔드의 금지 표현 검사를 거치지 않으므로, 같은 목록을 여기서 건다.
// - forbidden: 어느 판본에도 0건(대소문자 무시, pattern 이 없으면 term 그대로)
// - jargon: 보호자용에 그 용어가 나오면 explanation 문구가 같은 문서에 한 번은 있어야 한다(백엔드 checks.py 와 같은 규칙)
// 데이터: 시연 데이터 기관의 모든 회차(분석 실패 제외)로 보호자용·수의사용 종이(ReportPaper)를 그려 본다.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { db } from '../store/db'
import { body_map, result_view } from './views'
import { ReportPaper } from '../pages/Report'

const TERMS = resolve(__dirname, '../../../backend/app/report/terms.yaml')

type Rule = { term: string; pattern?: string; explanation?: string }

/** terms.yaml 의 forbidden·jargon 목록만 읽는 작은 파서(목록 항목은 "- term:" 으로 시작, 값은 한 줄) */
function readRules(): { forbidden: Rule[]; jargon: Rule[] } {
  const out: { forbidden: Rule[]; jargon: Rule[] } = { forbidden: [], jargon: [] }
  let sec: 'forbidden' | 'jargon' | null = null
  let cur: Rule | null = null
  const unq = (v: string) => {
    const s = v.trim()
    return (s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'")) ? s.slice(1, -1) : s
  }
  for (const line of readFileSync(TERMS, 'utf-8').split(/\r?\n/)) {
    if (/^forbidden:/.test(line)) { sec = 'forbidden'; continue }
    if (/^jargon:/.test(line)) { sec = 'jargon'; continue }
    if (/^\S/.test(line)) { sec = null; continue }
    if (!sec || /^\s*#/.test(line)) continue
    const m = /^\s*(-\s+)?(term|pattern|explanation|reason):\s?(.*)$/.exec(line)
    if (!m) continue
    if (m[1]) { cur = { term: '' }; out[sec].push(cur) }
    if (!cur) continue
    if (m[2] === 'term') cur.term = unq(m[3])
    if (m[2] === 'pattern') cur.pattern = unq(m[3])
    if (m[2] === 'explanation') cur.explanation = unq(m[3])
  }
  return out
}

const RULES = readRules()
/** 백엔드 normalize: 줄바꿈·연속 공백을 공백 하나로 */
const norm = (s: string) => s.split(/\s+/).filter(Boolean).join(' ')
const text = (html: string) => norm(html.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&#x27;|&#39;/g, "'").replace(/&quot;/g, '"'))
/** 백엔드 _term_pattern: 용어 글자 사이 공백은 있어도 없어도 된다 */
const termRe = (t: string) => new RegExp([...t.replace(/\s+/g, '')].map((c) => c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('\\s*'))

/** 시연 데이터의 모든 (기관, 회차) 로 보호자용·수의사용 종이 글 */
function papers(): { id: string; kind: 'g' | 'v'; t: string }[] {
  const out: { id: string; kind: 'g' | 'v'; t: string }[] = []
  for (const acct of Object.values(db.accounts)) {
    for (const r of acct.results) {
      if (r.st === 'fail') continue
      const v = result_view(acct, r)
      const bm = body_map(acct, r)
      for (const kind of ['g', 'v'] as const) {
        const html = renderToStaticMarkup(<ReportPaper acct={acct} r={r} rd={v.rd} rp={v.rp} bm={bm} kind={kind} fromServer={false} />)
        out.push({ id: `${acct.id}/${r.id}`, kind, t: text(html) })
      }
    }
  }
  return out
}

describe('웹 보고서 문구 — 백엔드 보고서 검사 목록(terms.yaml)', () => {
  const P = papers()

  it('검사 목록과 그려 본 보고서가 있다', () => {
    expect(RULES.forbidden.length).toBeGreaterThan(10)
    expect(RULES.jargon.length).toBeGreaterThan(10)
    expect(P.length).toBeGreaterThan(0)
  })

  it('금지 표현이 어느 판본에도 없다', () => {
    const hits: string[] = []
    for (const rule of RULES.forbidden) {
      const re = new RegExp(rule.pattern ?? rule.term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i')
      for (const p of P) {
        const m = re.exec(p.t)
        if (m) hits.push(`[${rule.term}] ${p.kind === 'g' ? '보호자용' : '수의사용'} ${p.id}: …${p.t.slice(Math.max(0, m.index - 20), m.index + m[0].length + 20)}…`)
      }
    }
    expect([...new Set(hits)].slice(0, 20)).toEqual([])
  })

  it('보호자용에 나온 전문 용어는 같은 문서에 풀이가 있다', () => {
    const miss: string[] = []
    for (const p of P.filter((x) => x.kind === 'g')) {
      for (const j of RULES.jargon) {
        if (!j.explanation || !termRe(j.term).test(p.t)) continue
        if (!p.t.includes(norm(j.explanation))) miss.push(`[${j.term}] ${p.id}`)
      }
    }
    expect([...new Set(miss.map((m) => m.replace(/ .*$/, '')))]).toEqual([])
  })
})
