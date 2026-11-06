/**
 * 디자인 화면의 뿌리. 주소 → 화면 이름, 로그인 여부 → 들어갈 수 있는 화면을 정하고
 * API 데이터와 동작을 로직 클래스(AppProto)에 props 로 넘긴다. 앱 v5 화면 하나만 쓴다(웹은 팀원이 따로 만든다).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'

import { dogKeys } from '../api/dogs'

import { fileUrl } from '../api/labels'
import { useSession } from '../api/sessions'
import type { DeviceCodeVerifyOut, LoginIn, ReportOut, ReportsOut, SessionDetailOut, SignupIn } from '../api/types'
import * as authApi from '../api/auth'
import { useAuth } from '../app/auth'
import { enterDemo, exitDemo, isDemo, takeDemoAutologin } from '../app/demoMode'
import { AppProto } from './app/AppProto'
import { AppVetSections, mainGaitOf } from './app/AppVetSections'
import { useCompare, useTrends } from '../api/results'
import { reportStatusLine, toAna, type DAna } from './adapter'
import { useCompareData, useDesignActions, useDesignData, useReportData, type DesignData } from './useDesignData'

export interface RouteInfo {
  screen: string
  params: { sessionId?: string; dogId?: string; petNew?: boolean; petEdit?: string; legal?: string }
}

export interface UiSel {
  cmp: 'base' | 'prev'
  tk: string
}

export interface ProtoProps {
  screen: string
  params: RouteInfo['params']
  query: URLSearchParams
  data: DesignData
  actions: ReturnType<typeof useDesignActions>
  auth: {
    login: (b: LoginIn) => Promise<unknown>
    signup: (b: SignupIn) => Promise<unknown>
    verifyDeviceCode: (code: string) => Promise<DeviceCodeVerifyOut>
    logout: () => void
    updateMe: (b: { name?: string; email?: string }) => Promise<unknown>
    changePassword: (current: string, next: string) => Promise<unknown>
  }
  nav: (path: string, opts?: { replace?: boolean }) => void
  back: () => void
  ui: UiSel
  setUi: (p: Partial<UiSel>) => void
  compare: ReturnType<typeof useCompareData> | null
  reports: ReportsOut | undefined
  /** 보고서 수의사용 탭의 추가 섹션(AppVetSections) */
  vetReport: React.ReactNode
  reportStatus: (r: ReportOut | undefined, model: string) => string
  session: SessionDetailOut | undefined
  sessionAna: DAna | null
  /** 숨은 파일 입력을 연다. capture=true 면 폰 카메라 */
  pickFile: (capture: boolean) => Promise<File | null>
  openFile: (url: string) => boolean
}

/** 주소 → 앱 v5 화면 이름 */
export function parseRoute(pathname: string): RouteInfo {
  const p = pathname.replace(/\/+$/, '') || '/'
  const seg = p.split('/').filter(Boolean)
  if (p === '/') return { screen: 'home', params: {} }
  if (p === '/welcome') return { screen: 'landing', params: {} }
  if (p === '/intro') return { screen: 'story', params: {} }
  if (p === '/login') return { screen: 'login', params: {} }
  if (p === '/signup') return { screen: 'signupOrg', params: {} }
  if (p === '/results') return { screen: 'results', params: {} }
  if (p === '/my') return { screen: 'my', params: {} }
  if (p === '/account') return { screen: 'account', params: {} }
  if (p === '/notifications') return { screen: 'notif', params: {} }
  if (p === '/capture') return { screen: 'capSelect', params: {} }
  if (seg[0] === 'legal' && seg[1]) return { screen: 'legal', params: { legal: seg[1] } } // 약관·개인정보·사업자 정보·고객센터
  if (seg[0] === 'sessions' && seg[1]) {
    const sessionId = seg[1]
    if (seg[2] === 'result') return { screen: 'detail', params: { sessionId } }
    if (seg[2] === 'report') return { screen: 'report', params: { sessionId } }
    if (seg[2] === 'analyzing') return { screen: 'analyzing', params: { sessionId } }
    if (seg[2] === 'record') return { screen: 'capGuide', params: { sessionId } }
    return { screen: 'capReview', params: { sessionId } }
  }
  if (seg[0] === 'dogs') {
    if (seg[1] === 'new') return { screen: 'petNew', params: { petNew: true } }
    const dogId = seg[1]
    if (seg[2] === 'compare') return { screen: 'compare', params: { dogId } }
    if (seg[2] === 'edit') return { screen: 'petNew', params: { petEdit: dogId, dogId } }
    return { screen: 'dog', params: { dogId } }
  }
  return { screen: 'home', params: {} }
}

const PUBLIC = new Set(['landing', 'story', 'login', 'signupOrg', 'splash'])

export function DesignRoot() {
  const loc = useLocation()
  const navigate = useNavigate()
  const { loggedIn, checking, login, signup, logout, setStaff } = useAuth()
  const route = useMemo(() => parseRoute(loc.pathname), [loc.pathname])
  const query = useMemo(() => new URLSearchParams(loc.search), [loc.search])

  // 로그인 안 했으면 공개 화면만. 홈은 랜딩으로, 나머지는 로그인으로 보낸다
  useEffect(() => {
    if (checking) return
    if (!loggedIn && !PUBLIC.has(route.screen)) {
      navigate(route.screen === 'home' ? '/welcome' : `/login?from=${encodeURIComponent(loc.pathname + loc.search)}`, { replace: true })
    } else if (loggedIn && (route.screen === 'login' || route.screen === 'signupOrg')) {
      navigate(query.get('from') || '/', { replace: true })
    }
  }, [checking, loggedIn, route.screen, loc.pathname, loc.search, navigate, query])

  const data = useDesignData(route.screen === 'detail' || route.screen === 'report' ? route.params.sessionId : undefined)
  const actions = useDesignActions()
  const [ui, setUiState] = useState<UiSel>({ cmp: 'base', tk: 'rom' })
  const setUi = useCallback((p: Partial<UiSel>) => setUiState((u) => ({ ...u, ...p })), [])

  const sessScreens = ['analyzing', 'capReview', 'capGuide']
  const sessQ = useSession(sessScreens.includes(route.screen) ? route.params.sessionId : undefined)
  const sessionAna = useMemo(() => (sessQ.data ? toAna(sessQ.data, sessQ.data.dog_id, sessQ.data.id) : null), [sessQ.data])
  const qc = useQueryClient()
  const prevSt = useRef<string | undefined>(undefined)
  useEffect(() => {
    const st = sessQ.data?.status
    if (prevSt.current && prevSt.current !== st && (st === 'DONE' || st === 'FAILED')) qc.invalidateQueries({ queryKey: dogKeys.all })
    prevSt.current = st
  }, [sessQ.data?.status, qc])
  const cmpDog = route.screen === 'compare' ? data.dogs.find((d) => d.id === route.params.dogId) : undefined
  const compare = useCompareData(cmpDog?.id, ui.cmp, ui.tk, cmpDog?.focus ?? null)
  const reportsQ = useReportData(route.screen === 'report' ? route.params.sessionId : undefined)
  // 보고서 수의사용 탭: 이 회차를 직전 회차와 비교(서버 판정)하고 무릎 가동 범위 추이를 읽는다(웹 수의사용 보고서와 같은 구성)
  // 회차 결과 화면도 보고서와 같은 본문을 쓴다
  const repR = route.screen === 'report' || route.screen === 'detail' ? data.results.find((r) => r.id === route.params.sessionId) : undefined
  const repGait = mainGaitOf(repR?.result)
  const repCmpQ = useCompare(repR?.dog, { target: repR?.id, base: 'PREVIOUS', gait_type: repGait })
  const repTrQ = useTrends(repR?.dog, { metric_code: 'rom_stifle', gait_type: repGait })
  const vetReport = repR ? <AppVetSections result={repR.result} cmp={repCmpQ.data} trend={repTrQ.data} /> : null

  // 숨은 파일 입력(영상 선택·촬영)
  const fileRef = useRef<HTMLInputElement>(null)
  const resolver = useRef<((f: File | null) => void) | null>(null)
  const pickFile = useCallback((capture: boolean) => {
    return new Promise<File | null>((resolve) => {
      const el = fileRef.current
      if (!el) return resolve(null)
      resolver.current?.(null)
      resolver.current = resolve
      if (capture) el.setAttribute('capture', 'environment')
      else el.removeAttribute('capture')
      el.value = ''
      el.click()
      // 선택 창을 그냥 닫은 경우: 창이 다시 활성화되고 잠시 뒤에도 파일이 없으면 null
      const onFocus = () => {
        window.removeEventListener('focus', onFocus)
        setTimeout(() => {
          if (resolver.current === resolve) {
            resolver.current = null
            resolve(null)
          }
        }, 800)
      }
      window.addEventListener('focus', onFocus)
    })
  }, [])
  const onFile = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null
    const r = resolver.current
    resolver.current = null
    r?.(f)
  }, [])

  const nav = useCallback((path: string, opts?: { replace?: boolean }) => navigate(path, opts), [navigate])
  const back = useCallback(() => {
    if (window.history.length > 1) navigate(-1)
    else navigate(loggedIn ? '/' : '/welcome')
  }, [navigate, loggedIn])
  /** 서명 주소(PDF 등)를 연다. 앱에서는 폰 브라우저로 넘어가 내려받는다. 체험 모드의 가짜 서버는 앱 밖에서 열 수 없어 false */
  const openFile = useCallback((url: string): boolean => {
    const u = fileUrl(url)
    if (!u || isDemo()) return false
    window.open(u, '_blank', 'noopener')
    return true
  }, [])

  const props: ProtoProps = {
    screen: route.screen, params: route.params, query, data, actions, auth: {
      login, signup, logout, verifyDeviceCode: authApi.verifyDeviceCode,
      updateMe: async (b: { name?: string; email?: string }) => setStaff(await authApi.updateMe(b)),
      changePassword: async (current: string, next: string) => setStaff(await authApi.changePassword(current, next)),
    }, nav, back, ui, setUi,
    compare: route.screen === 'compare' ? compare : null, reports: reportsQ.data, vetReport, reportStatus: reportStatusLine,
    session: sessQ.data, sessionAna, pickFile, openFile,
  }

  const gate = !checking && ((loggedIn && (route.screen === 'login' || route.screen === 'signupOrg')) || (!loggedIn && !PUBLIC.has(route.screen)))
  return (
    <>
      <input ref={fileRef} type="file" accept="video/*" onChange={onFile} style={{ display: 'none' }} />
      {checking || gate ? null : <AppShell {...props} />}
    </>
  )
}

/** 폰 폭: 화면을 꽉 채운다. 넓은 창(데스크톱 브라우저): 디자인 기기 크기(412×915)로 가운데에 */
function AppShell(props: ProtoProps) {
  const [wide, setWide] = useState(() => window.innerWidth >= 520 && window.innerHeight >= 760)
  useEffect(() => {
    const on = () => setWide(window.innerWidth >= 520 && window.innerHeight >= 760)
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  }, [])
  if (wide) {
    return (
      <div style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#E9E6E1', padding: '24px 0' }}>
        <AppProto {...props} rootStyle={{ maxHeight: 'calc(100dvh - 48px)' }} />
        <DemoPill screen={props.screen} />
      </div>
    )
  }
  // 안드로이드 15 이상은 화면이 내비게이션 바 밑까지 그려져 하단 버튼이 걸린다. 화면 안의 요소가 모두 absolute 라
  // 바깥 틀 아래에 그만큼 여백을 둔다(위는 첫 화면 영상이 상태 표시줄 밑까지 보이는 디자인이라 그대로).
  // --safe-area-inset-* 는 Capacitor(SystemBars)가 넣고, 브라우저는 env() 를 쓴다
  return (
    <div style={{ height: '100dvh', paddingBottom: SAFE_BOTTOM, background: '#FAF9F6' }}>
      {/* 디자인의 가짜 상태 표시줄(9:41)은 데스크톱 시안 틀에서만. 폰에서는 진짜 상태 표시줄과 겹친다 */}
      <style>{'.pp-fakebar{display:none !important}'}</style>
      <AppProto {...props} rootStyle={{ width: '100%', height: '100%', borderRadius: 0, boxShadow: 'none' }} />
      <DemoPill screen={props.screen} />
    </div>
  )
}

// 첫 화면(시작 로고 2.2초 뒤)의 배경 영상을 로고가 떠 있는 동안 미리 받아 둔다. 붙이지 않은 video 라 화면에는 안 보인다
const landingPreload = typeof document !== 'undefined' ? document.createElement('video') : null
if (landingPreload) {
  landingPreload.muted = true
  landingPreload.preload = 'auto'
  landingPreload.src = '/assets/landing.mp4'
}

const SAFE_BOTTOM = 'var(--safe-area-inset-bottom, env(safe-area-inset-bottom, 0px))'

/** 체험 모드 버튼. 로그인 전에는 "서버 없이 둘러보기", 체험 중에는 "체험 모드 끝내기"(src/app/demoMode.ts) */
/** 체험 모드 버튼은 첫 화면·로그인·홈·마이페이지에서만 띄운다(결과·보고서·촬영 화면의 내용을 가리지 않게) */
const PILL_SCREENS = new Set(['landing', 'login', 'home', 'my'])

function DemoPill({ screen }: { screen: string }) {
  const { loggedIn, login } = useAuth()
  const demo = isDemo()
  useEffect(() => {
    // 체험 모드에 막 들어왔으면 가짜 계정으로 바로 로그인한다(가짜 서버는 아무 아이디·비밀번호나 받는다)
    if (demo && !loggedIn && takeDemoAutologin()) void login({ login_id: 'demo', password: 'demo' })
  }, [demo, loggedIn, login])
  if ((!demo && loggedIn) || !PILL_SCREENS.has(screen)) return null
  return (
    <button
      type="button"
      onClick={() => (demo ? exitDemo() : enterDemo())}
      style={{
        position: 'fixed',
        // 화면 위쪽은 헤더(로고·알림·기관 칩)와 겹쳐서 아래 탭바 바로 위에 둔다
        bottom: `calc(${SAFE_BOTTOM} + 124px)`,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 1000,
        height: '30px',
        padding: '0 12px',
        border: 'none',
        borderRadius: '15px',
        background: demo ? '#D2601A' : 'rgba(27,36,51,.55)',
        color: '#fff',
        fontSize: '12px',
        fontWeight: 600,
        fontFamily: 'inherit',
        cursor: 'pointer',
      }}
    >
      {demo ? '체험 모드 · 끝내기' : '서버 없이 둘러보기'}
    </button>
  )
}
