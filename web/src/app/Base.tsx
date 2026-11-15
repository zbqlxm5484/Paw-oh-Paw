// 공통 틀. prototype/proto_app/templates/base.html 과 static/app.js 를 옮겼다(마크업·스타일 그대로).
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { herePath, link, SHOW_JUMPS, unlink } from '../config'
import { changed } from '../store/db'
import type { Account, Staff } from '../store/types'
import { finished_notices, hasActive } from './session'
import { JUMPS } from './jumps'
import { staticUrl } from './page'

declare global {
  interface Window {
    ppToast: (m: string) => void
    ppOpen: (id: string) => void
    ppClose: (el: Element) => void
  }
}

export interface BaseProps {
  acct?: Account
  me?: Staff
  nav?: string
  q?: string
  toast?: string
  /** 분석 중 화면처럼 이 화면이 직접 알림을 다루면 그 작업 id */
  jobId?: string
  topbar?: ReactNode | false
  modals?: ReactNode
  children?: ReactNode
}

export function Base({ acct, me, nav = '', q = '', toast = '', jobId = '', topbar, modals, children }: BaseProps) {
  const navigate = useNavigate()
  const [msg, setMsg] = useState(toast)
  const [show, setShow] = useState(!!toast)
  const tt = useRef<number | undefined>(undefined)
  const [jumpOpen, setJumpOpen] = useState(false)
  const lb = useRef<HTMLDivElement>(null)

  useEffect(() => {
    window.ppToast = (m: string) => {
      setMsg(m)
      setShow(true)
      clearTimeout(tt.current)
      tt.current = window.setTimeout(() => setShow(false), 2400)
    }
    window.ppOpen = (id: string) => {
      const m = document.getElementById(id)
      if (m) m.style.display = 'flex'
    }
    window.ppClose = (el: Element) => {
      const m = el.closest('.pp-modal') as HTMLElement | null
      if (m) m.style.display = 'none'
    }
  }, [])

  useEffect(() => {
    if (toast) window.ppToast(toast)
  }, [toast])

  // 모달·사진 팝업·행 클릭·알림 버튼·화면 안 링크(새로 불러오지 않고 이동)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const box = lb.current
      if (e.key === 'Escape' && box && box.style.display === 'flex') box.style.display = 'none'
    }
    const onClick = (e: MouseEvent) => {
      const t = e.target as HTMLElement
      const o = t.closest('[data-open]') as HTMLElement | null
      if (o) {
        e.preventDefault()
        window.ppOpen(o.dataset.open || '')
        return
      }
      const c = t.closest('[data-close]')
      if (c) {
        e.preventDefault()
        window.ppClose(c)
        return
      }
      if (t.classList && t.classList.contains('pp-modal')) (t as HTMLElement).style.display = 'none'
      const l = t.closest('[data-lightbox]') as HTMLAnchorElement | null
      if (l && lb.current) {
        e.preventDefault()
        const box = lb.current
        const img = box.querySelector('img') as HTMLImageElement
        img.src = l.getAttribute('href') || ''
        img.alt = l.dataset.caption || ''
        ;(box.querySelector('.lb-cap') as HTMLElement).textContent = l.dataset.caption || ''
        ;(box.querySelector('.lb-orig') as HTMLAnchorElement).href = l.getAttribute('href') || ''
        box.style.display = 'flex'
        return
      }
      const ts = t.closest('[data-toast]') as HTMLElement | null
      if (ts) {
        e.preventDefault()
        window.ppToast(ts.dataset.toast || '')
        return
      }
      const row = t.closest('[data-href]') as HTMLElement | null
      if (row && !t.closest('form, button, a')) {
        navigate(row.dataset.href || '/')
        return
      }
      const a = t.closest('a[href]') as HTMLAnchorElement | null
      if (a && !e.defaultPrevented && !a.target && !a.hasAttribute('download') && e.button === 0 && !e.metaKey && !e.ctrlKey) {
        let href = unlink(a.getAttribute('href') || '') // link() 로 붙인 /web 을 떼고 라우터에 넘긴다
        if (href.startsWith('?')) href = herePath() + href // 같은 화면의 다른 보기(?type=v 등)
        if (href.startsWith('/') && !href.startsWith('/static/') && !href.startsWith('/uploads/') && !href.startsWith('/api/')) {
          e.preventDefault()
          navigate(href)
        }
      }
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('click', onClick)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('click', onClick)
    }
  }, [navigate])

  // 작성자 이름: 로그인한 담당자 이름을 기본으로(고칠 수 있다). 이름이 없으면 이 브라우저에서 마지막에 쓴 이름
  useEffect(() => {
    let last = me?.name || ''
    if (!last) {
      try {
        last = localStorage.getItem('pp_author') || ''
      } catch {
        /* 무시 */
      }
    }
    document.querySelectorAll<HTMLInputElement>('input.author-inp').forEach((i) => {
      if (!i.value) i.value = last
    })
  })

  // 다른 화면에 있을 때 분석이 끝나면 알림 ("콩이 분석이 끝났어요")
  useEffect(() => {
    if (!acct || !hasActive(acct) || jobId) return
    const timer = window.setInterval(() => {
      const n = finished_notices(acct)
      if (n.length) {
        window.ppToast(n[0])
        document.querySelectorAll('.live-badge').forEach((b) => b.remove())
        changed()
      }
      if (!hasActive(acct)) clearInterval(timer)
    }, 1500)
    return () => clearInterval(timer)
  }, [acct, jobId])

  return (
    <>
      <svg width="0" height="0" style={{ position: 'absolute' }}>
        <defs>
          <g id="w-chev"><path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"></path></g>
          <g id="w-back"><path d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"></path></g>
          <g id="w-x"><path d="M6 6l12 12M18 6 6 18" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"></path></g>
          <g id="w-check"><path d="M5 12.5 10 17 19 7" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"></path></g>
          <g id="w-bell"><path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20.5h4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"></path></g>
          <g id="w-user"><circle cx="12" cy="8.5" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.6"></circle><path d="M5 20c1-4 4-5.5 7-5.5s6 1.5 7 5.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"></path></g>
          <g id="w-org"><path d="M4 20V8l8-4 8 4v12M9 20v-5h6v5M4 20h16" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"></path></g>
          <g id="w-doc"><path d="M7 3h7l4 4v14H7z M14 3v4h4 M10 12h5M10 16h5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"></path></g>
          <g id="w-up"><path d="M12 16V4M6 10l6-6 6 6M4 20h16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"></path></g>
          <g id="w-headset"><path d="M4 14v-2a8 8 0 0 1 16 0v2" fill="none" stroke="currentColor" strokeWidth="1.7"></path><rect x="3" y="13" width="4" height="6" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.7"></rect><rect x="17" y="13" width="4" height="6" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.7"></rect></g>
        </defs>
      </svg>

      <div className="page-bg" style={{ overflowX: 'clip', minHeight: '100vh', background: '#FAF9F6', position: 'relative' }}>
        {topbar !== undefined ? topbar || null : acct ? <TopBar acct={acct} nav={nav} q={q} /> : null}
        {children}
      </div>

      {modals}

      <div id="toast" className="no-print" style={{ position: 'fixed', left: 0, right: 0, bottom: 40, zIndex: 60, display: show ? 'flex' : 'none', justifyContent: 'center', pointerEvents: 'none' }}><span id="toastMsg" style={{ padding: '13px 20px', borderRadius: 12, background: 'rgba(27,36,51,.94)', color: '#fff', fontSize: 15, fontWeight: 600 }}>{msg}</span></div>

      {SHOW_JUMPS && (
        <div className="no-print" style={{ position: 'fixed', left: 20, bottom: 20, zIndex: 70, display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 8 }}>
          <div id="jumpMenu" style={{ width: 220, maxHeight: '60vh', overflow: 'auto', background: '#fff', border: '1px solid #E2DCD3', borderRadius: 14, boxShadow: '0 16px 40px rgba(27,36,51,.16)', padding: 6, display: jumpOpen ? 'flex' : 'none', flexDirection: 'column' }}>
            {JUMPS.map(([label], i) => <a key={i} className="lk hv-menu" href={link(`/jump/${i}`)} style={{ minHeight: 44, padding: '0 12px', borderRadius: 8, display: 'flex', alignItems: 'center', fontSize: 14 }}>{label}</a>)}
          </div>
          <div id="jumpBtn" onClick={() => setJumpOpen(!jumpOpen)} style={{ height: 40, padding: '0 14px', borderRadius: 20, background: '#1B2433', color: '#fff', display: 'flex', alignItems: 'center', fontSize: 13, fontWeight: 700, cursor: 'pointer', boxShadow: '0 6px 18px rgba(27,36,51,.25)' }}>화면 바로가기</div>
        </div>
      )}

      <div id="lightbox" ref={lb} className="pp-modal no-print" style={{ position: 'fixed', inset: 0, background: 'rgba(14,18,23,.82)', zIndex: 60, display: 'none', alignItems: 'center', justifyContent: 'center', padding: 32 }}>
        <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 'min(1100px,94vw)', maxHeight: '92vh' }}>
          <img src={undefined} alt="" style={{ maxWidth: '100%', maxHeight: 'calc(92vh - 60px)', objectFit: 'contain', borderRadius: 12, background: '#0E1217', display: 'block', margin: '0 auto' }} />
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, color: '#fff' }}><b className="lb-cap" style={{ fontSize: 15 }}></b>
            <span style={{ display: 'flex', gap: 8 }}><a className="lb-orig lk" target="_blank" rel="noopener" style={{ height: 44, padding: '0 14px', borderRadius: 9, border: '1px solid rgba(255,255,255,.4)', color: '#fff', display: 'flex', alignItems: 'center', fontSize: 14, fontWeight: 600 }}>원본 열기</a><button type="button" className="bt" data-close="" style={{ height: 44, padding: '0 16px', borderRadius: 9, background: '#fff', color: '#1B2433', fontSize: 14, fontWeight: 700 }}>닫기</button></span>
          </div>
        </div>
      </div>
    </>
  )
}

function TopBar({ acct, nav, q }: { acct: Account; nav: string; q: string }) {
  const navigate = useNavigate()
  return (
    <header className="no-print" style={{ position: 'sticky', top: 0, zIndex: 20, background: 'rgba(250,243,231,.92)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)', borderBottom: '1px solid #ECE8E2' }}>
      <div style={{ padding: '0 25px', height: 74, display: 'flex', alignItems: 'center', gap: 28 }}>
        <a className="lk" href={link('/home')} style={{ display: 'flex', alignItems: 'center', minHeight: 44, gap: 8, fontSize: 18, fontWeight: 800, letterSpacing: '-0.4px', flex: 'none' }}><img src={staticUrl('assets/logo.png')} alt="" style={{ width: 30, height: 30, objectFit: 'contain' }} />Paw oh Paw</a>
        {/* 가운데 검색: 어느 화면에서든 이름·동물번호·특이사항·메모·진단·보호자로 찾는다 */}
        <form method="get" action="/home" style={{ flex: 1, display: 'flex', justifyContent: 'center', margin: 0, minWidth: 0 }}
          onSubmit={(e) => {
            e.preventDefault()
            const v = String(new FormData(e.currentTarget).get('q') || '')
            navigate(v ? `/home?q=${encodeURIComponent(v)}` : '/home')
          }}>
          <label style={{ width: '100%', maxWidth: 560, height: 44, borderRadius: 22, border: '1px solid #E2DCD3', background: '#fff', display: 'flex', alignItems: 'center', gap: 8, padding: '0 16px', color: '#7A808A' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" style={{ flex: 'none' }}><circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.8"></circle><path d="M16 16l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"></path></svg>
            <input name="q" key={q} defaultValue={q} placeholder="반려견 검색 (이름, 동물번호, 진단, 보호자, 메모)" style={{ flex: 1, minWidth: 0, border: 'none', outline: 'none', fontSize: 15, background: 'transparent', color: '#1B2433' }} />
          </label>
        </form>
        <a className="lk hv-orange" href={link('/upload')} style={{ height: 44, padding: '0 18px', borderRadius: 12, background: '#D2601A', color: '#fff', display: 'flex', alignItems: 'center', gap: 8, fontSize: 15, fontWeight: 700, flex: 'none' }}><svg width="18" height="18" viewBox="0 0 24 24"><use href="#w-up"></use></svg>새 측정</a>
        <a className="lk hv-border" href={link('/my')} style={{ height: 44, padding: '0 14px 0 6px', borderRadius: 22, border: '1px solid #E2DCD3', background: nav === 'my' ? '#FCEEE3' : '#fff', display: 'flex', alignItems: 'center', gap: 8, flex: 'none' }}><span style={{ width: 30, height: 30, borderRadius: 15, background: '#FCEEE3', color: '#A8481A', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 800 }}>{acct.name.slice(0, 1)}</span><span className="acct-kind" style={{ fontSize: 13, fontWeight: 600, color: '#5B6472', whiteSpace: 'nowrap' }}>기관</span><span className="acct-name" style={{ fontSize: 14, fontWeight: 700, whiteSpace: 'nowrap' }}>{acct.name}</span></a>
      </div>
    </header>
  )
}
