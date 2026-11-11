import { describe, expect, it } from 'vitest'

import type { DogOut } from '../api/client'
import { badges, changes, diagnosis, patient_row } from '../views/views'
import { toDog } from './backend'
import { isoToday } from './db'
import type { Account, Dog, Result } from './types'

const daysBefore = (n: number) => {
  const t = new Date()
  t.setDate(t.getDate() - n)
  return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`
}

function out(over: Partial<DogOut> = {}): DogOut {
  return {
    id: 'd1', name: '보리', breed: '골든 리트리버', weight_kg: 28.4, size_class: 'LARGE', size_class_manual: false, birth_year: 2019,
    sex: 'FEMALE_SPAYED', rehab_start_date: null, focus_limb: 'RH', baseline_session_id: null, memo: null, version: 2,
    session_count: 0, last_measured_on: null, open_session_id: null, created_at: '', updated_at: '', ...over,
  }
}

const acct = (dogs: Dog[], results: Result[] = []): Account => ({
  id: 'i1', login_id: '', password: '', name: '기관', loc: '', dev: '', joined: '', dogs, results, jobs: [], notif_on: true, code: '', contract_ends: null,
})

describe('toDog: 271 칸', () => {
  it('동물번호·보호자·단계를 옮기고, 목록의 연락처는 뒤 4자리만 둔다', () => {
    const d = toDog(out({ chart_no: 'A-1024', owner_name: '김보호', owner_phone: null, owner_phone_last4: '5678', stage: 'PRE', stage_changed_on: '2026-11-01' }))
    expect([d.no, d.owner, d.phone, d.phone4, d.stage, d.stage_day]).toEqual(['A-1024', '김보호', '', '5678', 'pre', '2026-11-01'])
  })
  it('상세에서 읽은 전체 번호는 목록으로 다시 읽어도(뒤 4자리가 같으면) 남는다', () => {
    const full = toDog(out({ owner_phone: '010-1234-5678', owner_phone_last4: '5678' }))
    const again = toDog(out({ owner_phone: null, owner_phone_last4: '5678' }), full)
    expect(again.phone).toBe('010-1234-5678')
  })
  it('예전 서버(칸 없음)면 이 브라우저 값을 그대로 둔다', () => {
    const prev = { ...toDog(out()), no: 'X-1', owner: '이보호', stage: 'done' }
    const d = toDog(out(), prev)
    expect([d.no, d.owner, d.stage, d.srv]).toEqual(['X-1', '이보호', 'done', undefined])
  })
  it('차트를 읽기 전에는 목록의 최근 바이탈 한 줄을 보인다', () => {
    const d = toDog(out({ latest_vital: { id: 'v', measured_on: '2026-11-06', weight_kg: 28.1, temp_c: 38.6, heart_rate: 92, sbp: 132, dbp: 84, staff: { id: 's', name: '김담당' }, session_id: null, created_at: '', updated_at: '' } }))
    expect(d.vitals).toEqual([{ day: '2026-11-06', kg: '28.1', temp: '38.6', hr: '92', sbp: '132', dbp: '84', author: '김담당' }])
  })
})

describe('홈 배지·변동: 서버 값이 있으면 그것으로', () => {
  it('배지: 수술은 부위·D+일', () => {
    const d = toDog(out({ badges: [{ code: 'SURGERY', title: 'TPLO (경골 고원 수평화 절골술)', site: 'RH', on: daysBefore(71) }, { code: 'IMPORTANT_NOTE', title: null, site: null, on: isoToday() }], changes: [] }))
    expect(badges(d)).toEqual([{ t: 'TPLO · 오른뒤 · D+71', kind: 'surg' }])
  })
  it('변동: 재촬영은 가장 최근 회차가 실패면 재촬영 필요, 보행 점수 차는 서버 delta', () => {
    const d = toDog(out({ changes: [{ code: 'RESHOOT_NEEDED', on: daysBefore(1), delta: null }, { code: 'GAIT_WORSE', on: daysBefore(1), delta: -4 }, { code: 'IMPORTANT_NOTE', on: daysBefore(3), delta: null }], badges: [] }))
    const fail = { id: 'r1', dog: 'd1', day: daysBefore(1), st: 'fail' } as Result
    const [ch, last] = changes(acct([d], [fail]), d)
    expect(ch.map((c) => [c.t, c.tone])).toEqual([['재촬영 필요', 'bad'], ['보행 나빠짐 −4점', 'bad'], ['중요 메모', 'warn']])
    expect(last).toBe(daysBefore(1))
    const part = { ...fail, st: 'part' }
    expect(changes(acct([d], [part]), d)[0][0].t).toBe('일부 유효 · 재촬영 권장')
  })
  it('예전 서버면 이 브라우저 기록으로 계산한다', () => {
    const d = { ...toDog(out()), history: [{ day: daysBefore(2), kind: '수술', title: 'TPLO', site: 'RH', by: '', author: '' }] }
    expect(changes(acct([d]), d)[0].map((c) => c.t)).toEqual(['수술 등록'])
  })
  it('병명 칸·연락처 뒤 4자리는 차트를 열기 전에도 보인다', () => {
    const d = toDog(out({ owner_phone_last4: '5678', last_diagnosis: { occurred_on: '2026-08-14', title: '앞십자인대 파열 (CCL)', site: 'RH' }, badges: [], changes: [] }))
    expect(diagnosis(d)).toBe('앞십자인대 파열')
    expect(patient_row(acct([d]), d, new Set()).phone4).toBe('5678')
  })
})
