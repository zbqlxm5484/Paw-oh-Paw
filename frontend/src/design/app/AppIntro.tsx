// 앱 서비스 소개(소개 탭·/intro). 웹 서비스 소개(web/src/pages/About.tsx)와 같은 이야기를 폰에서 세로 스크롤로 읽게 한 것.
// 첫 화면 영상(글자 없음) → 어떻게 재나 → 소형~대형견 → 진료 차트 → 보고서 → 3D(웹) → 데이터 원칙 → 시작 버튼.
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

/** 폰 틀에 넣은 앱 화면 캡처(위쪽만 보이게 자른다) */
function Phone({ src, h = 440 }: { src: string; h?: number }) {
  return (
    <div style={{ width: '47%', maxWidth: 220, aspectRatio: `220 / ${h}`, borderRadius: 26, padding: 6, background: '#1B2433', boxShadow: '0 18px 40px rgba(27,36,51,.18)', flex: 'none' }}>
      <div style={{ width: '100%', height: '100%', borderRadius: 20, overflow: 'hidden', background: '#FAF9F6' }}>
        <img src={IMG + src} alt="" loading="lazy" style={{ width: '100%', display: 'block' }} />
      </div>
    </div>
  )
}

function Head({ k, t, p }: { k: string; t: ReactNode; p: ReactNode }) {
  return (
    <Reveal style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <span style={{ fontSize: 13, fontWeight: 700, color: ORANGE, letterSpacing: '.2px' }}>{k}</span>
      <b style={{ fontSize: 25, lineHeight: 1.32, letterSpacing: '-0.6px', color: INK }}>{t}</b>
      <span style={{ fontSize: 15, lineHeight: 1.6, color: SUB }}>{p}</span>
    </Reveal>
  )
}

const sec: CSSProperties = { padding: '56px 24px', display: 'flex', flexDirection: 'column', gap: 28 }

const STEPS: [string, string, string][] = [
  ['1', '옆모습을 찍습니다', '휴대폰을 가로로 들고, 걷는 방향과 직각으로 4초씩 찍습니다.'],
  ['2', '관절점을 따라갑니다', '프레임마다 22개 관절점을 찾아 다리마다 각도와 걸음을 잽니다.'],
  ['3', '숫자로 정리합니다', '쓴 걸음만 모아 관절 가동 범위·걸음 길이·좌우 대칭 지수를 냅니다.'],
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
        {/* 1. 첫 화면: 걷는 영상만(글자 없음) */}
        <div style={{ position: 'relative', height: 420, margin: '0 16px', borderRadius: 24, overflow: 'hidden', background: '#E9E4DC' }}>
          <video src="/assets/landing.mp4" poster="/assets/landing-poster.webp" autoPlay muted loop playsInline preload="auto" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>

        {/* 2. 어떻게 재나 */}
        <div style={sec}>
          <Head k="어떻게 재나요" t={<>관절점을 프레임마다<br />추적합니다</>} p="특별한 장비 없이 휴대폰으로 찍은 영상만 있으면 됩니다." />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {STEPS.map(([n, h, p], k) => (
              <Reveal key={n} delay={k * 80} style={{ display: 'flex', gap: 14, alignItems: 'flex-start', background: '#fff', border: `1px solid ${LINE}`, borderRadius: 18, padding: '16px 16px' }}>
                <span style={{ width: 30, height: 30, flex: 'none', borderRadius: 15, background: '#FCEEE3', color: ORANGE, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 14 }}>{n}</span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}><b style={{ fontSize: 16 }}>{h}</b><span style={{ fontSize: 14, lineHeight: 1.55, color: SUB }}>{p}</span></div>
              </Reveal>
            ))}
          </div>
          <Reveal style={{ display: 'flex', justifyContent: 'center', gap: 10 }}>
            <Phone src="capture.webp" h={400} />
            <Phone src="result.webp" h={400} />
          </Reveal>
        </div>

        {/* 3. 체급 */}
        <div style={{ ...sec, background: '#F3EBE0' }}>
          <Head k="체급" t="소형견부터 대형견까지" p="몸집이 다른 강아지도 같은 방법으로 찍고 잽니다. 체급을 함께 기록해 같은 체급끼리 비교할 수 있습니다." />
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
          <Head k="보고서" t={<>보호자용과 수의사용을<br />따로 만듭니다</>} p="보호자용은 주요 결과 한 줄과 그림으로, 수의사용은 관절별 수치로 정리합니다. 보고서 탭에서 반려견별로 모아 보고 PDF로 바로 저장합니다." />
          <Reveal style={{ display: 'flex', justifyContent: 'center', gap: 10 }}>
            <Phone src="report.webp" h={440} />
            <Phone src="reports.webp" h={440} />
          </Reveal>
        </div>

        {/* 6. 경과 비교·3D */}
        <div style={sec}>
          <Head k="경과 비교 · 3D" t="경과 비교부터 3D 모델까지" p="기준 회차나 직전 회차와 나란히 놓고 무엇이 좋아졌는지 봅니다. 웹에서는 측정한 수치로 다시 걷는 3D 모델도 볼 수 있습니다." />
          <Reveal>
            <div style={{ borderRadius: 18, overflow: 'hidden', border: `1px solid ${LINE}`, background: '#fff' }}>
              <img src={IMG + '3d.webp'} alt="" loading="lazy" style={{ width: '100%', display: 'block' }} />
            </div>
            <span style={{ display: 'block', marginTop: 8, fontSize: 12.5, color: '#8E949C', textAlign: 'center' }}>3D 모델은 웹에서 볼 수 있습니다</span>
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
          <Reveal><b style={{ fontSize: 23, lineHeight: 1.4, letterSpacing: '-0.5px' }}>분석은 수의사의 판단을 돕습니다.</b></Reveal>
          <Reveal delay={100} style={{ width: '100%' }}>
            <div onClick={i.cta.go} style={{ height: 56, borderRadius: 16, background: ORANGE, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontSize: 17, fontWeight: 700, cursor: 'pointer' }}>{i.cta.label}<svg width="18" height="18" viewBox="0 0 24 24"><use href="#i-chev"></use></svg></div>
          </Reveal>
          {i.login ? <span onClick={i.login} style={{ fontSize: 14, color: SUB, cursor: 'pointer', padding: 6 }}>이미 계정이 있으면 <b style={{ color: INK }}>로그인</b></span> : null}
        </div>
      </div>
    </div>
  )
}
