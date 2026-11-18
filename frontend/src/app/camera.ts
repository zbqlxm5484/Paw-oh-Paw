/**
 * 앱 안 카메라(촬영 화면의 미리보기·녹화). getUserMedia 를 처음 부를 때 안드로이드 카메라 권한 창이 뜬다
 * (Capacitor 의 WebChromeClient 가 WebView 권한 요청을 안드로이드 권한 요청으로 넘긴다).
 * 서버는 mp4·mov 만 받으므로 mp4 로 녹화할 수 없는 기기에서는 쓰지 않고 기존 방식(기기 카메라 앱)으로 돌아간다.
 */
const MP4_TYPES = ['video/mp4;codecs=avc1.640028', 'video/mp4;codecs=avc1', 'video/mp4']

let stream: MediaStream | null = null
let recorder: MediaRecorder | null = null
let chunks: Blob[] = []

/** 이 기기에서 앱 안 녹화를 쓸 수 있나(카메라 API 와 mp4 녹화) */
export function canRecordInApp(): boolean {
  return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined' && MP4_TYPES.some((t) => MediaRecorder.isTypeSupported(t))
}

/**
 * 카메라가 살아 있나. 앱이 백그라운드로 가면 안드로이드가 카메라를 빼앗는데, WebView 는 트랙을 'live' 로 둔 채
 * 프레임만 멈추는 경우가 있다(11-18 실기기: 미리보기가 멈추고 녹화가 3초 16KB). 그래서 끊김 신호를 따로 기억한다
 */
let lost = false
export function isLive(): boolean {
  return !lost && !!stream && stream.getVideoTracks().some((t) => t.readyState === 'live' && !t.muted)
}

/** 새로 받은 스트림에 끊김 감시를 단다 */
function watch(s: MediaStream): MediaStream {
  lost = false
  for (const t of s.getVideoTracks()) {
    t.addEventListener('ended', () => { if (stream === s) lost = true })
    t.addEventListener('mute', () => { if (stream === s) lost = true })
    t.addEventListener('unmute', () => { if (stream === s && t.readyState === 'live') lost = false })
  }
  return s
}

/** 끊긴 스트림은 닫고 새로 받는다 */
async function freshStream(): Promise<MediaStream> {
  if (stream && !isLive()) {
    stream.getTracks().forEach((t) => t.stop())
    stream = null
  }
  if (!stream) stream = watch(await navigator.mediaDevices.getUserMedia(CONSTRAINTS))
  return stream
}

/** 앱이 다시 화면에 오면 카메라를 다시 붙여야 한다(백그라운드 동안 시스템이 끊는다). 촬영 화면이 이 콜백을 등록한다 */
let onResume: (() => void) | null = null
export function setResumeHandler(fn: (() => void) | null): void {
  onResume = fn
}
if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      // 녹화 중에 화면을 떠나면 그 녹화는 버린다(뒤쪽이 빈 영상이 된다)
      if (recorder && recorder.state !== 'inactive') { recorder.onstop = null; recorder.stop(); recorder = null; chunks = []; cancelAnimationFrame(canvasLoop) }
      if (stream) lost = true
    } else if (stream || onResume) {
      onResume?.()
    }
  })
}

export function isRecording(): boolean {
  return recorder?.state === 'recording'
}

/** 촬영 화면에 들어오자마자 카메라만 먼저 켠다(영상 칸이 생기기 전). 이미 켜져 있으면 그대로 */
export async function warm(): Promise<void> {
  cancelStop()
  if (!canRecordInApp() || isLive()) return
  try {
    await freshStream()
  } catch {
    stream = null
  }
}

let stopTimer = 0
function cancelStop() {
  clearTimeout(stopTimer)
  stopTimer = 0
}
/** 촬영 화면을 잠깐 떠날 때(첨부 목록 확인 등)는 바로 끄지 않고 잠시 뒤에 끈다. 다시 들어오면 곧바로 이어 쓴다 */
export function stopLater(ms = 20000): void {
  cancelStop()
  stopTimer = window.setTimeout(stopPreview, ms)
}

const CONSTRAINTS: MediaStreamConstraints = {
  audio: false,
  // 보행 분석은 60fps 측면 영상이 기준(기업 촬영 조건). 기기가 못 주면 가능한 값으로 받는다
  video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 }, frameRate: { ideal: 60 } },
}

/** 뒤 카메라를 켜서 video 에 붙인다. 권한 거절·카메라 없음이면 false */
export async function startPreview(el: HTMLVideoElement): Promise<boolean> {
  if (!canRecordInApp()) return false
  try {
    cancelStop()
    await freshStream()
    el.removeAttribute('src')
    el.srcObject = stream
    el.muted = true
    await el.play().catch(() => undefined)
    const s = stream?.getVideoTracks()[0]?.getSettings()
    console.info('[camera] preview', s?.width, s?.height, s?.frameRate)
    return true
  } catch (e) {
    console.warn('[camera] preview failed', e)
    stopPreview()
    return false
  }
}

export function stopPreview(): void {
  cancelStop()
  if (recorder && recorder.state !== 'inactive') recorder.stop()
  recorder = null
  stream?.getTracks().forEach((t) => t.stop())
  stream = null
  lost = false
}

let canvasLoop = 0

/**
 * 앱은 세로 고정이라 폰을 가로로 눕혀도 카메라 프레임은 세로(1080×1920)로 오고 장면은 옆으로 누워 있다.
 * 촬영 화면은 폰을 반시계 방향으로 눕히는 디자인이라(위쪽이 왼쪽), 프레임을 반시계 방향으로 돌려 가로 영상으로 녹화한다.
 * 이미 가로 프레임이 오는 기기면 그대로 녹화한다
 */
function landscapeStream(): MediaStream {
  const track = stream!.getVideoTracks()[0]
  const st = track.getSettings()
  const w = st.width ?? 1080
  const h = st.height ?? 1920
  if (w >= h) return stream!
  const fps = st.frameRate ?? 30
  const video = document.createElement('video')
  video.muted = true
  video.playsInline = true
  video.srcObject = stream
  void video.play()
  const canvas = document.createElement('canvas')
  canvas.width = h
  canvas.height = w
  const ctx = canvas.getContext('2d')!
  const draw = () => {
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.translate(0, w)
    ctx.rotate(-Math.PI / 2)
    ctx.drawImage(video, 0, 0, w, h)
    canvasLoop = requestAnimationFrame(draw)
  }
  draw()
  console.info('[camera] record rotated', canvas.width, canvas.height, fps)
  return canvas.captureStream(fps)
}

let recStart = 0
/** 정상 녹화는 12Mbps 라 1초에 1MB 안팎이다. 1초당 100KB 도 안 되면 카메라가 멈춘 채 찍힌 빈 영상으로 본다 */
const MIN_BYTES_PER_SEC = 100_000

export function startRecording(): boolean {
  if (!stream || !isLive() || isRecording()) return false
  const mimeType = MP4_TYPES.find((t) => MediaRecorder.isTypeSupported(t))
  if (!mimeType) return false
  chunks = []
  recStart = Date.now()
  recorder = new MediaRecorder(landscapeStream(), { mimeType, videoBitsPerSecond: 12_000_000 })
  recorder.ondataavailable = (e) => {
    if (e.data.size) chunks.push(e.data)
  }
  recorder.start()
  return true
}

/** 녹화를 멈추고 mp4 파일로 돌려준다 */
export function stopRecording(): Promise<File | null> {
  const r = recorder
  if (!r || r.state === 'inactive') return Promise.resolve(null)
  return new Promise((resolve) => {
    r.onstop = () => {
      cancelAnimationFrame(canvasLoop)
      const blob = new Blob(chunks, { type: 'video/mp4' })
      chunks = []
      const stamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14)
      const sec = (Date.now() - recStart) / 1000
      console.info('[camera] recorded', blob.size, sec.toFixed(1))
      if (sec >= 1 && blob.size < sec * MIN_BYTES_PER_SEC) {
        console.warn('[camera] recording looks empty, dropped')
        lost = true
        return resolve(null)
      }
      resolve(blob.size ? new File([blob], `pawohpaw-${stamp}.mp4`, { type: 'video/mp4' }) : null)
    }
    r.stop()
  })
}

/** 촬영 화면에서는 폰 아래 내비게이션 바를 숨긴다(앱에서만). 화면을 떠나면 다시 보인다 */
export async function setNavBarHidden(hidden: boolean): Promise<void> {
  try {
    const { Capacitor, SystemBars, SystemBarType } = await import('@capacitor/core')
    if (!Capacitor.isNativePlatform()) return
    if (hidden) await SystemBars.hide({ bar: SystemBarType.NavigationBar })
    else await SystemBars.show({ bar: SystemBarType.NavigationBar })
  } catch {
    /* 숨기지 못해도 촬영은 된다 */
  }
}

/** 촬영 화면의 영상 칸은 가로로 눕힌 틀(90° 돌린 div) 안에 있다. 카메라 미리보기는 세로 프레임이 그대로 맞으므로 틀의 회전을 되돌린다 */
export function uprightInRotatedBox(el: HTMLVideoElement): void {
  const box = el.parentElement
  if (!box) return
  Object.assign(el.style, {
    inset: 'auto', left: '50%', top: '50%', width: `${box.clientHeight}px`, height: `${box.clientWidth}px`,
    transform: 'translate(-50%, -50%) rotate(-90deg)', objectFit: 'cover',
  })
}

// ── 첨부한 영상의 첫 프레임 미리보기 ──
// v2: 검은 프레임이 섞여 저장된 예전 기억은 버린다
const THUMB_KEY = 'pp.shot.thumbs.v2'

function loadThumbs(): Record<string, string> {
  try {
    localStorage.removeItem('pp.shot.thumbs')
    return JSON.parse(localStorage.getItem(THUMB_KEY) || '{}') as Record<string, string>
  } catch {
    return {}
  }
}

/** 촬영 id → 첫 프레임 그림(data URL). 이 기기에서 올린 영상만 있다 */
export const shotThumbs: Record<string, string> = loadThumbs()

// ── 서버 결과 영상의 첫 프레임(한 번만 뽑아 기억) ──
// v2: 예전엔 영상 맨 앞의 검은 프레임까지 그림으로 저장해 버렸다. 그 기억은 버리고 새로 뽑는다
const SERVER_KEY = 'pp.shot.serverThumbs.v2'
function loadServerThumbs(): Record<string, string> {
  try {
    localStorage.removeItem('pp.shot.serverThumbs')
    return JSON.parse(localStorage.getItem(SERVER_KEY) || '{}') as Record<string, string>
  } catch {
    return {}
  }
}
/** 촬영 id → 서버 결과 영상에서 뽑은 첫 프레임 그림(data URL). 목록을 다시 열어도 영상을 다시 안 불러온다 */
export const serverThumbs: Record<string, string> = loadServerThumbs()

/** 캔버스가 거의 검은색인지(평균 밝기). 로딩 전·영상 맨 앞의 검은 프레임을 그림으로 남기지 않으려고 본다 */
function isDark(c: HTMLCanvasElement): boolean {
  const ctx = c.getContext('2d')!
  const { data } = ctx.getImageData(0, 0, c.width, c.height)
  let sum = 0
  let n = 0
  for (let i = 0; i < data.length; i += 4 * 37) { sum += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]; n++ }
  return n === 0 || sum / n < 20
}

/** 이미 받은 <video> 에서 작은 jpeg 를 뽑아 촬영 id 에 붙여 둔다. 못 뽑으면(다른 출처·0 크기·검은 프레임) undefined */
export function captureFrame(v: HTMLVideoElement, shotId: string): string | undefined {
  try {
    if (!v.videoWidth || !v.videoHeight) return undefined
    const w = 320
    const h = Math.round((w * v.videoHeight) / v.videoWidth)
    const c = document.createElement('canvas')
    c.width = w
    c.height = h
    c.getContext('2d')!.drawImage(v, 0, 0, w, h)
    if (isDark(c)) return undefined
    const d = c.toDataURL('image/jpeg', 0.7)
    serverThumbs[shotId] = d
    const keys = Object.keys(serverThumbs)
    for (const k of keys.slice(0, Math.max(0, keys.length - 200))) delete serverThumbs[k]
    try { localStorage.setItem(SERVER_KEY, JSON.stringify(serverThumbs)) } catch { /* 저장 못 하면 이번 화면에서만 */ }
    return d
  } catch {
    return undefined // 교차 출처 등으로 canvas 가 막히면 자리표시 그대로
  }
}

/** 영상 파일의 첫 프레임을 작은 jpeg 로 만들어 촬영 id 에 붙여 둔다(새로 불러와도 남게 저장) */
export async function rememberFirstFrame(shotId: string, file: File): Promise<void> {
  const url = URL.createObjectURL(file)
  try {
    const v = document.createElement('video')
    v.muted = true
    v.playsInline = true
    v.preload = 'auto'
    v.src = url
    await new Promise<void>((ok, bad) => {
      v.onloadeddata = () => ok()
      v.onerror = () => bad(new Error('video'))
      setTimeout(() => bad(new Error('timeout')), 8000)
    })
    // 0초는 검은 프레임인 기기가 있어 조금 뒤로
    v.currentTime = Math.min(0.1, (v.duration || 1) / 2)
    await new Promise<void>((ok) => { v.onseeked = () => ok(); setTimeout(ok, 1500) })
    const w = 320
    const h = Math.round((w * (v.videoHeight || 9)) / (v.videoWidth || 16))
    const c = document.createElement('canvas')
    c.width = w
    c.height = h
    c.getContext('2d')!.drawImage(v, 0, 0, w, h)
    if (isDark(c)) return // 검은 프레임은 남기지 않는다(서버 영상에서 다시 뽑는다)
    shotThumbs[shotId] = c.toDataURL('image/jpeg', 0.7)
    const keys = Object.keys(shotThumbs)
    for (const k of keys.slice(0, Math.max(0, keys.length - 160))) delete shotThumbs[k] // 오래된 것부터 지워 저장소를 작게
    try {
      localStorage.setItem(THUMB_KEY, JSON.stringify(shotThumbs))
    } catch {
      /* 저장 못 하면 이번 화면에서만 보인다 */
    }
  } catch {
    /* 첫 프레임을 못 뽑으면 디자인 그림 그대로 */
  } finally {
    URL.revokeObjectURL(url)
  }
}
