import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { Icon } from '../components/Icon'
import { Button, Sheet } from '../components/ui'
import { useAuth } from './auth'
import './web.css'

/**
 * 웹 v2 의 바깥 틀. 로그인 뒤에는 앱 내비(홈·분석 결과·마이페이지 + 분석하기 버튼 + 계정 칩),
 * 로그인 전에는 공개 바(서비스 소개·로그인). 랜딩은 자기 헤더를 가지므로 여기서는 그리지 않는다.
 */
export function WebShell() {
  const { loggedIn, staff, logout } = useAuth()
  const loc = useLocation()
  const nav = useNavigate()
  const [menu, setMenu] = useState(false)
  const [askLogout, setAskLogout] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  const go = (to: string) => {
    setMenu(false)
    nav(to)
  }
  const isLanding = loc.pathname === '/welcome'
  const isAuth = loc.pathname === '/login'

  useEffect(() => {
    if (!menu) return
    const onDoc = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenu(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [menu])

  return (
    <div className="web">
      {!isLanding && loggedIn && (
        <header className="web-header">
          <div className="web-header-in">
            <button type="button" className="web-brand" onClick={() => nav('/')}>
              <img src="/assets/logo-joint.png" alt="" />
              Paw oh Paw
            </button>
            <nav className="web-nav">
              <NavLink to="/" end className={({ isActive }) => `web-nav-item${isActive ? ' on' : ''}`}>
                홈
              </NavLink>
              <NavLink to="/results" className={({ isActive }) => `web-nav-item${isActive ? ' on' : ''}`}>
                분석 결과
              </NavLink>
              <NavLink to="/my" className={({ isActive }) => `web-nav-item${isActive ? ' on' : ''}`}>
                마이페이지
              </NavLink>
              <NavLink to="/intro" className={({ isActive }) => `web-nav-item${isActive ? ' on' : ''}`}>
                서비스 소개
              </NavLink>
            </nav>
            <div style={{ flex: 1 }} />
            <button type="button" className="web-cta" onClick={() => nav('/capture')}>
              <Icon name="cam" size={18} />
              분석하기
            </button>
            <div className="web-acct" ref={menuRef}>
              <button type="button" className={`web-acct-chip${menu ? ' on' : ''}`} onClick={() => setMenu((m) => !m)} aria-haspopup="menu" aria-expanded={menu}>
                <span className="web-acct-avatar">{staff?.institution.name.charAt(0) ?? '?'}</span>
                <span className="web-acct-name">{staff?.institution.name ?? ''}</span>
                <Icon name="chev" size={16} style={{ transform: 'rotate(90deg)', color: 'var(--dim)' }} />
              </button>
              {menu && (
                <div className="web-menu" role="menu">
                  <button type="button" role="menuitem" onClick={() => go('/my')}>
                    마이페이지
                  </button>
                  <button type="button" role="menuitem" onClick={() => go('/account')}>
                    기본 정보
                  </button>
                  <button type="button" role="menuitem" className="muted" onClick={() => { setMenu(false); setAskLogout(true) }}>
                    로그아웃
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>
      )}
      {!isLanding && !loggedIn && (
        <header className={`web-header${isAuth ? ' plain' : ''}`}>
          <div className="web-header-in" style={{ justifyContent: 'space-between' }}>
            <button type="button" className="web-brand" onClick={() => nav('/welcome')}>
              <img src="/assets/logo-joint.png" alt="" />
              Paw oh Paw
            </button>
            {!isAuth && (
              <nav className="web-nav">
                <NavLink to="/intro" className={({ isActive }) => `web-nav-item${isActive ? ' on' : ''}`}>
                  서비스 소개
                </NavLink>
                <NavLink to="/login" className="web-nav-item">
                  로그인
                </NavLink>
              </nav>
            )}
          </div>
        </header>
      )}
      <Outlet />
      <Sheet open={askLogout} onClose={() => setAskLogout(false)}>
        <b className="sheet-title">로그아웃할까요?</b>
        <div className="sheet-actions">
          <Button variant="ghost" onClick={() => setAskLogout(false)}>
            취소
          </Button>
          <Button
            variant="dark"
            onClick={() => {
              setAskLogout(false)
              logout()
              nav('/welcome', { replace: true })
            }}
          >
            로그아웃
          </Button>
        </div>
      </Sheet>
    </div>
  )
}
