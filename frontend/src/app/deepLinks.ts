/**
 * 앱이 링크로 열렸을 때(App Links: 웹 '폰으로 촬영' QR) 그 주소의 화면으로 간다.
 * 앱이 꺼져 있다가 링크로 켜진 경우와 이미 켜져 있던 경우 모두 appUrlOpen 으로 온다.
 */
export async function listenDeepLinks(go: (path: string) => void): Promise<void> {
  const { Capacitor } = await import('@capacitor/core')
  if (!Capacitor.isNativePlatform()) return
  const { App } = await import('@capacitor/app')
  const open = (url: string) => {
    try {
      const u = new URL(url)
      go(u.pathname + u.search)
    } catch {
      /* 모르는 주소는 무시 */
    }
  }
  await App.addListener('appUrlOpen', ({ url }) => open(url))
  const launch = await App.getLaunchUrl()
  if (launch?.url) open(launch.url)
}
