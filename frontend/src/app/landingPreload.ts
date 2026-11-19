// 첫 화면(시작 로고 2.2초 뒤)의 배경 영상을 로고가 떠 있는 동안 미리 받아 둔다. 붙이지 않은 video 라 화면에는 안 보인다.
// 예전에는 모듈을 읽자마자 받아서 로그인·홈 등 모든 화면이 2.5MB 영상을 받았다 → 시작 로고를 띄울 때(로그아웃 상태 첫 화면)만 받는다.
let started = false

export function preloadLanding() {
  if (started || typeof document === 'undefined') return
  started = true
  const v = document.createElement('video')
  v.muted = true
  v.preload = 'auto'
  v.src = '/assets/landing.mp4'
}
