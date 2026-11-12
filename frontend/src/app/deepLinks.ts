/**
 * 앱이 링크로 열렸을 때(App Links: 웹 '폰으로 촬영' QR) 그 주소의 화면으로 간다.
 * 앱이 꺼져 있다가 링크로 켜진 경우와 이미 켜져 있던 경우 모두 appUrlOpen 으로 온다.
 */
import { exitDemo, isDemo } from './demoMode'

/** 체험 모드(가짜 서버) 회차 ID 는 s0000000-… 이다. 그 밖의 회차 링크(실제 QR)는 가짜 서버가 모른다 */
const REAL_SESSION = /^\/sessions\/(?!s0000000-)[^/]+/

export async function listenDeepLinks(go: (path: string) => void): Promise<void> {
  const { Capacitor } = await import('@capacitor/core')
  if (!Capacitor.isNativePlatform()) return
  const { App } = await import('@capacitor/app')
  const open = (url: string) => {
    try {
      const u = new URL(url)
      const path = u.pathname + u.search
      // 체험 모드로 켜진 앱에 실제 회차 QR 이 오면 체험 모드를 끝내고 로그인한 뒤 그 회차로 간다(그대로 두면 업로드가 404)
      if (isDemo() && REAL_SESSION.test(u.pathname)) return exitDemo(`/login?from=${encodeURIComponent(path)}`)
      go(path)
    } catch {
      /* 모르는 주소는 무시 */
    }
  }
  await App.addListener('appUrlOpen', ({ url }) => open(url))
  const launch = await App.getLaunchUrl()
  if (launch?.url) open(launch.url)
}
