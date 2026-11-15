/**
 * 체험 모드: 서버 없이 가짜 데이터(MSW, src/mocks)로 화면만 둘러본다.
 * 켜고 끄면 저장된 토큰을 지우고 새로 불러온다. 진짜 토큰과 가짜 토큰이 섞이지 않게 하려는 것이다.
 */
const DEMO_KEY = 'pp.demo'
const AUTOLOGIN_KEY = 'pp.demo.autologin'
const TOKEN_KEYS = ['pp.token', 'pp.expires_at']

function get(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function clearTokens() {
  try {
    for (const k of TOKEN_KEYS) localStorage.removeItem(k)
  } catch {
    /* 저장소를 못 쓰면 지울 것도 없다 */
  }
}

export function isDemo(): boolean {
  return get(DEMO_KEY) === '1'
}

export function enterDemo() {
  clearTokens()
  try {
    localStorage.setItem(DEMO_KEY, '1')
    localStorage.setItem(AUTOLOGIN_KEY, '1')
  } catch {
    return // 저장소를 못 쓰면 새로 불러온 뒤 켜진 상태를 기억할 수 없다
  }
  window.location.replace('/')
}

/** 체험 모드를 끝내고 next 로 새로 연다(기본 첫 화면) */
export function exitDemo(next = '/') {
  clearTokens()
  try {
    localStorage.removeItem(DEMO_KEY)
    localStorage.removeItem(AUTOLOGIN_KEY)
  } catch {
    /* 무시 */
  }
  window.location.replace(next)
}

/** 앱에서 체험 모드 진입을 없앴다(11-15). 예전 판에서 체험 모드로 켜 둔 기기는 시작할 때 조용히 끄고 가짜 토큰을 지운다 */
export function dropLeftoverDemo(): void {
  if (!isDemo()) return
  clearTokens()
  try {
    localStorage.removeItem(DEMO_KEY)
    localStorage.removeItem(AUTOLOGIN_KEY)
  } catch {
    /* 무시 */
  }
}

/** 체험 모드에 막 들어왔을 때 한 번만 true. 가짜 계정으로 바로 로그인시키는 데 쓴다 */
export function takeDemoAutologin(): boolean {
  if (get(AUTOLOGIN_KEY) !== '1') return false
  try {
    localStorage.removeItem(AUTOLOGIN_KEY)
  } catch {
    /* 무시 */
  }
  return true
}
