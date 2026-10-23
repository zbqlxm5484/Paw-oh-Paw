import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../../app/auth'
import { DogSkeleton } from '../../components/DogSkeleton'
import { Icon } from '../../components/Icon'
import './intro.css'

const LINES = ['반려견의 걸음을', '더욱 정확하게', 'Paw oh Paw']

/**
 * 스플래시 + 랜딩. 디자인 v5 `splash`·`landing`.
 * 디자인의 로고 PNG 와 배경 영상(landing.mp4)은 저장소에 아직 없어 글자 로고와 그라데이션으로 대신한다(assets 넣으면 교체).
 * 회원가입 버튼은 API 가 없어(계정은 관리자가 만든다) 두지 않는다.
 */
export function WelcomePage() {
  const nav = useNavigate()
  const { loggedIn } = useAuth()
  const [splash, setSplash] = useState(() => !sessionStorage.getItem('pp.splashed'))
  const [line, setLine] = useState(0)

  useEffect(() => {
    if (loggedIn) nav('/', { replace: true })
  }, [loggedIn, nav])

  useEffect(() => {
    if (!splash) return
    const t = window.setTimeout(() => {
      setSplash(false)
      try {
        sessionStorage.setItem('pp.splashed', '1')
      } catch {
        /* ignore */
      }
    }, 2000)
    return () => window.clearTimeout(t)
  }, [splash])

  useEffect(() => {
    const t = window.setInterval(() => setLine((l) => (l + 1) % LINES.length), 2200)
    return () => window.clearInterval(t)
  }, [])

  if (splash) {
    return (
      <button type="button" className="splash" onClick={() => setSplash(false)} aria-label="시작">
        <div className="splash-logo">
          <span className="paw-mark">
            <Icon name="paw" size={64} />
          </span>
          <b>Paw oh Paw</b>
        </div>
      </button>
    )
  }

  return (
    <div className="landing">
      <div className="landing-bg" aria-hidden="true">
        <div className="landing-dog">
          <DogSkeleton width={260} height={160} />
        </div>
      </div>
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
