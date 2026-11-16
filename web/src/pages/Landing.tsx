// landing.html: 로그인 전 첫 화면. 로그인한 사람은 바로 홈으로(main.py landing)
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { staticUrl, usePage, useTitle } from '../app/page'
import { link } from '../config'

const RV = 'opacity:0;transform:translateY(72px);transition:opacity 1s cubic-bezier(.2,.7,.2,1),transform 1s cubic-bezier(.2,.7,.2,1)'
const RV2 = 'opacity:0;transform:translateY(72px);transition:opacity 1s cubic-bezier(.2,.7,.2,1) .15s,transform 1s cubic-bezier(.2,.7,.2,1) .15s'

export default function Landing() {
  useTitle('Paw oh Paw')
  const { acct, me, toast } = usePage()
  const navigate = useNavigate()
  const img = staticUrl('assets/')

  useEffect(() => {
    if (acct) navigate('/home', { replace: true })
  }, [acct, navigate])

  // 스크롤해서 보이면 나타나기 (디자인의 checkReveal)
  useEffect(() => {
    if (acct) return
    const groups: HTMLElement[] = []
    document.querySelectorAll<HTMLElement>('.rv').forEach((el) => {
      const g = (el.closest('.rv-group') as HTMLElement | null) || el
      if (groups.indexOf(g) < 0) groups.push(g)
    })
    const check = () => {
      groups.forEach((g) => {
        if (g.dataset.seen) return
        if (g.getBoundingClientRect().top < window.innerHeight * 0.82) {
          g.dataset.seen = '1'
          const els = g.classList.contains('rv') ? [g] : Array.from(g.querySelectorAll<HTMLElement>('.rv'))
          els.forEach((el) => {
            el.style.opacity = '1'
            el.style.transform = 'translateY(0px)'
          })
        }
      })
    }
    window.addEventListener('scroll', check, { passive: true })
    window.addEventListener('resize', check)
    check()
    const v = document.getElementById('heroVid') as HTMLVideoElement | null
    if (v) {
      v.muted = true
      v.play().catch(() => {})
    }
    return () => {
      window.removeEventListener('scroll', check)
      window.removeEventListener('resize', check)
    }
  }, [acct])

  if (acct) return null

  return (
    <Base acct={acct} me={me} toast={toast} topbar={false}>
      <section style={css('position:relative;height:100vh;min-height:620px;max-height:960px;overflow:hidden;background:#EEE2CE')}>
        <video id="heroVid" src={`${img}landing-walk.mp4`} autoPlay muted loop playsInline style={css('position:absolute;top:0;left:0;width:calc(100% + 140px);height:calc(100% - 120px);max-width:none;object-fit:cover')}></video>
        <div style={css('position:absolute;left:0;right:0;bottom:120px;height:140px;background:linear-gradient(180deg,rgba(238,226,206,0),#EEE2CE);pointer-events:none')}></div>
        <div style={css('position:absolute;inset:0;background:linear-gradient(180deg,rgba(27,36,51,.35) 0%,rgba(27,36,51,0) 22%);pointer-events:none')}></div>
        <header style={css('position:absolute;top:0;left:0;right:0;z-index:2')}>
          <div style={css('padding:25px 25px 0;display:flex;align-items:center;justify-content:space-between;gap:16px')}>
            <a className="lk" href={link(acct ? '/home' : '/')} style={css('display:flex;align-items:center;min-height:44px;gap:8px;color:#fff;font-size:18px;font-weight:800;letter-spacing:-0.4px')}><img src={`${img}logo.png`} alt="" style={css('width:34px;height:34px;object-fit:contain;filter:drop-shadow(0 1px 6px rgba(0,0,0,.25))')} />Paw oh Paw</a>
            <nav style={css('display:flex;align-items:center;gap:8px')}>
              <a className="lk" href={link('/about')} style={css('height:44px;padding:0 14px;display:flex;align-items:center;font-size:15px;font-weight:600;color:#fff;text-shadow:0 1px 6px rgba(0,0,0,.3)')}>서비스 소개</a>
              {acct ? (
                <a className="lk" href={link('/home')} style={css('height:44px;padding:0 14px;display:flex;align-items:center;font-size:15px;font-weight:600;color:#fff;text-shadow:0 1px 6px rgba(0,0,0,.3)')}>홈</a>
              ) : (
                <>
                  <a className="lk" href={link('/login')} style={css('height:44px;padding:0 14px;display:flex;align-items:center;font-size:15px;font-weight:600;color:#fff;text-shadow:0 1px 6px rgba(0,0,0,.3)')}>로그인</a>
                  <a className="lk hv-orange" href={link('/signup')} style={css('height:44px;padding:0 18px;border-radius:6px;background:#D2601A;color:#fff;display:flex;align-items:center;font-size:15px;font-weight:700')}>회원가입</a>
                </>
              )}
            </nav>
          </div>
        </header>
        <style>{'@keyframes pp-hint{0%,100%{transform:translateY(0)}50%{transform:translateY(6px)}}'}</style>
        <a className="lk" href="#service" onClick={(e) => { e.preventDefault(); document.getElementById('service')?.scrollIntoView({ behavior: 'smooth' }) }} aria-label="아래로 스크롤"
          style={css('position:absolute;left:50%;bottom:60px;transform:translate(-50%,50%);z-index:2;display:flex;flex-direction:column;align-items:center;gap:6px;color:rgba(27,36,51,.55);font-size:14px;font-weight:600;letter-spacing:-0.2px;white-space:nowrap')}>
          <span>아래로 스크롤하면 서비스 기능을 확인하실 수 있습니다</span>
          <svg width="22" height="22" viewBox="0 0 24 24" style={css('animation:pp-hint 1.6s ease-in-out infinite')}><path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </a>
        <div style={css('position:absolute;left:0;right:0;bottom:0;height:120px;display:flex;align-items:center')}>
          <div style={css('width:100%;padding:0 80px;display:flex;align-items:center;justify-content:flex-end;gap:24px;flex-wrap:wrap')}>
            <div style={css('display:flex;align-items:center;gap:28px')}>
              <a className="lk hv-orange" href={link(acct ? '/upload' : '/signup')} style={css('height:60px;padding:0 32px;border-radius:6px;background:#D2601A;color:#fff;display:flex;align-items:center;font-size:18px;font-weight:700;transition:background .2s')}>{acct ? '보행 분석 시작하기' : '기관으로 시작하기'}</a>
            </div>
          </div>
        </div>
      </section>

      <section id="service" style={css('background:linear-gradient(180deg,#FAF9F6 0%,#FFF3EA 18%,#FFF3EA 82%,#FAF9F6 100%);color:#1B2433')}>
        <div style={css('max-width:none;margin:0;padding:160px 80px 160px;display:flex;flex-direction:column;gap:180px')}>
          <div className="rv" style={css(`display:flex;flex-direction:column;align-items:center;gap:24px;text-align:center;${RV}`)}>
            <span style={css('font-size:18px;font-weight:700;color:#D2601A;letter-spacing:-0.2px')}>Main Service</span>
            <h2 style={css('margin:0;font-size:clamp(30px,3.6vw,52px);line-height:1.25;font-weight:800;letter-spacing:-1.5px;text-wrap:balance')}>걷는 영상으로 강아지의 보행을<br />체계적으로 분석해 드립니다</h2>
          </div>
          <div className="rv-group" style={css('display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:48px 64px')}>
            <div className="rv" style={css(`flex:1 1 420px;min-width:0;max-width:820px;aspect-ratio:5 / 4;border-radius:32px;overflow:hidden;background:#FBE5D6;box-shadow:0 30px 60px -30px rgba(210,96,26,.25);${RV}`)}><img src={`${img}landing-emr.jpg`} alt="진료실 모니터에 떠 있는 강아지 차트 화면" style={css('width:100%;height:100%;object-fit:cover;display:block')} /></div>
            <div className="rv" style={css(`flex:1 1 340px;min-width:0;max-width:560px;display:flex;flex-direction:column;gap:22px;${RV2}`)}>
              <span style={css('font-size:18px;font-weight:700;color:#D2601A')}>EMR 형식의 화면</span>
              <h3 style={css('margin:0;font-size:clamp(34px,3.9vw,58px);line-height:1.22;font-weight:800;letter-spacing:-1.6px')}>쓰던 차트 그대로</h3>
              <p style={css('margin:0;font-size:18px;line-height:1.75;color:#5B6472;text-wrap:pretty')}>기존 EMR 시스템처럼 사용할 수 있습니다.</p>
            </div>
          </div>
          <div className="rv-group" style={css('display:flex;flex-wrap:wrap-reverse;align-items:center;justify-content:space-between;gap:48px 64px')}>
            <div className="rv" style={css(`flex:1 1 340px;min-width:0;max-width:560px;display:flex;flex-direction:column;gap:22px;${RV2}`)}>
              <span style={css('font-size:18px;font-weight:700;color:#D2601A')}>촬영 즉시 분석</span>
              <h3 style={css('margin:0;font-size:clamp(34px,3.9vw,58px);line-height:1.22;font-weight:800;letter-spacing:-1.6px')}>휴대폰 촬영 한 번으로<br />빠른 보행 분석</h3>
              <p style={css('margin:0;font-size:18px;line-height:1.75;color:#5B6472;text-wrap:pretty')}>걷는 옆모습 영상을 업로드하면<br />관절 각도·좌우 대칭·보행 패턴을 바로 계산합니다.</p>
            </div>
            <div className="rv" style={css(`flex:1 1 420px;min-width:0;max-width:820px;aspect-ratio:5 / 4;border-radius:32px;overflow:hidden;background:#FBE5D6;box-shadow:0 30px 60px -30px rgba(210,96,26,.25);${RV}`)}><img src={`${img}landing-capture.jpg`} alt="진료실에서 휴대폰으로 강아지의 걷는 옆모습을 촬영하는 수의사" style={css('width:100%;height:100%;object-fit:cover;display:block')} /></div>
          </div>
          <div className="rv-group" style={css('display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:48px 64px')}>
            <div className="rv" style={css(`flex:1 1 420px;min-width:0;max-width:820px;aspect-ratio:5 / 4;border-radius:32px;overflow:hidden;background:#FBE5D6;box-shadow:0 30px 60px -30px rgba(210,96,26,.25);${RV}`)}><img src={`${img}landing-compare.jpg`} alt="회차별 보행 수치 변화를 그래프로 비교하는 화면" style={css('width:100%;height:100%;object-fit:cover;display:block')} /></div>
            <div className="rv" style={css(`flex:1 1 340px;min-width:0;max-width:560px;display:flex;flex-direction:column;gap:22px;${RV2}`)}>
              <span style={css('font-size:18px;font-weight:700;color:#D2601A')}>경과 비교</span>
              <h3 style={css('margin:0;font-size:clamp(34px,3.9vw,58px);line-height:1.22;font-weight:800;letter-spacing:-1.6px')}>회복 경과를<br />한눈에</h3>
              <p style={css('margin:0;font-size:18px;line-height:1.75;color:#5B6472;text-wrap:pretty')}>기준 회차·직전 회차와 수치를 나란히 비교하고<br />회차별 추이를 그래프로 보여 줍니다.<br />수술 전후와 재활 경과를 숫자로 확인할 수 있습니다.</p>
            </div>
          </div>
          <div className="rv-group" style={css('display:flex;flex-wrap:wrap-reverse;align-items:center;justify-content:space-between;gap:48px 64px')}>
            <div className="rv" style={css(`flex:1 1 340px;min-width:0;max-width:560px;display:flex;flex-direction:column;gap:22px;${RV2}`)}>
              <span style={css('font-size:18px;font-weight:700;color:#D2601A')}>두 가지 보고서</span>
              <h3 style={css('margin:0;font-size:clamp(34px,3.9vw,58px);line-height:1.22;font-weight:800;letter-spacing:-1.6px')}>보호자용·수의사용<br />보고서 제공</h3>
              <p style={css('margin:0;font-size:18px;line-height:1.75;color:#5B6472;text-wrap:pretty')}>같은 회차를 보호자용, 수의사용 판본으로 함께 만들고<br />PDF 로 내려받아 공유할 수 있습니다.</p>
            </div>
            <div className="rv" style={css(`flex:1 1 500px;min-width:0;max-width:980px;aspect-ratio:5 / 4;${RV}`)}><img src={`${img}landing-report.jpg`} alt="보호자용과 수의사용 보고서 PDF 를 함께 보는 모습" style={css('width:100%;height:100%;object-fit:cover;display:block')} /></div>
          </div>
          <div className="rv" style={css(`display:flex;justify-content:center;${RV}`)}><a className="lk hv-orange" href={link('/about')} style={css('height:56px;padding:0 28px;border-radius:6px;background:#D2601A;color:#fff;display:flex;align-items:center;gap:8px;font-size:15px;font-weight:700')}>서비스 소개 자세히 보기<svg width="18" height="18" viewBox="0 0 24 24"><use href="#w-chev"></use></svg></a></div>
        </div>
      </section>
      <footer style={css('border-top:1px solid #E8E4DC;background:#F3F1EC;padding:72px 24px 88px;display:flex;flex-direction:column;align-items:center;gap:28px;text-align:center')}>
        <div style={css('display:flex;align-items:center;gap:10px')}><img src={`${img}logo.png`} alt="" style={css('width:36px;height:36px;object-fit:contain')} /><span style={css('font-size:28px;font-weight:800;letter-spacing:-0.6px;color:#1B2433')}>Paw oh Paw</span></div>
        <div style={css('display:flex;flex-wrap:wrap;justify-content:center;align-items:center;gap:12px;font-size:15px;font-weight:700;color:#5B6472')}>
          <a className="lk hv-dark tap" href={link('/terms')}>서비스 이용약관</a><span style={css('width:1.5px;height:14px;background:#A0A7B2')}></span><a className="lk hv-dark tap" href={link('/privacy')} style={css('color:#1B2433')}>개인정보 처리방침</a><span style={css('width:1.5px;height:14px;background:#A0A7B2')}></span><a className="lk hv-dark tap" href={link('/support')}>고객센터</a>
        </div>
        <span style={css('font-size:13px;color:#5B6472')}>© 2026 Paw oh Paw. All rights reserved.</span>
      </footer>
    </Base>
  )
}
