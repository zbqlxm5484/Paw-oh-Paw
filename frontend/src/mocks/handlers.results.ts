/** MSW 핸들러 2부: 회차 결과·보고서·촬영 상세·각도·비교·추이 (api-spec 6~8절). */
import { HttpResponse, delay, http } from 'msw'

import type { Edition, ReportOut } from '../api/types'
import { findDog, reason, sessions, type MockSession } from './db'
import { anglesFor, compareFor, resultFor, shotDetailFor, trendsFor } from './metrics'

const BASE = '/api/v1'
const TOKEN = 'mock-token'

function err(status: number, code: string, message: string, detail: Record<string, unknown> | null = null) {
  return HttpResponse.json({ error: { code, message, detail } }, { status })
}
const authed = (req: Request) => req.headers.get('authorization') === `Bearer ${TOKEN}`
const unauthorized = () => err(401, 'AUTH_REQUIRED', '로그인이 필요합니다.')
const notFound = () => err(404, 'NOT_FOUND', '요청한 정보를 찾을 수 없습니다.')

const findSession = (id: string | readonly string[] | undefined) => sessions.find((s) => s.id === id)

function reportOut(s: MockSession, edition: Edition, origin: string): ReportOut {
  const status = s.reports?.[edition] ?? 'PENDING'
  const id = `${s.id}:${edition}`
  const exp = new Date(Date.now() + 5 * 60_000).toISOString()
  const sig = `exp=${Math.floor(Date.parse(exp) / 1000)}&sig=mock`
  return {
    id,
    session_id: s.id,
    edition,
    status,
    fail_reason: status === 'FAILED' ? reason('REPORT_CHECK_FAILED') : null,
    generation_ms: status === 'DONE' ? 8400 : null,
    template_version: '1.0',
    model_version: s.model_version,
    updated_at: s.aggregated_at ?? s.created_at,
    file_url: status === 'DONE' ? `${origin}${BASE}/reports/${id}/file?${sig}` : null,
    download_url: status === 'DONE' ? `${origin}${BASE}/reports/${id}/file?${sig}&download=true` : null,
    url_expires_at: status === 'DONE' ? exp : null,
  }
}

export const resultHandlers = [
  http.get(`${BASE}/sessions/:sessionId/result`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(300)
    const s = findSession(params.sessionId)
    if (!s) return notFound()
    if (s.status !== 'DONE') return err(409, 'SESSION_NOT_DONE', '회차 집계가 끝난 뒤에 할 수 있습니다.')
    return HttpResponse.json(resultFor(s))
  }),

  http.get(`${BASE}/sessions/:sessionId/reports`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(200)
    const s = findSession(params.sessionId)
    if (!s) return notFound()
    const origin = new URL(request.url).origin
    const reports = s.status === 'DONE' && s.reports ? (['OWNER', 'VET'] as Edition[]).map((e) => reportOut(s, e, origin)) : []
    return HttpResponse.json({ session_id: s.id, session_status: s.status, reports })
  }),

  http.post(`${BASE}/reports/:reportId/regenerate`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(300)
    const [sid, edition] = String(params.reportId).split(':') as [string, Edition]
    const s = findSession(sid)
    if (!s || !s.reports || !edition) return notFound()
    if (s.reports[edition] === 'GENERATING') return err(409, 'REPORT_IN_PROGRESS', '보고서를 만드는 중입니다. 잠시 후 다시 시도해 주세요.')
    s.reports = { ...s.reports, [edition]: 'PENDING' }
    window.setTimeout(() => { if (s.reports) s.reports = { ...s.reports, [edition]: 'GENERATING' } }, 1500)
    window.setTimeout(() => { if (s.reports) s.reports = { ...s.reports, [edition]: 'DONE' } }, 5000)
    return HttpResponse.json(reportOut(s, edition, new URL(request.url).origin))
  }),

  /** 가짜 PDF: 진짜 서버는 application/pdf 를 준다. 여기서는 미리보기 확인용 HTML 한 장 */
  http.get(`${BASE}/reports/:reportId/file`, async ({ params, request }) => {
    const [sid, edition] = String(params.reportId).split(':') as [string, Edition]
    const s = findSession(sid)
    if (!s || !s.reports || s.reports[edition] !== 'DONE') return notFound()
    const url = new URL(request.url)
    const exp = Number(url.searchParams.get('exp') ?? 0) * 1000
    if (!exp || exp < Date.now()) return err(403, 'FILE_LINK_EXPIRED', '링크가 만료되었습니다. 화면을 새로 불러와 주세요.')
    const dog = findDog(s.dog_id)
    const html = `<!doctype html><meta charset="utf-8"><title>견본 보고서</title>
<body style="margin:0;padding:28px 24px;font-family:'Pretendard Variable',Pretendard,system-ui,sans-serif;color:#1B2433;background:#fff">
<div style="font-size:12px;font-weight:700">Paw oh Paw · ${edition === 'OWNER' ? '보호자용' : '수의사용'} 견본</div>
<div style="height:2px;width:40px;background:#D2601A;margin:12px 0 16px"></div>
<h1 style="font-size:20px;margin:0 0 4px">${dog?.name ?? ''}의 걸음 보고서</h1>
<div style="font-size:12px;color:#5B6472">${s.measured_on} 측정 · 모델 ${s.model_version ?? '-'} · 가짜 서버가 만든 미리보기입니다. 실제 서버는 PDF 를 줍니다.</div>
<p style="margin-top:24px;font-size:13px;line-height:1.7;color:#3A4250">보고서 본문(수치 표, 다리 비교, 안내 문구)은 백엔드 보고서 모듈(D-07)이 만듭니다. 화면은 이 파일을 그대로 보여 주고 내려받기만 합니다.</p>
<p style="font-size:11px;color:#A0A7B2">보행 평가 보조 자료이며 진단을 대신하지 않습니다.</p></body>`
    const download = url.searchParams.get('download') === 'true'
    return new HttpResponse(html, {
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        ...(download ? { 'Content-Disposition': `attachment; filename="${encodeURIComponent(`${dog?.name ?? 'report'}_${s.measured_on}_${edition === 'OWNER' ? '보호자용' : '수의사용'}.html`)}"` } : {}),
      },
    })
  }),

  http.get(`${BASE}/shots/:shotId`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(200)
    for (const s of sessions) {
      const shot = s.shots.find((x) => x.id === params.shotId)
      if (shot) return HttpResponse.json(shotDetailFor(shot, s, new URL(request.url).origin))
    }
    return notFound()
  }),

  http.get(`${BASE}/shots/:shotId/angles`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(250)
    for (const s of sessions) {
      const shot = s.shots.find((x) => x.id === params.shotId)
      if (shot) return HttpResponse.json(shot.status === 'DONE' ? anglesFor(shot) : { shot_id: shot.id, fps: 59.94, passes: [] })
    }
    return notFound()
  }),

  http.get(`${BASE}/dogs/:dogId/compare`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(300)
    const dog = findDog(params.dogId)
    if (!dog) return notFound()
    const url = new URL(request.url)
    const out = compareFor(dog.id, {
      target: url.searchParams.get('target') ?? undefined,
      base: url.searchParams.get('base') ?? undefined,
      gait_type: (url.searchParams.get('gait_type') as 'WALK' | 'TROT' | null) ?? undefined,
    })
    if ('error' in out) {
      if (out.error === 'NOT_FOUND') return notFound()
      return err(400, 'COMPARE_INVALID', '비교할 수 없는 회차입니다.', { reason: out.reason })
    }
    return HttpResponse.json(out)
  }),

  http.get(`${BASE}/dogs/:dogId/trends`, async ({ request, params }) => {
    if (!authed(request)) return unauthorized()
    await delay(250)
    const dog = findDog(params.dogId)
    if (!dog) return notFound()
    const url = new URL(request.url)
    const code = url.searchParams.get('metric_code')
    const gait = url.searchParams.get('gait_type') as 'WALK' | 'TROT' | null
    if (!code || !gait) return err(422, 'VALIDATION_ERROR', '입력값을 확인해 주세요.', { fields: [{ field: code ? 'gait_type' : 'metric_code', type: 'missing' }] })
    return HttpResponse.json(trendsFor(dog.id, code, gait, url.searchParams.get('limb') ?? undefined))
  }),
]
