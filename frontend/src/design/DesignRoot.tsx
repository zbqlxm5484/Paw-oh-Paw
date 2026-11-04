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
import type { LoginIn, ReportOut, ReportsOut, SessionDetailOut } from '../api/types'
import * as authApi from '../api/auth'
import { useAuth } from '../app/auth'
import { AppProto } from './app/AppProto'
import { reportStatusLine, toAna, type DAna } from './adapter'
import { useCompareData, useDesignActions, useDesignData, useReportData, type DesignData } from './useDesignData'

export interface RouteInfo {
  screen: string
  params: { sessionId?: string; dogId?: string; petNew?: boolean; petEdit?: string }
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
  reportStatus: (r: ReportOut | undefined, model: string) => string
  session: SessionDetailOut | undefined
  sessionAna: DAna | null
  /** 숨은 파일 입력을 연다. capture=true 면 폰 카메라 */
  pickFile: (capture: boolean) => Promise<File | null>
  openFile: (url: string) => void
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
  const { loggedIn, checking, login, logout, setStaff } = useAuth()
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
  const openFile = useCallback((url: string) => {
    const u = fileUrl(url)
    if (u) window.open(u, '_blank', 'noopener')
  }, [])

  const props: ProtoProps = {
    screen: route.screen, params: route.params, query, data, actions, auth: {
      login, logout,
      updateMe: async (b: { name?: string; email?: string }) => setStaff(await authApi.updateMe(b)),
      changePassword: async (current: string, next: string) => setStaff(await authApi.changePassword(current, next)),
    }, nav, back, ui, setUi,
    compare: route.screen === 'compare' ? compare : null, reports: reportsQ.data, reportStatus: reportStatusLine,
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
      </div>
    )
  }
  return <AppProto {...props} rootStyle={{ width: '100%', height: '100dvh', borderRadius: 0, boxShadow: 'none' }} />
}
