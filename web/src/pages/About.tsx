// about.html + static/about.js: 서비스 소개. 스크롤에 따라 다섯 장면이 아래에서 덮이며 바뀐다
import { useEffect } from 'react'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { staticUrl, usePage, useTitle } from '../app/page'

const STEPS: [string, string][] = [
  ['모든 견종', '대형견부터 소형견까지, 모든 반려견의 걸음을 분석합니다.'],
  ['촬영', '반려견이 걷는 모습을 옆에서 촬영합니다.'],
  ['영상 첨부', '반려견은 원하는 만큼 등록하고, 골라서 영상을 올려 주세요.'],
  ['AI 분석', 'AI 모델이 관절점을 찾고, 보행 패턴을 분석합니다.'],
  ['리포트', '결과를 리포트로 받아 PDF로 저장할 수 있습니다.'],
]

// 로그인 전 상단 바 (로그인했으면 기본 상단 바)
function GuestBar() {
  return (
    <header style={css('position:sticky;top:0;z-index:20;background:rgba(250,243,231,.92);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid #ECE8E2')}>
      <div style={css('padding:0 25px;height:74px;display:flex;align-items:center;justify-content:space-between;gap:16px')}>
        <a className="lk" href="/" style={css('display:flex;align-items:center;gap:8px;font-size:18px;font-weight:800;letter-spacing:-0.4px')}><img src={staticUrl('assets/logo.png')} alt="" style={css('width:30px;height:30px;object-fit:contain')} />Paw oh Paw</a>
        <nav style={css('display:flex;align-items:center;gap:8px')}>
          <span style={css('height:40px;padding:0 14px;border-radius:10px;background:#F1EAE0;color:#B4501A;display:flex;align-items:center;font-size:15px;font-weight:700')}>서비스 소개</span>
          <a className="lk" href="/login" style={css('height:40px;padding:0 14px;display:flex;align-items:center;font-size:15px;font-weight:600')}>로그인</a>
          <a className="lk" href="/signup" style={css('height:40px;padding:0 16px;border-radius:10px;background:#1B2433;color:#fff;display:flex;align-items:center;font-size:15px;font-weight:700')}>회원가입</a>
        </nav>
      </div>
    </header>
  )
}

const ROW = 'display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr'

export default function About() {
  useTitle('서비스 소개 · Paw oh Paw')
  const { acct, me, toast } = usePage()
  const img = staticUrl('assets/')

  // about.js 그대로: 매 프레임 스크롤 위치(P)로 장면을 칠한다
  useEffect(() => {
    const story = document.getElementById('scStory')
    if (!story) return
    const $ = (id: string) => document.getElementById(id) as HTMLElement
    const layers = Array.from(document.querySelectorAll<HTMLElement>('.sc-layer'))
    const steps = Array.from(document.querySelectorAll<HTMLElement>('.sc-step'))
    const N = 5
    const cl = (v: number) => Math.max(0, Math.min(1, v))

    // 보고서 카드의 곡선 (고정값)
    const pts = (amp: number, ph: number) => {
      const a: string[] = []
      for (let i = 0; i <= 40; i++) a.push(24 + i * 7.15 + ',' + (75 - amp * Math.sin((i / 40) * Math.PI * 4 - ph)).toFixed(1))
      return a.join(' ')
    }
    $('kL').setAttribute('points', pts(48, 0))
    $('kR').setAttribute('points', pts(40, 0.5))

    const apply = (P: number) => {
      const sm = (a: number, b: number) => {
        const t = cl((P - a) / (b - a))
        return t * t * (3 - 2 * t)
      }
      const bd = (i: number) => i / N
      const inP = (i: number) => (i === 0 ? 1 : sm(bd(i) - 0.05, bd(i) + 0.025))

      layers.forEach((el, i) => {
        const nx = i < N - 1 ? inP(i + 1) : 0
        el.style.clipPath = 'inset(' + ((1 - inP(i)) * 100).toFixed(3) + '% 0 0 0)'
        ;(el.querySelector('.sc-scale') as HTMLElement).style.transform = 'scale(' + (1 - 0.05 * nx).toFixed(3) + ')'
        ;(el.querySelector('.sc-dark') as HTMLElement).style.opacity = (0.35 * nx).toFixed(3)
      })

      // 영상 첨부 장면
      const u = cl((P - 0.44) / 0.12)
      $('upThumb').style.opacity = u > 0 ? '1' : '0'
      $('upBar').style.width = Math.round(u * 100) + '%'
      $('upTxt').textContent = u <= 0 ? '영상을 끌어다 놓거나 눌러서 선택' : u < 1 ? '업로드 중 · ' + Math.round(u * 100) + '%' : '업로드 완료 · 00:12'
      $('upBox').style.borderColor = u > 0 ? '#D2601A' : '#E2DCD3'
      $('upBox').style.background = u > 0 ? '#FFF7F0' : '#FAF9F6'
      $('upBtn').style.background = u >= 1 ? '#D2601A' : '#E2DCD3'

      // AI 분석 장면
      const an = cl((P - 0.63) / 0.14)
      const kx = cl((P - 0.62) / 0.1) * 100
      $('anPct').textContent = Math.round(an * 100) + '%'
      $('anBar').style.width = Math.round(an * 100) + '%'
      $('kpImg').style.clipPath = 'inset(0 ' + (100 - kx).toFixed(3) + '% 0 0)'
      $('kpLine').style.left = kx.toFixed(3) + '%'
      $('kpLine').style.opacity = kx > 0 && kx < 100 ? '1' : '0'
      document.querySelectorAll<HTMLElement>('.an-step').forEach((el, i) => {
        const done = an >= (i + 1) / 3 - 0.001
        const cur = !done && an >= i / 3
        el.textContent = (done ? '✓ ' : '') + el.dataset.n
        el.style.background = done ? '#FCEEE3' : cur ? '#1B2433' : '#F1EDE6'
        el.style.color = done ? '#A8481A' : cur ? '#fff' : '#7A808A'
      })

      // 리포트 장면: 카드를 위로 넘겨 본다
      const H = window.innerHeight * 0.7
      const repH = $('repCard').offsetHeight || 700
      $('repScroll').style.transform = 'translate(-50%,-' + (Math.max(0, repH - H + 60) * sm(0.86, 0.98)).toFixed(1) + 'px)'

      // 위쪽 문장: 지금 장면의 문장을 단어별로 칠한다
      const idx = Math.min(N - 1, Math.floor(P * N + 0.02))
      steps.forEach((st, i) => {
        const words = st.querySelectorAll<HTMLElement>('.sc-word')
        const a0 = bd(i) + (i ? 0.02 : 0.03)
        const p = cl((P - a0) / 0.13)
        st.style.opacity = i === idx ? '1' : '0'
        words.forEach((w, k) => {
          const dl = i === idx ? 120 + k * 55 : 0
          w.style.transition = 'color .3s ease,opacity .7s ease ' + dl + 'ms,transform .9s cubic-bezier(.2,.7,.2,1) ' + dl + 'ms'
          w.style.color = p * words.length > k + 0.3 ? '#1B2433' : '#D6D0C7'
          w.style.opacity = i === idx ? '1' : '0'
          w.style.transform = 'translateY(' + (i === idx ? 0 : i < idx ? -28 : 36) + 'px)'
        })
      })
    }

    let last = -1
    let raf = 0
    const frame = () => {
      const r = story.getBoundingClientRect()
      const tot = r.height - window.innerHeight
      const P = tot > 0 ? cl(-r.top / tot) : 0
      if (P !== last) {
        last = P
        apply(P)
      }
      raf = requestAnimationFrame(frame)
    }
    raf = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(raf)
  }, [])

  return (
    <Base acct={acct} me={me} nav="about" toast={toast} topbar={acct ? undefined : <GuestBar />}>
      <section style={css('max-width:none;margin:0;padding:88px 80px 96px;display:flex;flex-direction:column;gap:40px')}>
        <h2 style={css('margin:0;text-align:center;font-size:clamp(30px,3.4vw,44px);font-weight:800;letter-spacing:-1px;color:#D2601A')}>서비스 소개</h2>
        <div id="scStory" style={css('position:relative;height:1000vh;width:100vw;margin-left:calc(50% - 50vw)')}>
          <div id="scStage" style={css('position:sticky;top:0;height:100vh;overflow:hidden')}>
            <div style={css('position:absolute;top:0;right:0;bottom:0;left:0;border-radius:0;overflow:hidden;background:#EFE6DA')}>
              <div className="sc-layer" style={css('position:absolute;inset:0;clip-path:inset(0% 0 0 0);background:#EFE6DA')}>
                <div className="sc-scale" style={css('position:absolute;inset:0;transform-origin:50% 40%')}>
                  <img src={`${img}about-dogs.jpg`} alt="골든 리트리버, 비글, 포메라니안이 함께 걷는 모습" style={css('width:100%;height:100%;object-fit:cover;object-position:50% 65%;display:block')} />
                </div>
                <div className="sc-dark" style={css('position:absolute;inset:0;background:#1B2433;opacity:0;pointer-events:none')}></div>
              </div>
              <div className="sc-layer" style={css('position:absolute;inset:0;clip-path:inset(100% 0 0 0);background:#EFE6DA')}>
                <div className="sc-scale" style={css('position:absolute;inset:0;transform-origin:50% 40%')}>
                  <img src={`${img}about-shoot.jpg`} alt="휴대폰을 가로로 들고 걷는 리트리버를 촬영하는 보호자" style={css('width:100%;height:100%;object-fit:cover;object-position:50% 60%;display:block')} />
                </div>
                <div className="sc-dark" style={css('position:absolute;inset:0;background:#1B2433;opacity:0;pointer-events:none')}></div>
              </div>
              <div className="sc-layer" style={css('position:absolute;inset:0;clip-path:inset(100% 0 0 0);background:#F3EFE8')}>
                <div className="sc-scale" style={css('position:absolute;inset:0;transform-origin:50% 40%')}>
                  <div style={css('position:absolute;left:50%;top:62%;transform:translate(-50%,-50%);width:min(820px,92%);background:#fff;border:1px solid #ECE8E2;border-radius:24px;box-shadow:0 30px 70px -30px rgba(27,36,51,.3);padding:32px 36px;display:flex;flex-direction:column;gap:22px')}>
                    <b style={css('font-size:26px;letter-spacing:-0.6px')}>보행 영상 분석</b>
                    <div style={css('display:flex;flex-direction:column;gap:12px')}><b style={css('font-size:15px')}>1. 반려견 선택</b><div style={css('display:flex;gap:20px')}>
                      <div style={css('display:flex;flex-direction:column;align-items:center;gap:8px;width:92px;text-align:center')}><div style={css('width:68px;height:68px;border-radius:50%;background:#FCEEE3;color:#A8481A;display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:800;box-shadow:0 0 0 3px #fff,0 0 0 6px #D2601A')}>보</div><span style={css('font-size:14px;font-weight:700;color:#1B2433')}>보리</span><span style={css('font-size:12px;color:#7A808A')}>(골든 리트리버)</span></div>
                      <div style={css('display:flex;flex-direction:column;align-items:center;gap:8px;width:92px;text-align:center')}><div style={css('width:68px;height:68px;border-radius:50%;background:#EEEAE4;color:#7A808A;display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:800')}>콩</div><span style={css('font-size:14px;font-weight:500;color:#5B6472')}>콩이</span><span style={css('font-size:12px;color:#7A808A')}>(포메라니안)</span></div>
                      <div style={css('display:flex;flex-direction:column;align-items:center;gap:8px;width:92px;text-align:center')}><div style={css('width:68px;height:68px;border-radius:50%;background:#EEEAE4;color:#7A808A;display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:800')}>두</div><span style={css('font-size:14px;font-weight:500;color:#5B6472')}>두부</span><span style={css('font-size:12px;color:#7A808A')}>(비글)</span></div>
                      <div style={css('display:flex;flex-direction:column;align-items:center;gap:8px;width:92px;text-align:center')}><div style={css('width:68px;height:68px;border-radius:50%;background:#fff;border:2px dashed #D9D2C7;color:#D2601A;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:500')}>+</div><span style={css('font-size:14px;font-weight:700;color:#D2601A')}>등록</span></div>
                    </div></div>
                    <div style={css('display:flex;flex-direction:column;gap:12px')}><b style={css('font-size:15px')}>2. 영상 올리기</b>
                      <div id="upBox" style={css('border:2px dashed #E2DCD3;border-radius:16px;padding:22px;display:flex;align-items:center;gap:16px;background:#FAF9F6;transition:background .3s,border-color .3s')}>
                        <div id="upThumb" style={css('width:84px;height:56px;border-radius:10px;overflow:hidden;flex:none;background:#EEE2CE;opacity:0')}><img src={`${img}about-dogs.jpg`} alt="" style={css('width:100%;height:100%;object-fit:cover')} /></div>
                        <div style={css('flex:1;min-width:0;display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:15px;font-weight:700')}>bori_walk_1014.mp4</span><div style={css('height:6px;border-radius:3px;background:#F1E7D6')}><div id="upBar" style={css('height:100%;width:0%;border-radius:3px;background:#D2601A')}></div></div><span id="upTxt" style={css('font-size:13px;color:#5B6472;font-variant-numeric:tabular-nums')}>영상을 끌어다 놓거나 눌러서 선택</span></div>
                      </div>
                    </div>
                    <div id="upBtn" style={css('align-self:flex-end;width:220px;height:54px;border-radius:12px;background:#E2DCD3;color:#fff;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700;transition:background .3s')}>분석 시작</div>
                  </div>
                </div>
                <div className="sc-dark" style={css('position:absolute;inset:0;background:#1B2433;opacity:0;pointer-events:none')}></div>
              </div>
              <div className="sc-layer" style={css('position:absolute;inset:0;clip-path:inset(100% 0 0 0);background:#FAF9F6')}>
                <div className="sc-scale" style={css('position:absolute;inset:0;transform-origin:50% 40%')}>
                  <img src={`${img}about-keypoints.jpg`} alt="" style={css('position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 100%;filter:grayscale(1) blur(6px) brightness(1.08)')} />
                  <img id="kpImg" src={`${img}about-keypoints.jpg`} alt="관절점이 표시된 골든 리트리버" style={css('position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 100%;clip-path:inset(0 100% 0 0)')} />
                  <div id="kpLine" style={css('position:absolute;top:0;bottom:0;left:0%;width:3px;margin-left:-1.5px;background:#fff;box-shadow:0 0 24px 6px rgba(255,255,255,.85),0 0 70px 18px rgba(240,122,58,.45);opacity:0')}></div>
                  <div style={css('position:absolute;right:5%;bottom:6%;width:min(360px,86%);background:rgba(255,255,255,.94);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-radius:18px;box-shadow:0 20px 50px -20px rgba(27,36,51,.35);padding:20px 22px;display:flex;flex-direction:column;gap:12px')}>
                    <div style={css('display:flex;align-items:center;justify-content:space-between')}><b style={css('font-size:17px')}>분석 중입니다</b><b id="anPct" style={css('font-size:16px;color:#D2601A;font-variant-numeric:tabular-nums')}>0%</b></div>
                    <div style={css('height:6px;border-radius:3px;background:#FCEEE3')}><div id="anBar" style={css('height:100%;width:0%;border-radius:3px;background:#D2601A')}></div></div>
                    <div style={css('display:flex;gap:6px;flex-wrap:wrap')}>
                      {['영상 확인', '관절점 찾기', '각도 계산'].map((n) => <span key={n} className="an-step" data-n={n} style={css('height:28px;padding:0 10px;border-radius:14px;background:#F1EDE6;color:#7A808A;display:flex;align-items:center;font-size:12.5px;font-weight:600;transition:background .3s,color .3s')}>{n}</span>)}
                    </div>
                  </div>
                </div>
                <div className="sc-dark" style={css('position:absolute;inset:0;background:#1B2433;opacity:0;pointer-events:none')}></div>
              </div>
              <div className="sc-layer" style={css('position:absolute;inset:0;clip-path:inset(100% 0 0 0);background:#F3EFE8')}>
                <div className="sc-scale" style={css('position:absolute;inset:0;transform-origin:50% 40%')}>
                  <div style={css('position:absolute;left:0;right:0;top:30vh;bottom:0;overflow:hidden;-webkit-mask-image:linear-gradient(180deg,transparent 0,#000 28px);mask-image:linear-gradient(180deg,transparent 0,#000 28px)')}><div id="repScroll" style={css('position:absolute;left:50%;top:20px;transform:translate(-50%,0px);width:min(960px,92%);')}>
                    <div id="repCard" style={css('background:#fff;border-radius:16px;box-shadow:0 30px 70px -30px rgba(27,36,51,.35);padding:48px 52px 56px;display:flex;flex-direction:column;gap:26px;font-size:17px')}>
                      <div style={css('display:flex;align-items:center;justify-content:space-between')}><div style={css('display:flex;align-items:center;gap:8px;font-size:15px;font-weight:800')}><img src={`${img}logo.png`} alt="" style={css('width:26px;height:26px;object-fit:contain')} />Paw oh Paw</div><span style={css('font-size:13px;color:#5B6472')}>보행 분석 리포트</span></div>
                      <div style={css('height:3px;width:40px;background:#D2601A')}></div>
                      <div><div style={css('font-size:26px;font-weight:800;letter-spacing:-0.6px')}>보리의 걸음 리포트</div><div style={css('font-size:14px;color:#5B6472;margin-top:4px')}>10월 14일 측정 · 골든 리트리버 · 7살</div></div>
                      <div style={css('display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px')}>
                        <div style={css('background:#FAF6F0;border-radius:12px;padding:14px')}><div style={css('font-size:12.5px;color:#5B6472;font-weight:600')}>좌우 대칭</div><div style={css('font-size:26px;font-weight:800;margin-top:4px')}>92<span style={css('font-size:14px;color:#5B6472')}>%</span></div></div>
                        <div style={css('background:#FAF6F0;border-radius:12px;padding:14px')}><div style={css('font-size:12.5px;color:#5B6472;font-weight:600')}>뒷무릎 가동 범위</div><div style={css('font-size:26px;font-weight:800;margin-top:4px')}>48<span style={css('font-size:14px;color:#5B6472')}>°</span></div></div>
                        <div style={css('background:#FAF6F0;border-radius:12px;padding:14px')}><div style={css('font-size:12.5px;color:#5B6472;font-weight:600')}>보폭 왼 / 오</div><div style={css('font-size:26px;font-weight:800;margin-top:4px')}>41<span style={css('color:#A0A7B2;font-weight:500')}> / </span>38<span style={css('font-size:14px;color:#5B6472')}>cm</span></div></div>
                      </div>
                      <div style={css('border:1px solid #ECE8E2;border-radius:8px;overflow:hidden')}>
                        <div style={css(`${ROW};background:#1B2433;color:#fff;font-weight:700`)}><span style={css('padding:9px 12px')}>지표</span><span style={css('padding:9px 8px')}>왼쪽</span><span style={css('padding:9px 8px')}>오른쪽</span><span style={css('padding:9px 8px')}>차이</span></div>
                        <div style={css(`${ROW};background:#FAF8F5`)}><span style={css('padding:9px 12px;font-weight:600')}>무릎 ROM</span><span style={css('padding:9px 8px')}>66°</span><span style={css('padding:9px 8px')}>58°</span><span style={css('padding:9px 8px;font-weight:700')}>8°</span></div><div style={css(ROW)}><span style={css('padding:9px 12px;font-weight:600')}>고관절 ROM</span><span style={css('padding:9px 8px')}>44°</span><span style={css('padding:9px 8px')}>41°</span><span style={css('padding:9px 8px;font-weight:700')}>3°</span></div><div style={css(`${ROW};background:#FAF8F5`)}><span style={css('padding:9px 12px;font-weight:600')}>팔꿈치 ROM</span><span style={css('padding:9px 8px')}>52°</span><span style={css('padding:9px 8px')}>50°</span><span style={css('padding:9px 8px;font-weight:700')}>2°</span></div><div style={css(ROW)}><span style={css('padding:9px 12px;font-weight:600')}>보폭</span><span style={css('padding:9px 8px')}>41cm</span><span style={css('padding:9px 8px')}>38cm</span><span style={css('padding:9px 8px;font-weight:700')}>7%</span></div>
                      </div>
                      <div><b style={css('font-size:15px')}>뒷무릎 각도 · 보행 주기</b>{' '}
                        <svg viewBox="0 0 320 150" style={css('width:100%;display:block;margin-top:8px')}><g stroke="#ECE8E2" strokeDasharray="3 4"><line x1="24" y1="20" x2="310" y2="20"></line><line x1="24" y1="75" x2="310" y2="75"></line><line x1="24" y1="130" x2="310" y2="130"></line></g><polyline id="kL" fill="none" stroke="#3B6FE0" strokeWidth="2.5"></polyline><polyline id="kR" fill="none" stroke="#E5604D" strokeWidth="2.5" strokeDasharray="6 5"></polyline></svg>
                      </div>
                    </div>
                  </div></div>
                </div>
                <div className="sc-dark" style={css('position:absolute;inset:0;background:#1B2433;opacity:0;pointer-events:none')}></div>
              </div>
            </div>

            <div style={css('position:absolute;top:calc(74px + 4vh);left:5%;width:90%')}>
              <div style={css('position:relative;min-height:120px;text-align:center')}>
                {STEPS.map(([tag, txt], si) => (
                  <div key={tag} className="sc-step" style={css(`position:absolute;left:0;right:0;top:0;display:flex;flex-direction:column;align-items:center;gap:12px;opacity:${si === 0 ? 1 : 0};transition:opacity .6s ease;pointer-events:none`)}>
                    <p style={css('margin:0;font-size:clamp(24px,2.8vw,44px);line-height:1.3;font-weight:800;letter-spacing:-1.4px;display:flex;flex-wrap:wrap;justify-content:center;column-gap:.28em')}>
                      {/* loop.first 는 안쪽(단어) 반복의 첫 단어 */}
                      {txt.split(' ').map((w, wi) => <span key={wi} className="sc-word" style={css(`display:inline-block;color:#D6D0C7;opacity:${wi === 0 ? 1 : 0};transform:translateY(36px);transition:color .3s ease,opacity .7s ease 0ms,transform .9s cubic-bezier(.2,.7,.2,1) 0ms`)}>{w}</span>)}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
        <div style={css('display:flex;justify-content:center;padding-top:8px')}><a className="lk hv-orange" href={acct ? '/upload' : '/signup'} style={css('height:56px;padding:0 28px;border-radius:14px;background:#D2601A;color:#fff;display:flex;align-items:center;gap:8px;font-size:17px;font-weight:700')}>{acct ? '보행 분석 시작하기' : '지금 시작하기'}<svg width="18" height="18" viewBox="0 0 24 24"><use href="#w-chev"></use></svg></a></div>
      </section>
    </Base>
  )
}
