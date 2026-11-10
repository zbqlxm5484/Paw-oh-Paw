// 폼 처리(POST). prototype/proto_app/main.py 의 @app.post 함수들을 같은 주소로 옮긴다.
// 백엔드에 있는 기능(로그인·가입·반려견·회차·촬영·관리자)은 backend.ts 를 거쳐 서버에도 보내고, 없는 기능은 이 저장소만 바꾼다.
import type { Go } from '../app/session'
import { herePath } from '../config'

export type Handler = (params: Record<string, string>, fd: FormData) => Go | Promise<Go>

/** 처리 순서: 백엔드 처리 함수가 언제나 먼저(등록 순서·import 순서와 무관). 백엔드가 '__local__' 로 넘기면 로컬 처리 함수로 */
export const BACKEND = 1
const LOCAL = 0
const routes: [RegExp, string[], Handler, number][] = []

/** 주소 패턴 등록. 예) on('/dogs/:dog_id/notes', (p, fd) => ...). 백엔드 처리 함수는 prio = BACKEND */
export function on(pattern: string, h: Handler, prio = LOCAL): void {
  const names: string[] = []
  const re = new RegExp('^' + pattern.replace(/:([a-z_]+)/g, (_, n) => (names.push(n), '([^/]+)')) + '$')
  routes.push([re, names, h, prio])
}

export async function dispatch(path: string, fd: FormData): Promise<Go> {
  const url = new URL(path, window.location.origin)
  const ordered = [...routes].sort((a, b) => b[3] - a[3]) // 같은 우선순위 안에서는 등록 순서(정렬은 안정적)
  for (const [re, names, h] of ordered) {
    const m = url.pathname.match(re)
    if (m) {
      const p: Record<string, string> = {}
      names.forEach((n, i) => (p[n] = decodeURIComponent(m[i + 1])))
      url.searchParams.forEach((v, k) => (p[k] = v))
      const { changed } = await import('./db')
      const g = await h(p, fd)
      if (g.to === '__local__') continue // 백엔드 처리 함수가 "이 기관은 브라우저 저장소에서" 라고 넘긴 경우 다음 처리 함수로
      changed()
      return g
    }
  }
  return { to: herePath() + window.location.search, toast: `처리할 수 없는 요청: ${path}` }
}

/** 반려견 폼 값 검사(11-09 QA: 체중 -3kg·2099년생이 등록됐다). 문제가 없으면 '' */
export function petInputError(kg: string, birth: string, thisYear = new Date().getFullYear()): string {
  const w = Number(kg)
  if (!/^\d+(\.\d+)?$/.test(kg) || !(w >= 0.5 && w <= 100)) return '체중은 0.5~100kg 사이 숫자로 입력해 주세요'
  if (birth && !(/^\d{4}$/.test(birth) && +birth >= 1990 && +birth <= thisYear)) return `출생 연도는 1990~${thisYear} 사이 네 자리로 입력해 주세요`
  return ''
}

/** FormData 에서 문자열 하나(시제품의 Form("")) */
export const f = (fd: FormData, k: string, dflt = ''): string => {
  const v = fd.get(k)
  return typeof v === 'string' ? v : dflt
}

