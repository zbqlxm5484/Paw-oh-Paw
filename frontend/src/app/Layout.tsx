import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { IconSprite } from '../components/Icon'
import { useIsDesktop } from './useIsDesktop'
import { WebShell } from './WebShell'
import './layout.css'

/**
 * 모든 화면의 바깥 틀. 1024px 이상이면 웹 v2 틀(WebShell), 아니면 앱 v5 폰 프레임.
 * 폰 폭은 꽉 채우고, 데스크톱 브라우저에서 창이 좁을 때는 가운데 412×915 기둥으로 보인다.
 */
export function AppFrame() {
  const desktop = useIsDesktop()
  if (desktop)
    return (
      <>
        <IconSprite />
        <WebShell />
      </>
    )
  return (
    <div className="app-shell">
      <IconSprite />
      <div className="app-frame">
        <Outlet />
      </div>
    </div>
  )
}

/** 하단 탭이 있는 화면들(홈 · 소개 · 분석 · 분석 결과 · 마이페이지). 웹 틀에서는 상단 내비가 대신하므로 탭바를 그리지 않는다. */
export function TabLayout() {
  const nav = useNavigate()
  const desktop = useIsDesktop()
  if (desktop) return <Outlet />
  return (
    <>
      <Outlet />
      <nav className="tabbar" aria-label="주요 화면">
        <div className="tabbar-inner">
          <NavLink to="/" end className={({ isActive }) => `tab${isActive ? ' on' : ''}`}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round">
              <path d="M4 10.5 12 4l8 6.5V20H4z" />
              <path d="M10 20v-5h4v5" />
            </svg>
            홈
          </NavLink>
          <NavLink to="/story" className={({ isActive }) => `tab${isActive ? ' on' : ''}`}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <circle cx="12" cy="12" r="8.5" />
              <path d="M12 11v5M12 8v.01" />
            </svg>
            소개
          </NavLink>
          <div className="tab-center">
            <button type="button" className="tab-capture" onClick={() => nav('/capture')} aria-label="보행 분석 시작">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              분석
            </button>
          </div>
          <NavLink to="/results" className={({ isActive }) => `tab${isActive ? ' on' : ''}`}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <path d="M4 20h16M7 16v-6M12 16V5M17 16v-4" />
            </svg>
            분석 결과
          </NavLink>
          <NavLink to="/my" className={({ isActive }) => `tab${isActive ? ' on' : ''}`}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <circle cx="12" cy="8.5" r="3.5" />
              <path d="M5 20c1-3.6 3.8-5.5 7-5.5s6 1.9 7 5.5" />
            </svg>
            마이페이지
          </NavLink>
        </div>
      </nav>
    </>
  )
}
