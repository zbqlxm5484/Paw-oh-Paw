/**
 * MSW 핸들러. api-spec v1.0(명세 v1.5) 의 로그인·반려견·이력·회차 측정 API 를 흉내 낸다(이식 0~5단계).
 * 오류 모양 `{error: {code, message, detail}}` 과 상태 코드는 명세와 같게 둔다.
 */
import { HttpResponse, delay, http } from 'msw'

import type { DogCreate, DogUpdate, LoginIn, SessionCreate } from '../api/types'
import { MOCK_STAFF, classifySize, dogs, findDog, historyOf, newId, reason, sessions, simulateAggregation, simulateAnalysis, toDogOut, toSessionDetail, toSessionOut, type MockShot } from './db'

const BASE = '/api/v1'
const TOKEN = 'mock-token'
const TODAY = () => new Date().toISOString().slice(0, 10)

function err(status: number, code: string, message: string, detail: Record<string, unknown> | null = null) {
  return HttpResponse.json({ error: { code, message, detail } }, { status })
}

function authed(req: Request) {
  return req.headers.get('authorization') === `Bearer ${TOKEN}`
}

const unauthorized = () => err(401, 'AUTH_REQUIRED', '로그인이 필요합니다.')
const notFound = () => err(404, 'NOT_FOUND', '요청한 정보를 찾을 수 없습니다.')

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
  if (body.rehab_start_date && body.rehab_start_date > TODAY()) fields.push({ field: 'rehab_start_date', type: 'value_error' })
  return fields
}

function findSession(id: string | readonly string[] | undefined) {
  return sessions.find((s) => s.id === id)
}
function findShot(id: string | readonly string[] | undefined) {
  for (const s of sessions) {
    const sh = s.shots.find((x) => x.id === id)
    if (sh) return { session: s, shot: sh }
  }
  return null
}
const inProgress = (st: MockShot['status']) => st === 'SUBMITTED' || st === 'ANALYZING'

export const handlers = [
  http.get(`${BASE}/health`, () => HttpResponse.json({ status: 'ok', db: 'ok', storage: 'ok', version: 'mock' })),

  // ---------- 인증 ----------
  http.post(`${BASE}/auth/login`, async ({ request }) => {
    await delay(400)
    const body = (await request.json()) as LoginIn
    if (!body.login_id || !body.password) {
      return err(422, 'VALIDATION_ERROR', '입력값을 확인해 주세요.', {
        fields: ['login_id', 'password'].filter((k) => !body[k as keyof LoginIn]).map((field) => ({ field, type: 'missing' })),
      })
    }
    // 가짜 규칙: 비밀번호가 "wrong" 이면 실패, "disabled" 면 중지 계정. 그 밖에는 모두 통과
    if (body.password === 'wrong') return err(401, 'LOGIN_FAILED', '아이디 또는 비밀번호가 맞지 않습니다.')
    if (body.password === 'disabled') return err(403, 'ACCOUNT_DISABLED', '사용이 중지된 계정입니다.')
    const staff = { ...MOCK_STAFF, login_id: body.login_id }   // 기관은 계정에 묶여 있어 로그인 본문에 없다(인증 설계 v0.3)
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
      version: 0,
      created_at: ts,
      updated_at: ts,
    }
    dogs.push(row)
    return HttpResponse.json(toDogOut(row), { status: 201 })
  }),

  http.get(`${BASE}/dogs/:dogId`, ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    const row = findDog(params.dogId)
    if (!row) return notFound()
    return HttpResponse.json(toDogOut(row))
  }),

  http.patch(`${BASE}/dogs/:dogId`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(300)
    const row = findDog(params.dogId)
    if (!row) return notFound()
    const body = (await request.json()) as DogUpdate
    const fields = validate(body, true)
    // 낙관적 잠금(백엔드 15.5 BE-25): version 은 필수, 저장된 값과 다르면 아무것도 바꾸지 않고 409
    if (typeof body.version !== 'number') fields.push({ field: 'version', type: 'missing' })
    if (fields.length) return err(422, 'VALIDATION_ERROR', '입력값을 확인해 주세요.', { fields })
    if (body.version !== row.version) return err(409, 'DOG_MODIFIED', '다른 담당자가 먼저 수정했습니다. 다시 불러온 뒤 시도해 주세요.')

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
    row.version += 1
    row.updated_at = new Date().toISOString()
    return HttpResponse.json(toDogOut(row))
  }),

  // ---------- 이력 ----------
  http.get(`${BASE}/dogs/:dogId/sessions`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(250)
    const row = findDog(params.dogId)
    if (!row) return notFound()
    const items = historyOf(row.id)
    return HttpResponse.json({ items, total: items.length, page: 1, size: 100 })
  }),

  // ---------- 회차 측정 (api-spec 6절) ----------
  http.post(`${BASE}/dogs/:dogId/sessions`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(350)
    const dog = findDog(params.dogId)
    if (!dog) return notFound()
    // 본문은 한 번만 읽는다(빈 본문도 허용)
    const raw = await request.text().catch(() => '')
    const data = (raw ? (JSON.parse(raw) as SessionCreate) : {}) ?? {}
    const open = sessions.find((s) => s.dog_id === dog.id && s.status === 'MEASURING')
    if (open) return err(409, 'SESSION_ALREADY_OPEN', '이 반려견은 이미 측정 중인 회차가 있습니다.', { session_id: open.id })
    const measured_on = data.measured_on ?? TODAY()
    if (measured_on > TODAY()) return err(422, 'VALIDATION_ERROR', '입력값을 확인해 주세요.', { fields: [{ field: 'measured_on', type: 'value_error' }] })
    const w = data.weight_kg == null ? null : Number(data.weight_kg)
    if (w != null && (!Number.isFinite(w) || w < 0.5 || w > 100)) return err(422, 'VALIDATION_ERROR', '입력값을 확인해 주세요.', { fields: [{ field: 'weight_kg', type: 'value_error' }] })
    const s = {
      id: newId(), dog_id: dog.id, staff: { id: MOCK_STAFF.id, name: MOCK_STAFF.name }, measured_on, weight_kg: w,
      // 회차 체급: 그날 체중(없으면 등록 체중), 직접 지정한 체급이 있으면 그 값(명세 v1.5)
      size_class: dog.size_class_manual ? dog.size_class : classifySize(w ?? dog.weight_kg),
      status: 'MEASURING' as const, fail_reason: null, model_name: null, model_version: null, completed_at: null, aggregated_at: null,
      created_at: new Date().toISOString(), shots: [] as MockShot[], reports: null,
    }
    sessions.push(s)
    return HttpResponse.json(toSessionOut(s), { status: 201 })
  }),

  http.get(`${BASE}/sessions/:sessionId`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(150)
    const s = findSession(params.sessionId)
    if (!s) return notFound()
    return HttpResponse.json(toSessionDetail(s))
  }),

  http.delete(`${BASE}/sessions/:sessionId`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(300)
    const s = findSession(params.sessionId)
    if (!s) return notFound()
    if (s.status !== 'MEASURING') return err(409, 'SESSION_CLOSED', '측정이 끝난 회차입니다.')
    if (s.shots.some((sh) => inProgress(sh.status))) return err(409, 'SHOT_IN_PROGRESS', '분석 중인 촬영이 있어 지금은 지울 수 없습니다. 분석이 끝난 뒤 다시 시도해 주세요.')
    sessions.splice(sessions.indexOf(s), 1)
    return new HttpResponse(null, { status: 204 })
  }),

  http.post(`${BASE}/sessions/:sessionId/shots`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    const s = findSession(params.sessionId)
    if (!s) return notFound()
    if (s.status !== 'MEASURING') return err(409, 'SESSION_CLOSED', '측정이 끝난 회차입니다.')
    const form = await request.formData().catch(() => null)
    const file = form?.get('file')
    if (!(file instanceof File)) return err(422, 'VALIDATION_ERROR', '입력값을 확인해 주세요.', { fields: [{ field: 'file', type: 'missing' }] })
    const name = file.name.toLowerCase()
    // 13.1 검사 흉내: 확장자, 크기, 이름에 portrait 가 들어 있으면 세로 영상
    if (!/\.(mp4|mov)$/.test(name) && !file.type.startsWith('video/')) return err(400, 'VIDEO_FORMAT', 'MP4 또는 MOV 영상만 올릴 수 있습니다.')
    if (file.size > 100 * 1024 * 1024) return err(413, 'VIDEO_TOO_LARGE', '영상 파일이 너무 큽니다. 최대 100 MB까지 올릴 수 있습니다.', { max_mb: 100 })
    if (name.includes('portrait')) return err(400, 'VIDEO_PORTRAIT', '가로로 촬영한 영상만 올릴 수 있습니다.', { width: 1080, height: 1920 })
    await delay(900)
    const seq = (s.shots.reduce((m, x) => Math.max(m, x.seq_no), 0) || 0) + 1
    const below = name.includes('low')
    const shot: MockShot = {
      session_id: s.id, id: newId(), seq_no: seq, status: 'UPLOADED', fail_reason: null, validity: null, validity_reason: null,
      video_status: 'PENDING', below_min_spec: below, passes: [], uploaded_at: new Date().toISOString(), analyzed_at: null,
    }
    s.shots.push(shot)
    simulateAnalysis(shot, file.name)
    const { session_id: _sid, ...out } = shot
    return HttpResponse.json({ ...out, warnings: below ? [reason('BELOW_MIN_SPEC')] : [] }, { status: 201 })
  }),

  http.post(`${BASE}/sessions/:sessionId/complete`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(300)
    const s = findSession(params.sessionId)
    if (!s) return notFound()
    if (s.status !== 'MEASURING') return err(409, 'SESSION_CLOSED', '측정이 끝난 회차입니다.')
    if (!s.shots.length) return err(409, 'SESSION_EMPTY', '촬영이 1건 이상 있어야 측정을 끝낼 수 있습니다.')
    s.status = 'AGGREGATING'
    s.completed_at = new Date().toISOString()
    simulateAggregation(s)
    return HttpResponse.json(toSessionOut(s))
  }),

  http.post(`${BASE}/shots/:shotId/retry`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(300)
    const found = findShot(params.shotId)
    if (!found) return notFound()
    const { session, shot } = found
    if (shot.status !== 'FAILED') return err(409, 'SHOT_NOT_FAILED', '실패한 촬영만 다시 분석할 수 있습니다.')
    if (session.status !== 'MEASURING') return err(409, 'SESSION_CLOSED', '측정이 끝난 회차입니다.')
    shot.status = 'UPLOADED'
    shot.fail_reason = null
    simulateAnalysis(shot, 'retry.mp4')
    const { session_id: _sid, ...out } = shot
    return HttpResponse.json(out)
  }),

  http.delete(`${BASE}/shots/:shotId`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(300)
    const found = findShot(params.shotId)
    if (!found) return notFound()
    const { session, shot } = found
    if (session.status !== 'MEASURING') return err(409, 'SESSION_CLOSED', '측정이 끝난 회차입니다.')
    if (inProgress(shot.status)) return err(409, 'SHOT_IN_PROGRESS', '분석 중인 촬영이 있어 지금은 지울 수 없습니다. 분석이 끝난 뒤 다시 시도해 주세요.')
    session.shots.splice(session.shots.indexOf(shot), 1)
    return new HttpResponse(null, { status: 204 })
  }),
]
