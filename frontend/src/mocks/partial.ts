/**
 * 반쪽 가짜 서버(VITE_MOCK=partial). 백엔드에 이미 있는 API 는 그대로 진짜 서버로 보내고(onUnhandledFrame: 'bypass'),
 * 아직 없는 API 만 여기서 받는다. 진짜 반려견·회차 id 를 가짜 DB 가 모르므로 가짜 데이터를 지어내지 않고
 * "빈 목록" 또는 "아직 없는 기능" 오류로만 답한다. 백엔드에 생기면 여기서 한 줄씩 지운다.
 *
 * 백엔드 develop(10-29)에 있는 것: health, auth/login·me, dogs 목록·등록·상세·수정,
 * dogs/:id/sessions 시작(POST), sessions/:id 조회·취소, sessions/:id/shots 업로드, shots/:id 조회·재시도·삭제,
 * sessions/:id/complete 측정 종료·sessions/:id/result 회차 결과(!65)
 */
import { http, HttpResponse } from 'msw'

const BASE = `${(import.meta.env.VITE_API_BASE as string | undefined) ?? ''}/api/v1`

const notYet = (what: string) =>
  HttpResponse.json(
    { error: { code: 'NOT_IMPLEMENTED', message: `${what} 기능은 아직 서버에 없어요.`, detail: null } },
    { status: 501 },
  )

export const partialHandlers = [
  // 반려견별 측정 이력: 없으면 화면 전체가 못 뜨므로 빈 목록. 측정 중인 회차는 dogs 의 open_session_id 로 따로 읽는다
  http.get(`${BASE}/dogs/:dogId/sessions`, ({ request }) => {
    const u = new URL(request.url)
    return HttpResponse.json({ items: [], total: 0, page: Number(u.searchParams.get('page') ?? 1), size: Number(u.searchParams.get('size') ?? 100) })
  }),
  http.get(`${BASE}/sessions/:sessionId/reports`, () => notYet('보고서')),
  http.post(`${BASE}/reports/:reportId/regenerate`, () => notYet('보고서 다시 만들기')),
  http.get(`${BASE}/reports/:reportId/file`, () => notYet('보고서 파일')),
  http.get(`${BASE}/shots/:shotId/angles`, () => notYet('관절 각도')),
  http.get(`${BASE}/dogs/:dogId/compare`, () => notYet('경과 비교')),
  http.get(`${BASE}/dogs/:dogId/trends`, () => notYet('추이')),
]
