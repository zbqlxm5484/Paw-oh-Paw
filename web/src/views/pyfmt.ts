// 파이썬 숫자 서식 흉내. views.py·real.py 가 화면에 찍는 숫자가 한 글자도 다르지 않게.
// round·f"{x:.1f}" 는 이진 값 그대로의 십진 전개를 짝수 반올림한다(JS toFixed 는 동점이면 올림).

/** |x| 의 정확한 십진 전개 → [정수부, 소수부(100자리)] */
function exact(x: number): [string, string] {
  const s = Math.abs(x).toFixed(100) // V8 은 100자리까지 정확(보통 값은 소수 70자리 안에서 끝난다)
  const i = s.indexOf('.')
  return [s.slice(0, i), s.slice(i + 1)]
}

/** 숫자 문자열(점 없음)에 1 더하기 */
function inc(d: string): string {
  const a = d.split('')
  let k = a.length - 1
  while (k >= 0) {
    if (a[k] === '9') {
      a[k] = '0'
      k -= 1
    } else {
      a[k] = String(Number(a[k]) + 1)
      return a.join('')
    }
  }
  return '1' + a.join('')
}

/** 숫자열 digits 를 앞 keep 자리만 남기고 짝수 반올림. 올림으로 자리가 늘면 carry=true */
function roundDigits(digits: string, keep: number): { d: string; carry: boolean } {
  const head = digits.slice(0, keep)
  const rest = digits.slice(keep)
  const r0 = rest[0] ?? '0'
  let up = false
  if (r0 > '5') up = true
  else if (r0 === '5') {
    if (/[1-9]/.test(rest.slice(1))) up = true
    else up = head.length > 0 && Number(head[head.length - 1]) % 2 === 1 // 동점: 짝수로
  }
  if (!up) return { d: head, carry: false }
  const n = inc(head || '0')
  return { d: n, carry: n.length > Math.max(1, head.length) || (head === '' && n === '1') }
}

const neg = (x: number) => x < 0 || Object.is(x, -0)

/** |x| 를 소수 nd 자리로 짝수 반올림한 문자열(부호 없음) */
function fixedAbs(x: number, nd: number): string {
  const [ip, fp] = exact(x)
  const all = ip + fp.slice(0, nd)
  const { d } = roundDigits(ip + fp, ip.length + nd)
  const s = d.padStart(all.length, '0')
  if (nd <= 0) return s.replace(/^0+(?=\d)/, '')
  const cut = s.length - nd
  return (s.slice(0, cut).replace(/^0+(?=\d)/, '') || '0') + '.' + s.slice(cut)
}

/** f"{x:.{nd}f}" */
export function fmt(x: number, nd = 0): string {
  if (Number.isNaN(x)) return 'nan'
  if (!Number.isFinite(x)) return x > 0 ? 'inf' : '-inf'
  return (neg(x) ? '-' : '') + fixedAbs(x, nd)
}

/** f"{x:+.{nd}f}" (정수 f"{x:+d}" 는 nd=0) */
export function fmt_signed(x: number, nd = 0): string {
  const s = fmt(x, nd)
  return s.startsWith('-') ? s : '+' + s
}

/** 파이썬 round(x) / round(x, nd). nd 없으면 정수(짝수 반올림) */
export function pyround(x: number, nd = 0): number {
  if (!Number.isFinite(x)) return x
  const v = Number(fixedAbs(x, nd))
  if (!neg(x) || (nd <= 0 && v === 0)) return v // 정수 round 에는 -0 이 없다
  return -v
}

/** JavaScript Math.round와 같은 반올림 (0.5는 올림) — views.jround */
export function jround(x: number): number {
  return Math.floor(x + 0.5)
}

/** 파이썬 a // b (정수) */
export function floordiv(a: number, b: number): number {
  return Math.floor(a / b)
}

/** 파이썬 a % b (부호는 b 를 따름) */
export function pymod(a: number, b: number): number {
  return ((a % b) + b) % b
}

/** 파이썬 float 의 str()/repr(): 정수 값이면 "28.0" */
export function pystr(x: number): string {
  if (Number.isNaN(x)) return 'nan'
  if (!Number.isFinite(x)) return x > 0 ? 'inf' : '-inf'
  if (x === 0) return Object.is(x, -0) ? '-0.0' : '0.0'
  const a = Math.abs(x)
  if (a >= 1e16 || a < 1e-4) {
    const [m, e] = x.toExponential().split('e')
    const n = Number(e)
    return `${m}e${n < 0 ? '-' : '+'}${String(Math.abs(n)).padStart(2, '0')}`
  }
  const s = String(x)
  return Number.isInteger(x) ? s + '.0' : s
}

/** f"{x:g}" (유효 숫자 6자리, 끝의 0 지움) */
export function g(x: number, prec = 6): string {
  if (Number.isNaN(x)) return 'nan'
  if (!Number.isFinite(x)) return x > 0 ? 'inf' : '-inf'
  const sign = neg(x) ? '-' : ''
  if (x === 0) return sign + '0'
  const [ip, fp] = exact(x)
  const all = (ip + fp).replace(/^0+/, '')
  // 첫 유효 숫자의 지수
  let e = ip !== '0' ? ip.length - 1 : -(fp.length - fp.replace(/^0+/, '').length) - 1
  const sig = all.replace(/^0+/, '')
  const r = roundDigits(sig, prec)
  let d = r.d
  if (d.length > prec) {
    d = d.slice(0, prec)
    e += 1
  }
  d = d.padEnd(prec, '0')
  if (e >= -4 && e < prec) {
    let s: string
    if (e >= 0) s = d.slice(0, e + 1) + '.' + d.slice(e + 1)
    else s = '0.' + '0'.repeat(-e - 1) + d
    s = s.replace(/\.?0+$/, '')
    if (s.endsWith('.')) s = s.slice(0, -1)
    return sign + s
  }
  let m = (d[0] + '.' + d.slice(1)).replace(/\.?0+$/, '')
  if (m.endsWith('.')) m = m.slice(0, -1)
  return `${sign}${m}e${e < 0 ? '-' : '+'}${String(Math.abs(e)).padStart(2, '0')}`
}

/** 파이썬 3.12+ sum(floats): Neumaier 보정 합(첫 값은 0 + x 로 그대로) */
export function pysum(xs: number[]): number {
  if (!xs.length) return 0
  let f = xs[0]
  let c = 0
  for (let i = 1; i < xs.length; i++) {
    const x = xs[i]
    const t = f + x
    if (Math.abs(f) >= Math.abs(x)) c += f - t + x
    else c += x - t + f
    f = t
  }
  if (c && Number.isFinite(c)) f += c
  return f
}

/** 파이썬 float(x): 못 바꾸면 null (views._num) */
export function pyfloat(x: unknown): number | null {
  if (typeof x === 'number') return x
  if (typeof x !== 'string') return null
  const s = x.trim().replace(/(\d)_(?=\d)/g, '$1')
  if (/^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/i.test(s)) return Number(s)
  if (/^[+-]?(inf|infinity)$/i.test(s)) return s.startsWith('-') ? -Infinity : Infinity
  if (/^[+-]?nan$/i.test(s)) return NaN
  return null
}

/** 파이썬 int(s): 못 바꾸면 null(ValueError) */
export function pyint(s: string): number | null {
  const t = s.trim().replace(/(\d)_(?=\d)/g, '$1')
  return /^[+-]?\d+$/.test(t) ? Number(t) : null
}

/** 파이썬 sorted(xs, key, reverse) — 안정 정렬. 키는 숫자·문자열·불·배열(튜플) */
export type Key = number | string | boolean | null | Key[]
export function cmpKey(a: Key, b: Key): number {
  if (Array.isArray(a) && Array.isArray(b)) {
    for (let i = 0; i < Math.min(a.length, b.length); i++) {
      const c = cmpKey(a[i], b[i])
      if (c) return c
    }
    return a.length - b.length
  }
  if (typeof a === 'string' && typeof b === 'string') {
    // 코드 포인트 순(파이썬 str 비교)
    const A = [...a]
    const B = [...b]
    for (let i = 0; i < Math.min(A.length, B.length); i++) {
      const x = A[i].codePointAt(0)!
      const y = B[i].codePointAt(0)!
      if (x !== y) return x < y ? -1 : 1
    }
    return A.length - B.length
  }
  const x = Number(a)
  const y = Number(b)
  return x < y ? -1 : x > y ? 1 : 0
}
export function sorted<T>(xs: Iterable<T>, key: (x: T) => Key = (x) => x as Key, reverse = false): T[] {
  const arr = [...xs]
  return arr.sort((p, q) => (reverse ? -cmpKey(key(p), key(q)) : cmpKey(key(p), key(q))))
}

/** max(xs, key) — 같으면 처음 것 */
export function maxBy<T>(xs: T[], key: (x: T) => Key): T {
  let best = xs[0]
  for (const x of xs.slice(1)) if (cmpKey(key(x), key(best)) > 0) best = x
  return best
}
export function minBy<T>(xs: T[], key: (x: T) => Key): T {
  let best = xs[0]
  for (const x of xs.slice(1)) if (cmpKey(key(x), key(best)) < 0) best = x
  return best
}

/** s.replace(old, new, count) */
export function replaceN(s: string, a: string, b: string, count: number): string {
  let out = s
  let from = 0
  for (let k = 0; k < count; k++) {
    const i = out.indexOf(a, from)
    if (i < 0) break
    out = out.slice(0, i) + b + out.slice(i + a.length)
    from = i + b.length
  }
  return out
}
