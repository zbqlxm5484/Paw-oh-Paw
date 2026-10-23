/**
 * MSW 핸들러. api-spec v1.0 의 로그인·반려견·이력 API 만 흉내 낸다(이식 0~3단계).
 * 오류 모양 `{error: {code, message, detail}}` 과 상태 코드는 명세와 같게 둔다.
 */
import { HttpResponse, delay, http } from 'msw'

import type { DogCreate, DogUpdate, LoginIn } from '../api/types'
import { MOCK_STAFF, classifySize, dogs, historyOf, newId, sessions, toDogOut } from './db'

const BASE = '/api/v1'
const TOKEN = 'mock-token'

function err(status: number, code: string, message: string, detail: Record<string, unknown> | null = null) {
  return HttpResponse.json({ error: { code, message, detail } }, { status })
}

function authed(req: Request) {
  return req.headers.get('authorization') === `Bearer ${TOKEN}`
}

const unauthorized = () => err(401, 'AUTH_REQUIRED', '로그인이 필요합니다.')

/** 422 VALIDATION_ERROR 를 명세 모양으로 */
function validate(body: Partial<DogCreate>, partial: boolean) {
  const fields: { field: string; type: string }[] = []
  const has = (k: keyof DogCreate) => Object.prototype.hasOwnProperty.call(body, k)
  if (!partial || has('name')) {
    if (!body.name || !String(body.name).trim()) fields.push({ field: 'name', type: 'missing' })
    else if (String(body.name).length > 50) fields.push({ field: 'name', type: 'string_too_long' })
  }
  if (!partial || has('breed')) {
    if (!body.breed || !String(body.breed).trim()) fields.push({ field: 'breed', type: 'missing' })
  }
  if (!partial || has('weight_kg')) {
    const w = Number(body.weight_kg)
    if (!Number.isFinite(w)) fields.push({ field: 'weight_kg', type: 'missing' })
    else if (w < 0.5) fields.push({ field: 'weight_kg', type: 'greater_than_equal' })
    else if (w > 100) fields.push({ field: 'weight_kg', type: 'less_than_equal' })
  }
  if (body.birth_year != null) {
    const y = Number(body.birth_year)
    if (!Number.isInteger(y) || y < 1990 || y > 2026) fields.push({ field: 'birth_year', type: 'value_error' })
  }
  if (body.rehab_start_date && body.rehab_start_date > '2026-10-22') fields.push({ field: 'rehab_start_date', type: 'value_error' })
  return fields
}

export const handlers = [
  http.get(`${BASE}/health`, () => HttpResponse.json({ status: 'ok', db: 'ok', storage: 'ok', version: 'mock' })),

  // ---------- 인증 ----------
  http.post(`${BASE}/auth/login`, async ({ request }) => {
    await delay(400)
    const body = (await request.json()) as LoginIn
    if (!body.institution_code || !body.login_id || !body.password) {
      return err(422, 'VALIDATION_ERROR', '입력값을 확인해 주세요.', {
        fields: ['institution_code', 'login_id', 'password'].filter((k) => !body[k as keyof LoginIn]).map((field) => ({ field, type: 'missing' })),
      })
    }
    // 가짜 규칙: 비밀번호가 "wrong" 이면 실패, "disabled" 면 중지 계정. 그 밖에는 모두 통과
    if (body.password === 'wrong') return err(401, 'LOGIN_FAILED', '기관 코드, 아이디 또는 비밀번호가 맞지 않습니다.')
    if (body.password === 'disabled') return err(403, 'ACCOUNT_DISABLED', '사용이 중지된 계정입니다.')
    const staff = { ...MOCK_STAFF, login_id: body.login_id, institution: { ...MOCK_STAFF.institution, code: body.institution_code } }
    return HttpResponse.json({
      access_token: TOKEN,
      token_type: 'bearer',
      expires_at: new Date(Date.now() + 12 * 3600 * 1000).toISOString(),
      staff,
    })
  }),

  http.get(`${BASE}/auth/me`, ({ request }) => {
    if (!authed(request)) return unauthorized()
    return HttpResponse.json(MOCK_STAFF)
  }),

  // ---------- 반려견 ----------
  http.get(`${BASE}/dogs`, async ({ request }) => {
    if (!authed(request)) return unauthorized()
    await delay(250)
    const url = new URL(request.url)
    const q = (url.searchParams.get('q') ?? '').trim().toLowerCase()
    const page = Math.max(1, Number(url.searchParams.get('page') ?? 1))
    const size = Math.min(100, Math.max(1, Number(url.searchParams.get('size') ?? 20)))
    let items = dogs.map(toDogOut)
    if (q) items = items.filter((d) => d.name.toLowerCase().includes(q))
    // 최근 측정일 늦은 순, 안 잰 반려견은 뒤, 같으면 등록이 늦은 순
    items.sort((a, b) => {
      if (a.last_measured_on && b.last_measured_on) return b.last_measured_on.localeCompare(a.last_measured_on)
      if (a.last_measured_on) return -1
      if (b.last_measured_on) return 1
      return b.created_at.localeCompare(a.created_at)
    })
    const total = items.length
    items = items.slice((page - 1) * size, page * size)
    return HttpResponse.json({ items, total, page, size })
  }),

  http.post(`${BASE}/dogs`, async ({ request }) => {
    if (!authed(request)) return unauthorized()
    await delay(350)
    const body = (await request.json()) as DogCreate
    const fields = validate(body, false)
    if (fields.length) return err(422, 'VALIDATION_ERROR', '입력값을 확인해 주세요.', { fields })
    const ts = new Date().toISOString()
    const weight = Number(body.weight_kg)
    const row = {
      id: newId(),
      name: body.name.trim(),
      breed: body.breed.trim(),
      weight_kg: weight,
      size_class: body.size_class ?? classifySize(weight),
      size_class_manual: !!body.size_class,
      birth_year: body.birth_year ?? null,
      sex: body.sex ?? null,
      rehab_start_date: body.rehab_start_date ?? null,
      focus_limb: body.focus_limb ?? null,
      baseline_session_id: null,
      memo: body.memo?.trim() || null,
      created_at: ts,
      updated_at: ts,
    }
    dogs.push(row)
    return HttpResponse.json(toDogOut(row), { status: 201 })
  }),

  http.get(`${BASE}/dogs/:dogId`, ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    const row = dogs.find((d) => d.id === params.dogId)
    if (!row) return err(404, 'NOT_FOUND', '요청한 정보를 찾을 수 없습니다.')
    return HttpResponse.json(toDogOut(row))
  }),

  http.patch(`${BASE}/dogs/:dogId`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(300)
    const row = dogs.find((d) => d.id === params.dogId)
    if (!row) return err(404, 'NOT_FOUND', '요청한 정보를 찾을 수 없습니다.')
    const body = (await request.json()) as DogUpdate
    const fields = validate(body, true)
    if (fields.length) return err(422, 'VALIDATION_ERROR', '입력값을 확인해 주세요.', { fields })

    if ('baseline_session_id' in body) {
      if (body.baseline_session_id != null) {
        const s = sessions.find((x) => x.id === body.baseline_session_id && x.dog_id === row.id)
        if (!s || s.status !== 'DONE') return err(400, 'BASELINE_INVALID', '기준 회차는 이 반려견의 완료된 회차여야 합니다.')
      }
      row.baseline_session_id = body.baseline_session_id ?? null
    }
    if (body.name !== undefined) row.name = String(body.name).trim()
    if (body.weight_kg !== undefined) row.weight_kg = Number(body.weight_kg)
    if (body.breed !== undefined) row.breed = String(body.breed).trim()
    if (body.birth_year !== undefined) row.birth_year = body.birth_year
    if (body.sex !== undefined) row.sex = body.sex ?? null
    if (body.rehab_start_date !== undefined) row.rehab_start_date = body.rehab_start_date ?? null
    if (body.focus_limb !== undefined) row.focus_limb = body.focus_limb ?? null
    if (body.memo !== undefined) row.memo = body.memo?.trim() || null
    // 체급: 값을 보내면 직접 지정, null 이면 자동으로 돌아감. 안 보내면 그대로(체중만 바꿔도 그대로, 명세 5절)
    if ('size_class' in body) {
      if (body.size_class) {
        row.size_class = body.size_class
        row.size_class_manual = true
      } else {
        row.size_class = classifySize(row.weight_kg)
        row.size_class_manual = false
      }
    }
    row.updated_at = new Date().toISOString()
    return HttpResponse.json(toDogOut(row))
  }),

  // ---------- 이력 ----------
  http.get(`${BASE}/dogs/:dogId/sessions`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(250)
    const row = dogs.find((d) => d.id === params.dogId)
    if (!row) return err(404, 'NOT_FOUND', '요청한 정보를 찾을 수 없습니다.')
    const items = historyOf(row.id)
    return HttpResponse.json({ items, total: items.length, page: 1, size: 100 })
  }),
]
