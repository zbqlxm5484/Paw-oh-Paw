// 시제품 템플릿의 style="..." 문자열을 React style 객체로 그대로 바꾼다. 값을 손으로 옮기다 틀리지 않게(픽셀 동일).
// 예) <div style={css('display:flex;gap:8px')}>, 값이 바뀌면 템플릿 문자열: css(`background:${bg};padding:4px`)
import type { CSSProperties } from 'react'

const cache = new Map<string, CSSProperties>()

const camel = (p: string): string =>
  p.startsWith('--') ? p : p.replace(/^-(webkit|moz|ms)-/, (_, v) => `${v[0].toUpperCase()}${v.slice(1)}-`).replace(/-([a-z])/g, (_, c) => c.toUpperCase())

export function css(s: string | undefined | null): CSSProperties {
  if (!s) return {}
  const hit = cache.get(s)
  if (hit) return hit
  const out: Record<string, string> = {}
  // 세미콜론으로 나누되 url(...)·괄호 안 세미콜론은 없다고 본다(시제품 스타일에 없음)
  for (const part of s.split(';')) {
    const i = part.indexOf(':')
    if (i < 0) continue
    const k = part.slice(0, i).trim()
    const v = part.slice(i + 1).trim()
    if (k) out[camel(k)] = v
  }
  if (cache.size > 5000) cache.clear()
  cache.set(s, out as CSSProperties)
  return out as CSSProperties
}
