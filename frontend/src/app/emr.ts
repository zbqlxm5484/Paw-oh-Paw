/**
 * 반려견 진료 정보(바이탈·진단·수술). 웹(web/src/store)과 같은 모양.
 * 백엔드에 아직 이 API 가 없어서(웹도 브라우저 저장소에만 둔다) 실제 계정은 빈 값이고, 체중만 서버 값을 쓴다.
 * 체험 모드·가짜 서버에서는 웹 시연 데이터(web/src/mocks/fixture.json)의 같은 이름 반려견 값을 보인다(src/mocks/emrDemo.json).
 */
import demo from '../mocks/emrDemo.json'
import { isDemo } from './demoMode'

export interface Vital { day: string; kg: string; temp: string; hr: string; sbp: string; dbp: string; author: string }
export interface Hist { day: string; kind: string; title: string; site: string; by: string }
export interface Emr { vitals: Vital[]; history: Hist[] }

const EMPTY: Emr = { vitals: [], history: [] }
const MOCK = !!import.meta.env.VITE_MOCK && import.meta.env.VITE_MOCK !== '0'
export const SITE: Record<string, string> = { LF: '왼앞', RF: '오른앞', LH: '왼뒤', RH: '오른뒤', SP: '척추' }

/** 반려견 이름으로 진료 정보. 바이탈은 최신이 앞, 이력은 오래된 것이 앞 */
export function emrOf(name: string): Emr {
  if (!isDemo() && !MOCK) return EMPTY
  return (demo as Record<string, Emr>)[name] ?? EMPTY
}

const head = (t: string) => t.replace(/\s*\(.*\)\s*$/, '')
const daysAgo = (iso: string) => Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 86400000))

/** 홈 목록에 띄울 특이사항: 최근 수술(D+일), 그 뒤 최근 진단. 웹 views.badges 와 같은 규칙 */
export function badgesOf(e: Emr): { t: string; kind: 'surg' | 'diag' }[] {
  const out: { t: string; kind: 'surg' | 'diag' }[] = []
  const last = (k: string) => [...e.history].reverse().find((h) => h.kind === k)
  const surg = last('수술'), diag = last('진단')
  if (surg) out.push({ t: `${head(surg.title)} · ${SITE[surg.site] ?? ''} · D+${daysAgo(surg.day)}`.replace(' ·  ·', ' ·'), kind: 'surg' })
  if (diag) out.push({ t: `${head(diag.title)}${SITE[diag.site] ? ` · ${SITE[diag.site]}` : ''}`, kind: 'diag' })
  return out
}
