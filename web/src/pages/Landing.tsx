// landing.html: 로그인 전 첫 화면. 로그인한 사람은 바로 홈으로(main.py landing)
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { staticUrl, usePage, useTitle } from '../app/page'

const RV = 'opacity:0;transform:translateY(72px);transition:opacity 1s cubic-bezier(.2,.7,.2,1),transform 1s cubic-bezier(.2,.7,.2,1)'
const RV2 = 'opacity:0;transform:translateY(72px);transition:opacity 1s cubic-bezier(.2,.7,.2,1) .15s,transform 1s cubic-bezier(.2,.7,.2,1) .15s'

export default function Landing() {
  useTitle('Paw oh Paw · 걷는 영상 하나로, 반려견 보행 분석')
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
            <a className="lk" href={acct ? '/home' : '/'} style={css('display:flex;align-items:center;gap:8px;color:#fff;font-size:19px;font-weight:800;letter-spacing:-0.4px')}><img src={`${img}logo.png`} alt="" style={css('width:34px;height:34px;object-fit:contain;filter:drop-shadow(0 1px 6px rgba(0,0,0,.25))')} />Paw oh Paw</a>
            <nav style={css('display:flex;align-items:center;gap:8px')}>
              <a className="lk" href="/about" style={css('height:40px;padding:0 14px;display:flex;align-items:center;font-size:15px;font-weight:600;color:#fff;text-shadow:0 1px 6px rgba(0,0,0,.3)')}>서비스 소개</a>
              {acct ? (
                <a className="lk" href="/home" style={css('height:40px;padding:0 14px;display:flex;align-items:center;font-size:15px;font-weight:600;color:#fff;text-shadow:0 1px 6px rgba(0,0,0,.3)')}>홈</a>
              ) : (
                <>
                  <a className="lk" href="/login" style={css('height:40px;padding:0 14px;display:flex;align-items:center;font-size:15px;font-weight:600;color:#fff;text-shadow:0 1px 6px rgba(0,0,0,.3)')}>로그인</a>
                  <a className="lk hv-orange" href="/signup" style={css('height:42px;padding:0 18px;border-radius:6px;background:#D2601A;color:#fff;display:flex;align-items:center;font-size:15px;font-weight:700')}>회원가입</a>
                </>
              )}
            </nav>
          </div>
        </header>
        <div style={css('position:absolute;left:0;right:0;bottom:0;height:120px;display:flex;align-items:center')}>
          <div style={css('width:100%;padding:0 80px;display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap')}>
            <span style={css('font-size:clamp(18px,1.8vw,26px);font-weight:700;letter-spacing:-0.6px;color:#1B2433')}>걷는 영상 하나로, 반려견 보행 분석</span>
            <div style={css('display:flex;align-items:center;gap:28px')}>
              <a className="lk hv-orange" href={acct ? '/upload' : '/signup'} style={css('height:60px;padding:0 32px;border-radius:6px;background:#D2601A;color:#fff;display:flex;align-items:center;font-size:18px;font-weight:700;transition:background .2s')}>{acct ? '보행 분석 시작하기' : '기관으로 시작하기'}</a>
            </div>
          </div>
        </div>
      </section>

      <section style={css('background:linear-gradient(180deg,#FAF9F6 0%,#FFF3EA 18%,#FFF3EA 82%,#FAF9F6 100%);color:#1B2433')}>
        <div style={css('max-width:none;margin:0;padding:160px 80px 160px;display:flex;flex-direction:column;gap:180px')}>
          <div className="rv" style={css(`display:flex;flex-direction:column;align-items:center;gap:24px;text-align:center;${RV}`)}>
            <span style={css('font-size:20px;font-weight:700;color:#D2601A;letter-spacing:-0.2px')}>Main Service</span>
            <h2 style={css('margin:0;font-size:clamp(36px,4.6vw,68px);line-height:1.22;font-weight:800;letter-spacing:-2px;text-wrap:balance')}>걷는 영상 하나로<br />반려견의 보행을<br />분석해 드려요</h2>
          </div>
          <div className="rv-group" style={css('display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:48px 64px')}>
            <div className="rv" style={css(`flex:1 1 420px;min-width:0;max-width:820px;aspect-ratio:5 / 4;border-radius:32px;overflow:hidden;background:#FBE5D6;box-shadow:0 30px 60px -30px rgba(210,96,26,.25);${RV}`)}><img src={`${img}landing-shoot.jpg`} alt="휴대폰으로 걷는 반려견을 촬영하는 모습" style={css('width:100%;height:100%;object-fit:cover;display:block')} /></div>
            <div className="rv" style={css(`flex:1 1 340px;min-width:0;max-width:560px;display:flex;flex-direction:column;gap:22px;${RV2}`)}>
              <span style={css('font-size:19px;font-weight:700;color:#D2601A')}>촬영</span>
              <h3 style={css('margin:0;font-size:clamp(34px,3.9vw,58px);line-height:1.22;font-weight:800;letter-spacing:-1.6px')}>휴대폰으로<br />걷는 옆모습만</h3>
              <p style={css('margin:0;font-size:19px;line-height:1.75;color:#5B6472;text-wrap:pretty')}>휴대폰을 가로로 들고<br />반려견이 평소처럼 걷는 모습을<br />옆에서 10초만 찍어 주세요.</p>
            </div>
          </div>
          <div className="rv-group" style={css('display:flex;flex-wrap:wrap-reverse;align-items:center;justify-content:space-between;gap:48px 64px')}>
            <div className="rv" style={css(`flex:1 1 340px;min-width:0;max-width:560px;display:flex;flex-direction:column;${RV2}`)}>
              <div style={css('display:flex;flex-direction:column;gap:22px;max-width:100%')}>
                <span style={css('font-size:19px;font-weight:700;color:#D2601A')}>AI 분석</span>
                <h3 style={css('margin:0;font-size:clamp(34px,3.9vw,58px);line-height:1.22;font-weight:800;letter-spacing:-1.6px')}>AI가 관절점을<br />찾아냅니다</h3>
                <p style={css('margin:0;font-size:19px;line-height:1.75;color:#5B6472;text-wrap:pretty')}>영상 속 관절 위치를 프레임마다 추적해<br />관절 각도와 좌우 차이,<br />보행 패턴을 계산합니다.</p>
              </div>
            </div>
            <div className="rv" style={css(`flex:1 1 420px;min-width:0;max-width:820px;aspect-ratio:5 / 4;border-radius:32px;overflow:hidden;background:#FBE5D6;box-shadow:0 30px 60px -30px rgba(210,96,26,.25);${RV}`)}><img src={`${img}landing-keypoints.jpg`} alt="관절점이 표시된 반려견" style={css('width:100%;height:100%;object-fit:cover;display:block')} /></div>
          </div>
          <div className="rv-group" style={css('display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:48px 64px')}>
            <div className="rv" style={css(`flex:1 1 420px;min-width:0;max-width:820px;aspect-ratio:5 / 4;border-radius:32px;overflow:hidden;background:#FBE5D6;box-shadow:0 30px 60px -30px rgba(210,96,26,.25);${RV}`)}><img src={`${img}landing-report.jpg`} alt="리포트를 설명하는 수의사와 반려견" style={css('width:100%;height:100%;object-fit:cover;display:block')} /></div>
            <div className="rv" style={css(`flex:1 1 340px;min-width:0;max-width:560px;display:flex;flex-direction:column;gap:22px;${RV2}`)}>
              <span style={css('font-size:19px;font-weight:700;color:#D2601A')}>리포트</span>
              <h3 style={css('margin:0;font-size:clamp(34px,3.9vw,58px);line-height:1.22;font-weight:800;letter-spacing:-1.6px')}>결과는 리포트로,<br />PDF로 간편하게</h3>
              <p style={css('margin:0;font-size:19px;line-height:1.75;color:#5B6472;text-wrap:pretty')}>측정한 수치와 그래프를<br />한눈에 볼 수 있는 리포트로 정리하고<br />PDF로 저장해 공유할 수 있습니다.</p>
            </div>
          </div>
          <div className="rv" style={css(`display:flex;justify-content:center;${RV}`)}><a className="lk hv-orange" href="/about" style={css('height:56px;padding:0 28px;border-radius:6px;background:#D2601A;color:#fff;display:flex;align-items:center;gap:8px;font-size:16px;font-weight:700')}>서비스 소개 자세히 보기<svg width="18" height="18" viewBox="0 0 24 24"><use href="#w-chev"></use></svg></a></div>
        </div>
      </section>
      <footer style={css('border-top:1px solid #E8E4DC;background:#F3F1EC;padding:72px 24px 88px;display:flex;flex-direction:column;align-items:center;gap:28px;text-align:center')}>
        <div style={css('display:flex;align-items:center;gap:10px')}><img src={`${img}logo.png`} alt="" style={css('width:36px;height:36px;object-fit:contain')} /><span style={css('font-size:26px;font-weight:800;letter-spacing:-0.6px;color:#1B2433')}>Paw oh Paw</span></div>
        <div style={css('display:flex;flex-wrap:wrap;justify-content:center;align-items:center;gap:12px;font-size:15px;font-weight:700;color:#5B6472')}>
          <span className="hv-dark" style={css('cursor:pointer')} data-toast="준비 중이에요">개인정보 처리방침</span><span style={css('width:1.5px;height:14px;background:#A0A7B2')}></span><span className="hv-dark" style={css('cursor:pointer')} data-toast="준비 중이에요">이용약관</span><span style={css('width:1.5px;height:14px;background:#A0A7B2')}></span><span className="hv-dark" style={css('cursor:pointer')} data-toast="준비 중이에요">사업자 정보 확인</span>
        </div>
        <span style={css('font-size:13px;color:#A0A7B2')}>© 2026 Paw oh Paw. All rights reserved.</span>
      </footer>
    </Base>
  )
}
