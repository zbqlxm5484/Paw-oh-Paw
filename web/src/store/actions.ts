// 폼 처리(POST). prototype/proto_app/main.py 의 @app.post 함수들을 같은 주소로 옮긴다.
// 백엔드에 있는 기능(로그인·가입·반려견·회차·촬영·관리자)은 backend.ts 를 거쳐 서버에도 보내고, 없는 기능은 이 저장소만 바꾼다.
import type { Go } from '../app/session'

type Handler = (params: Record<string, string>, fd: FormData) => Go | Promise<Go>

const routes: [RegExp, string[], Handler][] = []

/** 주소 패턴 등록. 예) on('/dogs/:dog_id/notes', (p, fd) => ...) */
export function on(pattern: string, h: Handler): void {
  const names: string[] = []
  const re = new RegExp('^' + pattern.replace(/:([a-z_]+)/g, (_, n) => (names.push(n), '([^/]+)')) + '$')
  routes.push([re, names, h])
}

export async function dispatch(path: string, fd: FormData): Promise<Go> {
  const url = new URL(path, window.location.origin)
  for (const [re, names, h] of routes) {
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
  return { to: window.location.pathname + window.location.search, toast: `처리할 수 없는 요청: ${path}` }
}

/** FormData 에서 문자열 하나(시제품의 Form("")) */
export const f = (fd: FormData, k: string, dflt = ''): string => {
  const v = fd.get(k)
  return typeof v === 'string' ? v : dflt
}

