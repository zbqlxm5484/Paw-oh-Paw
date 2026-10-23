import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../../app/auth'
import { Icon } from '../../components/Icon'
import './intro.css'

const LINES = ['반려견의 걸음을', '더욱 정확하게', 'Paw oh Paw']

/**
 * 스플래시 + 랜딩. 디자인 v5 `splash`·`landing` 그대로: 로고(plain → joint 가 겹쳐 나타남) 뒤 배경 영상 위에 문구 세 줄이 번갈아 뜬다.
 * 회원가입 버튼은 API 가 없어(계정은 관리자가 만든다) 두지 않는다.
 */
export function WelcomePage() {
  const nav = useNavigate()
  const { loggedIn } = useAuth()
  const [splash, setSplash] = useState(() => !sessionStorage.getItem('pp.splashed'))
  const [joint, setJoint] = useState(false)
  const [line, setLine] = useState(0)
  const vidRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    if (loggedIn) nav('/', { replace: true })
  }, [loggedIn, nav])

  // 스플래시: 0.3초 뒤 관절 로고가 겹쳐 나타나고 2.2초 뒤 랜딩으로
  useEffect(() => {
    if (!splash) return
    const t1 = window.setTimeout(() => setJoint(true), 300)
    const t2 = window.setTimeout(() => {
      setSplash(false)
      try {
        sessionStorage.setItem('pp.splashed', '1')
      } catch {
        /* ignore */
      }
    }, 2200)
    return () => {
      window.clearTimeout(t1)
      window.clearTimeout(t2)
    }
  }, [splash])

  // 랜딩 문구: 영상 길이를 셋으로 나눠 구간마다 한 줄씩(디자인 data-lines). 영상이 없으면 2.2초마다
  useEffect(() => {
    if (splash) return
    const v = vidRef.current
    let raf = 0
    const tick = () => {
      if (v && v.duration) {
        const seg = (v.duration - 0.2) / 3
        setLine(Math.min(2, Math.floor(v.currentTime / seg)))
      }
      raf = window.requestAnimationFrame(tick)
    }
    raf = window.requestAnimationFrame(tick)
    const fallback = window.setInterval(() => {
      if (!v || !v.duration) setLine((l) => (l + 1) % LINES.length)
    }, 2200)
    return () => {
      window.cancelAnimationFrame(raf)
      window.clearInterval(fallback)
    }
  }, [splash])

  if (splash) {
    return (
      <button type="button" className="splash" onClick={() => setSplash(false)} aria-label="시작">
        <div className="splash-logo">
          <img src="/assets/logo-plain.png" alt="Paw oh Paw" />
          <img src="/assets/logo-joint.png" alt="" className={`joint${joint ? ' on' : ''}`} />
        </div>
      </button>
    )
  }

  return (
    <div className="landing">
      <video ref={vidRef} className="landing-video" src="/assets/landing.mp4" autoPlay muted loop playsInline poster="/assets/story-1.png" />
      <div className="landing-shade" aria-hidden="true" />
      <div className="landing-lines" aria-live="polite">
        {LINES.map((t, i) => (
          <b key={t} className={i === line ? 'on' : ''}>
            {t}
          </b>
        ))}
      </div>
      <div className="landing-actions">
        <button type="button" className="landing-link" onClick={() => nav('/intro')}>
          서비스 소개 자세히 보기
        </button>
        <button type="button" className="landing-btn" onClick={() => nav('/login')}>
          로그인
          <Icon name="chev" size={20} />
        </button>
        <span className="landing-note">동물병원·재활센터 담당자 계정으로 이용해요. 계정은 기관 관리자가 만들어 드려요.</span>
      </div>
    </div>
  )
}
