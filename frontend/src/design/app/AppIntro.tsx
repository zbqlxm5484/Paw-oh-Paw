// 앱 서비스 소개(소개 탭·/intro). 웹 서비스 소개(web/src/pages/About.tsx)와 같은 이야기를 폰에서 세로 스크롤로 읽게 한 것.
// 첫 화면 영상(한 줄 소개만) → 어떻게 재나 → 소형~대형견 → 진료 차트 → 보고서 → 3D(웹) → 데이터 원칙 → 시작 버튼.
// 그림은 앱 체험 모드 화면을 캡처한 것(public/assets/intro). 움직임은 스크롤하면 살짝 떠오르는 정도만 둔다.
import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react'

const INK = '#1B2433', SUB = '#5B6472', LINE = '#ECE8E2', ORANGE = '#D2601A', CREAM = '#FAF6F0'
const IMG = '/assets/intro/'

export interface IntroProps {
  showBack: boolean
  back: () => void
  titlePad: number
  bottom: number
  /** 맨 아래 큰 버튼(로그인했으면 보행 분석, 아니면 시작하기) */
  cta: { label: string; go: () => void }
  /** 로그인 안 했을 때만: 로그인 링크 */
  login?: () => void
}

/** 화면에 들어오면 아래에서 살짝 떠오른다 */
function Reveal({ children, delay = 0, style }: { children: ReactNode; delay?: number; style?: CSSProperties }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver((es) => {
      for (const e of es) if (e.isIntersecting) { el.style.opacity = '1'; el.style.transform = 'none'; io.disconnect() }
    }, { threshold: 0.15 })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return <div ref={ref} style={{ opacity: 0, transform: 'translateY(24px)', transition: `opacity .6s ease ${delay}ms, transform .6s ease ${delay}ms`, ...style }}>{children}</div>
}

/** 갤럭시 S(울트라) 모양 폰 틀에 넣은 앱 화면 캡처(위쪽만 보이게 자른다): 각진 모서리·얇고 고른 베젤·티타늄 테두리·가운데 펀치홀·오른쪽 측면 버튼 */
function Phone({ src, h = 440 }: { src: string; h?: number }) {
  const key = (top: string, len: string): CSSProperties => ({ position: 'absolute', right: -3, top, width: 3, height: len, borderRadius: '0 2px 2px 0', background: '#8A8F96' })
  return (
    <div style={{ position: 'relative', width: '47%', maxWidth: 220, aspectRatio: `220 / ${h}`, flex: 'none' }}>
      <span style={key('18%', '16%')} />
      <span style={key('38%', '8%')} />
      <div style={{ position: 'absolute', inset: 0, borderRadius: 12, padding: 4, background: 'linear-gradient(135deg,#9AA0A6 0%,#4A4F55 18%,#2B2E33 50%,#4A4F55 82%,#9AA0A6 100%)', boxShadow: '0 18px 40px rgba(27,36,51,.18)' }}>
        <div style={{ position: 'relative', width: '100%', height: '100%', borderRadius: 9, overflow: 'hidden', background: '#FAF9F6', boxShadow: '0 0 0 2px #0B0D10' }}>
          <img src={IMG + src} alt="" loading="lazy" style={{ width: '100%', display: 'block', marginTop: 14 }} />
          <span style={{ position: 'absolute', top: 5, left: '50%', width: 7, height: 7, marginLeft: -3.5, borderRadius: '50%', background: '#0B0D10' }} />
        </div>
      </div>
    </div>
  )
}

/** one: 제목을 한 줄로(폰 폭에 맞춰 글자 크기를 줄인다) */
function Head({ k, t, p, one }: { k: string; t: ReactNode; p: ReactNode; one?: boolean }) {
  return (
    <Reveal style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <span style={{ fontSize: 13, fontWeight: 700, color: ORANGE, letterSpacing: '.2px' }}>{k}</span>
      <b style={{ fontSize: one ? 'min(22px, 6vw)' : 22, lineHeight: 1.32, letterSpacing: '-0.6px', color: INK , whiteSpace: one ? 'nowrap' : undefined }}>{t}</b>
      <span style={{ fontSize: 15, lineHeight: 1.6, color: SUB }}>{p}</span>
    </Reveal>
  )
}

const sec: CSSProperties = { padding: '56px 24px', display: 'flex', flexDirection: 'column', gap: 28 }

const STEPS: [string, string, string][] = [
  ['1', '옆모습을 찍습니다', '휴대폰을 가로로 들고, 걷는 방향과 직각으로 4초씩 찍습니다.'],
  ['2', '관절점을 따라갑니다', '프레임마다 22개 관절점을 찾아 다리마다 각도와 걸음을 잽니다.'],
  ['3', '숫자로 정리합니다', '쓴 걸음만 모아 관절 가동 범위·걸음 길이·좌우 대칭 점수를 냅니다.'],
]
const TRUST: [string, string][] = [
  ['측정 품질 공개', '쓴 걸음과 뺀 걸음, 뺀 이유를 그대로 보여 줍니다.'],
  ['기관별 분리', '다른 기관의 자료는 서로 볼 수 없습니다.'],
  ['암호화', '전송은 HTTPS, 비밀번호는 복호화할 수 없게 저장합니다.'],
  ['보관과 삭제', '계약 기간 동안 보관하고, 지운 자료는 30일 뒤 영구 삭제합니다.'],
]

export function IntroBody({ i }: { i: IntroProps }) {
  return (
    <div style={{ position: 'absolute', inset: 0, padding: `36px 0 ${i.bottom}px`, display: 'flex', flexDirection: 'column', background: CREAM }}>
      <div style={{ flex: 'none', height: 56, display: 'flex', alignItems: 'center', padding: '0 20px 0 8px' }}>
        {i.showBack ? <div onClick={i.back} style={{ width: 44, height: 44, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}><svg width="24" height="24" viewBox="0 0 24 24"><use href="#i-back"></use></svg></div> : null}
        <b style={{ fontSize: 18, paddingLeft: i.titlePad }}>서비스 소개</b>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }} className="pp-s">
        {/* 1. 첫 화면: 걷는 영상 + 한 줄 소개(큰 제목은 두지 않는다) */}
        <div style={{ position: 'relative', height: 420, margin: '0 16px', borderRadius: 24, overflow: 'hidden', background: '#E9E4DC' }}>
          <video src="/assets/landing.mp4" poster="/assets/landing-poster.webp" autoPlay muted loop playsInline preload="auto" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
          <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg,rgba(27,36,51,0) 70%,rgba(27,36,51,.5) 100%)' }} />
          <span style={{ position: 'absolute', left: 22, right: 22, bottom: 20, color: '#fff', fontSize: 15, fontWeight: 600 }}>동물병원·재활센터를 위한 보행 분석</span>
        </div>

        {/* 2. 어떻게 재나 */}
        <div style={sec}>
          <Head k="어떻게 재나요" t={<>관절점을 프레임마다<br />추적합니다</>} p="특별한 장비 없이 휴대폰으로 찍은 영상만 있으면 됩니다." />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {STEPS.map(([n, h, p], k) => (
              <Reveal key={n} delay={k * 80} style={{ display: 'flex', gap: 14, alignItems: 'flex-start', background: '#fff', border: `1px solid ${LINE}`, borderRadius: 18, padding: '16px 16px' }}>
                <span style={{ width: 30, height: 30, flex: 'none', borderRadius: 15, background: '#FCEEE3', color: ORANGE, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 14 }}>{n}</span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}><b style={{ fontSize: 15 }}>{h}</b><span style={{ fontSize: 14, lineHeight: 1.55, color: SUB }}>{p}</span></div>
              </Reveal>
            ))}
          </div>
        </div>

        {/* 3. 체급 */}
        <div style={{ ...sec, background: '#F3EBE0' }}>
          <Head k="체급" t="소형견부터 대형견까지" p="몸집이 다른 강아지도 같은 방법으로 찍고 잽니다." />
          <Reveal style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8, alignItems: 'end' }}>
            {[['dog-small.webp', '소형', 64], ['dog-medium.webp', '중형', 82], ['dog-large.webp', '대형', 100]].map(([src, label, w]) => (
              <div key={label as string} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                <img src={IMG + src} alt="" loading="lazy" style={{ width: `${w}%`, display: 'block' }} />
                <b style={{ fontSize: 14, color: SUB }}>{label}</b>
              </div>
            ))}
          </Reveal>
        </div>

        {/* 4. 진료 차트 */}
        <div style={sec}>
          <Head k="진료 차트" t="진료 차트처럼 익숙하게" p="오늘 진행한 반려견, 재촬영이 필요한 반려견을 홈에서 바로 봅니다. 반려견 차트에는 바이탈과 진단·수술 이력, 측정 이력이 한곳에 있습니다." />
          <Reveal style={{ display: 'flex', justifyContent: 'center', gap: 10 }}>
            <Phone src="home.webp" h={420} />
            <Phone src="dog.webp" h={420} />
          </Reveal>
        </div>

        {/* 5. 보고서 */}
        <div style={{ ...sec, background: '#F3EDE4' }}>
          <Head k="보고서" one t="보호자용과 수의사용을 따로 만듭니다" p="보호자용은 주요 결과 한 줄과 그림으로, 수의사용은 관절별 수치로 정리합니다. 보고서 탭에서 반려견별로 모아 보고 PDF로 바로 저장합니다." />
          <Reveal style={{ display: 'flex', justifyContent: 'center', gap: 10 }}>
            <Phone src="report.webp" h={440} />
            <Phone src="reports.webp" h={440} />
          </Reveal>
        </div>

        {/* 6. 경과 비교·3D */}
        <div style={sec}>
          <Head k="경과 비교 · 3D" t="경과 비교부터 3D 모델까지" p="기준 회차나 직전 회차와 나란히 놓고 무엇이 좋아졌는지 봅니다. 회차 결과에서 3D 보기를 누르면 측정한 수치로 다시 걷는 3D 모델을 손가락으로 돌려 볼 수 있습니다." />
          <Reveal>
            <div style={{ borderRadius: 18, overflow: 'hidden', border: `1px solid ${LINE}`, background: '#fff' }}>
              <img src={IMG + '3d.webp'} alt="" loading="lazy" style={{ width: '100%', display: 'block' }} />
            </div>
          </Reveal>
        </div>

        {/* 7. 데이터 원칙 */}
        <div style={{ ...sec, background: '#fff' }}>
          <Head k="데이터" t="숨기지 않고, 섞지 않고, 지웁니다" p="" />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            {TRUST.map(([h, p], k) => (
              <Reveal key={h} delay={k * 70} style={{ background: CREAM, borderRadius: 16, padding: '16px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                <b style={{ fontSize: 15 }}>{h}</b><span style={{ fontSize: 13, lineHeight: 1.5, color: SUB }}>{p}</span>
              </Reveal>
            ))}
          </div>
        </div>

        {/* 8. 마무리 */}
        <div style={{ padding: '64px 24px 48px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18, textAlign: 'center' }}>
          <Reveal><b style={{ fontSize: 22, lineHeight: 1.4, letterSpacing: '-0.5px' }}>분석은 수의사의 판단을 돕습니다.</b></Reveal>
          <Reveal delay={100} style={{ width: '100%' }}>
            <div onClick={i.cta.go} style={{ height: 56, borderRadius: 16, background: ORANGE, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontSize: 18, fontWeight: 700, cursor: 'pointer' }}>{i.cta.label}<svg width="18" height="18" viewBox="0 0 24 24"><use href="#i-chev"></use></svg></div>
          </Reveal>
          {i.login ? <span onClick={i.login} style={{ fontSize: 14, color: SUB, cursor: 'pointer', padding: '0 6px', lineHeight: '44px', margin: '-8px 0', display: 'inline-block' }}>이미 계정이 있으면 <b style={{ color: INK }}>로그인</b></span> : null}
        </div>
      </div>
    </div>
  )
}
