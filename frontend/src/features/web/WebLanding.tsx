import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../../app/auth'
import { Icon } from '../../components/Icon'
import { IntroStage } from './IntroStage'

/** 스크롤해 들어오면 나타나는 블록(디자인 rv.o/rv.y) */
function Reveal({ className = '', children }: { className?: string; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  const [on, setOn] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(
      (es) => {
        for (const e of es) if (e.isIntersecting) setOn(true)
      },
      { threshold: 0.18 },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return (
    <div ref={ref} className={`${className} reveal${on ? ' in' : ''}`}>
      {children}
    </div>
  )
}

/** 웹 v2 랜딩: 배경 영상 히어로 → Main Service 세 블록 → 서비스 소개 스크롤 스테이지 → 푸터. 회원가입은 API 가 없어 로그인으로 보낸다. */
export function WebLanding() {
  const nav = useNavigate()
  const { loggedIn } = useAuth()
  const introRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (loggedIn) nav('/', { replace: true })
  }, [loggedIn, nav])

  const scrollIntro = () => introRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })

  return (
    <div>
      <section className="wl-hero">
        <video src="/assets/landing.mp4" autoPlay muted loop playsInline poster="/assets/about-film.webp" />
        <div className="fade" />
        <div className="shade" />
        <header>
          <div className="brand">
            <img src="/assets/logo-joint.png" alt="" />
            Paw oh Paw
          </div>
          <nav>
            <button type="button" onClick={scrollIntro}>
              서비스 소개
            </button>
            <button type="button" onClick={() => nav('/login')}>
              로그인
            </button>
            <button type="button" className="pri" onClick={() => nav('/login')}>
              기관 로그인
            </button>
          </nav>
        </header>
        <div className="bar">
          <div className="bar-in">
            <span className="tagline">걷는 영상 하나로, 반려견 보행 분석</span>
            <button type="button" className="start" onClick={() => nav('/login')}>
              기관으로 시작하기
            </button>
          </div>
        </div>
      </section>

      <section className="wl-main">
        <div className="wl-main-in">
          <Reveal className="wl-lead">
            <span className="eyebrow">Main Service</span>
            <h2>
              걷는 영상 하나로
              <br />
              반려견의 보행을
              <br />
              분석해 드려요
            </h2>
          </Reveal>
          <Reveal className="wl-feature">
            <div className="pic">
              <img src="/assets/photo-film.webp" alt="휴대폰으로 걷는 반려견을 촬영하는 모습" />
            </div>
            <div className="txt">
              <span className="eyebrow">촬영</span>
              <h3>
                휴대폰으로
                <br />
                걷는 옆모습만
              </h3>
              <p>
                휴대폰을 가로로 들고
                <br />
                반려견이 평소처럼 걷는 모습을
                <br />
                옆에서 10초만 찍어 주세요.
              </p>
            </div>
          </Reveal>
          <Reveal className="wl-feature rev">
            <div className="txt">
              <span className="eyebrow">AI 분석</span>
              <h3>
                AI가 관절점을
                <br />
                찾아냅니다
              </h3>
              <p>
                영상 속 관절 위치를 프레임마다 추적해
                <br />
                관절 각도와 좌우 차이,
                <br />
                보행 패턴을 계산합니다.
              </p>
            </div>
            <div className="pic">
              <img src="/assets/photo-kp.webp" alt="관절점이 표시된 반려견" />
            </div>
          </Reveal>
          <Reveal className="wl-feature">
            <div className="pic">
              <img src="/assets/photo-report.webp" alt="리포트를 설명하는 수의사와 반려견" />
            </div>
            <div className="txt">
              <span className="eyebrow">리포트</span>
              <h3>
                결과는 리포트로,
                <br />
                PDF로 간편하게
              </h3>
              <p>
                측정한 수치와 그래프를
                <br />
                한눈에 볼 수 있는 리포트로 정리하고
                <br />
                PDF로 저장해 공유할 수 있습니다.
              </p>
            </div>
          </Reveal>
          <Reveal className="wl-intro-cta">
            <button type="button" className="web-btn pri lg" onClick={scrollIntro}>
              서비스 소개 자세히 보기
              <Icon name="chev" size={18} />
            </button>
          </Reveal>
        </div>
      </section>

      <div ref={introRef}>
        <IntroStage ctaLabel="기관으로 시작하기" onCta={() => nav('/login')} />
      </div>

      <footer className="wl-footer">
        <div className="brand">
          <img src="/assets/logo-joint.png" alt="" />
          <span>Paw oh Paw</span>
        </div>
        <div className="links">
          <span>개인정보 처리방침</span>
          <i />
          <span>이용약관</span>
          <i />
          <span>사업자 정보 확인</span>
        </div>
        <span className="copy">© 2026 Paw oh Paw. All rights reserved.</span>
      </footer>
    </div>
  )
}
