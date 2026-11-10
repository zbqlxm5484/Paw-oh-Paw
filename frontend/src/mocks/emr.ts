/**
 * 가짜 서버의 진료 정보(바이탈·진단/수술 이력). 백엔드(11-09 조영운) API 모양 그대로 돌려준다.
 * 값은 웹 시연 데이터(web/src/mocks/fixture.json)에서 같은 이름 반려견 것을 옮긴 emrDemo.json.
 */
import type { DogHistoryOut, HistoryKind, HistorySite, HistorySummary, VitalOut } from '../api/types'
import demo from './emrDemo.json'

type DemoVital = { day: string; kg: string; temp: string; hr: string; sbp: string; dbp: string; author: string }
type DemoHist = { day: string; kind: string; title: string; site: string; by: string }
const DEMO = demo as Record<string, { vitals: DemoVital[]; history: DemoHist[] }>
const KIND: Record<string, HistoryKind> = { 진단: 'DIAGNOSIS', 수술: 'SURGERY', 재활: 'REHAB' }
const num = (s: string) => (s && !Number.isNaN(Number(s)) ? Number(s) : null)
const site = (s: string): HistorySite | null => (['LF', 'RF', 'LH', 'RH', 'SP'].includes(s) ? (s as HistorySite) : null)
const staff = (name: string) => (name ? { id: `staff-${name}`, name } : null)

/** 최신 날짜가 앞 */
export function emrVitals(dogId: string, dogName: string): VitalOut[] {
  return (DEMO[dogName]?.vitals ?? []).map((v, i) => ({
    id: `${dogId}-v${i}`, measured_on: v.day, weight_kg: num(v.kg), temp_c: num(v.temp), heart_rate: num(v.hr), sbp: num(v.sbp), dbp: num(v.dbp),
    staff: staff(v.author), session_id: null, created_at: `${v.day}T09:00:00+09:00`, updated_at: `${v.day}T09:00:00+09:00`,
  }))
}

/** 오래된 것부터 */
export function emrHistory(dogId: string, dogName: string): DogHistoryOut[] {
  return (DEMO[dogName]?.history ?? []).map((h, i) => ({
    id: `${dogId}-h${i}`, occurred_on: h.day, kind: KIND[h.kind] ?? 'DIAGNOSIS', title: h.title, site: site(h.site),
    clinician: h.by || null, staff: staff(h.by), created_at: `${h.day}T09:00:00+09:00`,
  }))
}

/** DogOut 에 붙는 요약: latest_vital·last_surgery·last_diagnosis */
export function emrSummary(dogId: string, dogName: string) {
  const v = emrVitals(dogId, dogName)[0] ?? null
  const hs = emrHistory(dogId, dogName)
  const last = (k: HistoryKind): HistorySummary | null => {
    const h = [...hs].reverse().find((x) => x.kind === k)
    return h ? { occurred_on: h.occurred_on, title: h.title, site: h.site } : null
  }
  return { latest_vital: v, last_surgery: last('SURGERY'), last_diagnosis: last('DIAGNOSIS') }
}
