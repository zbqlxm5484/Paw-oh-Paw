// 파이썬 views.py 와 TS 옮김이 같은 값을 내는지 견준다. 기대값은 web/scripts/dump_views.py 로 만든다.
// 기대값 파일(__parity__/expected.json)은 크고(약 15MB) 만든 날에 따라 달라 git 에 넣지 않는다. 없으면 이 비교는 건너뛴다.
// 날짜: 시연 데이터는 '오늘' 기준으로 날짜를 옮기므로, 기대값을 뜬 날(E.today)로 시계를 고정한 뒤 데이터를 불러온다.
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import type { Account } from '../store/types'
import * as P from './pyfmt'

const found = import.meta.glob('./__parity__/expected.json', { eager: true, import: 'default' })
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const E: any = Object.values(found)[0] ?? null
let acct: Account
let V: typeof import('./views')
let activeJobs: typeof import('../store/db').activeJobs
const SVG_FULL = new Set(['r1', 'r2', 'r3', 'r4', 'r5'])
const CMP_DOGS = ['d1', 'd2', 'd3', 'd4', 'g001', 'g002', 'g003']

// 파이썬 json 처럼: Set 은 정렬한 배열, undefined 는 빠짐
const plain = (o: unknown): unknown => JSON.parse(JSON.stringify(o, (_k, v) => (v instanceof Set ? [...v].sort() : v)))

// 파이썬 3.13 에서 직접 뽑은 값: [x, round(x), round(x,1), round(x,2), .1f, .0f, +.1f, g, repr(round(x,1))]
const PY: [number, number, number, number, string, string, string, string, string][] = [
  [0.5, 0, 0.5, 0.5, '0.5', '0', '+0.5', '0.5', '0.5'], [1.5, 2, 1.5, 1.5, '1.5', '2', '+1.5', '1.5', '1.5'],
  [2.5, 2, 2.5, 2.5, '2.5', '2', '+2.5', '2.5', '2.5'], [-0.5, 0, -0.5, -0.5, '-0.5', '-0', '-0.5', '-0.5', '-0.5'],
  [-2.5, -2, -2.5, -2.5, '-2.5', '-2', '-2.5', '-2.5', '-2.5'], [0.125, 0, 0.1, 0.12, '0.1', '0', '+0.1', '0.125', '0.1'],
  [0.375, 0, 0.4, 0.38, '0.4', '0', '+0.4', '0.375', '0.4'], [2.675, 3, 2.7, 2.67, '2.7', '3', '+2.7', '2.675', '2.7'],
  [1.005, 1, 1.0, 1.0, '1.0', '1', '+1.0', '1.005', '1.0'], [-0.04, 0, -0.0, -0.04, '-0.0', '-0', '-0.0', '-0.04', '-0.0'],
  [9.96, 10, 10.0, 9.96, '10.0', '10', '+10.0', '9.96', '10.0'], [0.05, 0, 0.1, 0.05, '0.1', '0', '+0.1', '0.05', '0.1'],
  [0.15, 0, 0.1, 0.15, '0.1', '0', '+0.1', '0.15', '0.1'], [0.25, 0, 0.2, 0.25, '0.2', '0', '+0.2', '0.25', '0.2'],
  [123.45, 123, 123.5, 123.45, '123.5', '123', '+123.5', '123.45', '123.5'], [28.1, 28, 28.1, 28.1, '28.1', '28', '+28.1', '28.1', '28.1'],
  [1e-5, 0, 0.0, 0.0, '0.0', '0', '+0.0', '1e-05', '0.0'],
]

describe('pyfmt', () => {
  it('round·서식이 파이썬과 같다', () => {
    for (const [x, r0, r1, r2, f1, f0, s1, gg, rp] of PY) {
      expect(P.pyround(x), `round(${x})`).toBe(r0)
      expect(P.pyround(x, 1), `round(${x},1)`).toEqual(r1)
      expect(P.pyround(x, 2), `round(${x},2)`).toEqual(r2)
      expect(P.fmt(x, 1), `${x}:.1f`).toBe(f1)
      expect(P.fmt(x, 0), `${x}:.0f`).toBe(f0)
      expect(P.fmt_signed(x, 1), `${x}:+.1f`).toBe(s1)
      expect(P.g(x), `${x}:g`).toBe(gg)
      expect(P.pystr(P.pyround(x, 1)), `repr round(${x},1)`).toBe(rp)
    }
    expect(P.g(1234567.0)).toBe('1.23457e+06')
    expect(P.g(0.0001234)).toBe('0.0001234')
    expect(P.g(28.0)).toBe('28')
    expect(P.pysum(Array(10).fill(0.1))).toBe(1.0)
    expect(P.pysum([1e16, 1.0, -1e16])).toBe(1.0)
    expect(P.fmt_signed(0)).toBe('+0')
  })
})

describe.skipIf(!E)('views parity (기대값 파일이 있을 때만)', () => {
  beforeAll(async () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(`${E.today}T12:00:00`))
    const store = await import('../store/db')
    activeJobs = store.activeJobs
    acct = store.db.accounts.demo
    V = await import('./views')
  })
  afterAll(() => vi.useRealTimers())

  it('ROM_REF·MEDIAN_SPEED', () => {
    expect(V.ROM_REF).toEqual(E.ROM_REF)
    expect(V.MEDIAN_SPEED).toEqual(E.MEDIAN_SPEED)
  })

  it('home_view', () => {
    for (const h of E.home) {
      const [view, q, dog, by, changed, stage, page] = h.args
      expect(plain(V.home_view(acct, view, q, dog, by, changed, stage, page)), JSON.stringify(h.args)).toEqual(h.out)
    }
  })

  it('today_rows·analysis_rows·staff_rows', () => {
    expect(plain(V.today_rows(acct, acct.dogs))).toEqual(E.today_rows)
    expect(plain(V.analysis_rows(acct, acct.results))).toEqual(E.analysis_rows)
    expect(plain(V.staff_rows(acct, acct.results))).toEqual(E.staff_rows)
  })

  it('반려견별', () => {
    const live = new Set(activeJobs(acct).map((j) => j.dog))
    expect(Object.keys(E.dogs)).toEqual(acct.dogs.map((d) => d.id))
    for (const d of acct.dogs) {
      const e = E.dogs[d.id]
      const got = {
        patient_row: V.patient_row(acct, d, live), dog_detail: V.dog_detail(acct, d),
        visits: V.visits(acct, d), dx_history: V.dx_history(acct, d), memos: V.memos(d),
        memo_panel: V.memo_panel(acct, d, acct.results.find((r) => r.dog === d.id)?.id ?? ''),
        soap_entries: V.soap_entries(d, acct), note_rows: V.note_rows(d, acct), vital_rows: V.vital_rows(d),
        kg_trend: V.kg_trend(d), chart_summary: V.chart_summary(acct, d), care_team: V.care_team(acct, d),
        image_list: V.image_list(d), dog_text: V.dog_text(d), compare: V.compare_view(acct, d, 'prev', 'rom'),
      }
      for (const k of Object.keys(e)) expect(plain(got[k as keyof typeof got]), `${d.id}.${k}`).toEqual(e[k])
    }
  })

  it('compare_view 모드·추이', () => {
    for (const id of CMP_DOGS) {
      const d = acct.dogs.find((x) => x.id === id)!
      for (const mode of ['base', 'prev'])
        for (const tk of ['rom', 'stride', 'stance', 'sym', 'zzz'])
          expect(plain(V.compare_view(acct, d, mode, tk)), `${id} ${mode}/${tk}`).toEqual(E.compare[id][`${mode}/${tk}`])
    }
  })

  it('회차별 result_view·body_map·best_view·knee_chart', () => {
    expect(Object.keys(E.results)).toEqual(acct.results.map((r) => r.id))
    for (const r of acct.results) {
      const e = E.results[r.id]
      expect(plain(V.result_view(acct, r)), `${r.id} trot`).toEqual(e.trot)
      expect(plain(V.result_view(acct, r, 'walk')), `${r.id} walk`).toEqual(e.walk)
      expect(plain(V.result_view(acct, r, 'walk', true)), `${r.id} home`).toEqual(e.home)
      expect(plain(V.sym_view(acct, r)), `${r.id} sym_view`).toEqual(e.sym_view)
      if (r.st !== 'fail') {
        const bm = V.body_map(acct, r)
        expect(plain(V.best_view(bm)), `${r.id} best_view`).toEqual(e.best_view)
        const { svg, ...rest } = bm
        expect(plain(SVG_FULL.has(r.id) ? bm : rest), `${r.id} body_map`).toEqual(e.body_map)
        void svg
      }
    }
  })
})
