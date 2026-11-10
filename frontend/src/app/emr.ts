/**
 * 반려견 진료 정보(바이탈·진단/수술 이력). 백엔드 API(11-09 조영운):
 * - 목록 요약: DogOut.latest_vital·last_surgery·last_diagnosis (홈 목록의 수술·진단 줄, 검색)
 * - 상세: GET /dogs/{id}/vitals(최신 날짜가 앞)·/dogs/{id}/history(오래된 것부터) (반려견 차트의 바이탈·진단·수술 카드)
 * 서버에 아직 API 가 없으면 빈 값으로 보인다(api/dogs.ts orEmpty). 체험 모드는 가짜 서버(mocks/emr.ts)가 같은 모양으로 준다.
 */
import { useDogHistory, useDogVitals } from '../api/dogs'
import type { DogHistoryOut, DogOut, HistorySummary, VitalOut } from '../api/types'

export const SITE: Record<string, string> = { LF: '왼앞', RF: '오른앞', LH: '왼뒤', RH: '오른뒤', SP: '척추' }
const KIND: Record<string, string> = { DIAGNOSIS: '진단', SURGERY: '수술', REHAB: '재활' }
const head = (t: string) => t.replace(/\s*\(.*\)\s*$/, '')
const daysAgo = (iso: string) => Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 86400000))
const fmt = (iso: string) => { const p = (iso || '').split('-'); return p.length === 3 ? `${p[0]}년 ${+p[1]}월 ${+p[2]}일` : iso }
const siteOf = (h: HistorySummary) => (h.site ? SITE[h.site] ?? '' : '')

/** 홈 목록에 띄울 특이사항: 최근 수술(부위·D+일), 최근 진단(부위). 웹 views.badges 와 같은 규칙 */
export function badgesOfDog(o: DogOut | undefined): { t: string; kind: 'surg' | 'diag' }[] {
  const out: { t: string; kind: 'surg' | 'diag' }[] = []
  const s = o?.last_surgery, d = o?.last_diagnosis
  if (s) out.push({ t: [head(s.title), siteOf(s), `D+${daysAgo(s.occurred_on)}`].filter(Boolean).join(' · '), kind: 'surg' })
  if (d) out.push({ t: [head(d.title), siteOf(d)].filter(Boolean).join(' · '), kind: 'diag' })
  return out
}

/** 검색 대상에 넣을 병명·수술명(목록 요약에 있는 것) */
export const emrSearchText = (o: DogOut | undefined) => [o?.last_surgery?.title, o?.last_diagnosis?.title].filter(Boolean).join(' ')

export interface VitView {
  cells: { k: string; v: string; sub?: string }[]
  when: string
  note: string
  hist: { id: string; day: string; kind: string; title: string; site: string; by: string }[]
}

/** 반려견 차트의 바이탈·진단/수술 카드 값. 체중은 반려견 체중(서버가 최근 바이탈 체중으로 맞춘다) */
export function vitView(vitals: VitalOut[], history: DogHistoryOut[], dogKg: string): VitView {
  const v = vitals[0]
  const kg = dogKg && dogKg !== '0' ? dogKg : v?.weight_kg != null ? String(v.weight_kg) : ''
  const has = !!v && (v.temp_c != null || v.heart_rate != null || v.sbp != null)
  return {
    cells: [
      { k: '체중', v: kg ? `${kg}kg` : '—' },
      { k: '체온', v: v?.temp_c != null ? `${v.temp_c}℃` : '—' },
      { k: '심박', v: v?.heart_rate != null ? `${v.heart_rate}회/분` : '—' },
      { k: '혈압', v: v?.sbp != null ? `${v.sbp}/${v.dbp ?? '—'}` : '—', sub: v?.sbp != null ? 'mmHg' : '' },
    ],
    when: v ? [fmt(v.measured_on), v.staff?.name].filter(Boolean).join(' · ') : '',
    note: has ? '' : '체온·심박·혈압은 아직 기록이 없습니다',
    hist: [...history].reverse().map((h) => ({ id: h.id, day: fmt(h.occurred_on), kind: KIND[h.kind] ?? h.kind, title: h.title, site: h.site ? SITE[h.site] ?? '' : '', by: h.clinician ?? '' })),
  }
}

/** 반려견 차트에서 부르는 훅: 바이탈·이력을 읽어 카드 값으로 */
export function useVitView(dogId: string | undefined, dogKg: string): VitView {
  const v = useDogVitals(dogId), h = useDogHistory(dogId)
  return vitView(v.data ?? [], h.data ?? [], dogKg)
}
