import { useEffect, useRef, useState } from 'react'

import { Icon } from '../../components/Icon'

/**
 * 웹 v2 "서비스 소개" 스크롤 스테이지. 긴 트랙(500vh)을 내리면 고정된 무대 위에 다섯 장면이 위에서부터 차례로 덮인다.
 * 1 여러 견종이 걷는 사진 → 2 촬영 사진 → 3 영상 올리기 화면 → 4 관절점 분석 → 5 보고서.
 */
const STEPS = [
  { words: ['견종과', '체격이', '달라도', '같은', '기준으로'], dark: false },
  { words: ['휴대폰으로', '걷는', '옆모습을', '찍고'], dark: false },
  { words: ['영상을', '올리면', '분석이', '시작돼요'], dark: true },
  { words: ['AI가', '관절점을', '찾아', '보행을', '계산하고'], dark: false },
  { words: ['보고서로', '정리해', 'PDF로', '드려요'], dark: true },
]

export function IntroStage({ ctaLabel, onCta }: { ctaLabel: string; onCta: () => void }) {
  const trackRef = useRef<HTMLDivElement>(null)
  const [p, setP] = useState(0)

  useEffect(() => {
    let raf = 0
    const onScroll = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const el = trackRef.current
        if (!el) return
        const r = el.getBoundingClientRect()
        const total = r.height - window.innerHeight
        const v = total > 0 ? Math.min(1, Math.max(0, -r.top / total)) : 0
        setP(v)
      })
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      cancelAnimationFrame(raf)
    }
  }, [])

  const N = STEPS.length
  const seg = 1 / N
  // 장면 i 가 덮이는 정도(0: 아직, 1: 다 덮임). 장면 0 은 처음부터 보인다
  const cover = (i: number) => (i === 0 ? 1 : Math.min(1, Math.max(0, (p - (i - 1) * seg - seg * 0.25) / (seg * 0.6))))
  const active = Math.min(N - 1, Math.floor(p / seg + 0.001))
  const upP = Math.round(Math.min(1, Math.max(0, (p - 2 * seg) / (seg * 0.7))) * 100)
  const anP = Math.round(Math.min(1, Math.max(0, (p - 3 * seg) / (seg * 0.7))) * 100)
  const kx = 8 + anP * 0.84

  return (
    <section className="wl-intro">
      <h2>서비스 소개</h2>
      <div className="sc-track" ref={trackRef}>
        <div className="sc-stage">
          <div className="sc-frame">
            {/* 1 견종 */}
            <div className="sc-layer" style={{ clipPath: `inset(${(1 - cover(0)) * 100}% 0 0 0)` }}>
              <img src="/assets/about-breeds.webp" alt="골든 리트리버, 비글, 포메라니안이 함께 걷는 모습" style={{ objectPosition: '50% 65%' }} />
              <div className="dim" style={{ opacity: Math.min(0.55, cover(1) * 0.55) }} />
            </div>
            {/* 2 촬영 */}
            <div className="sc-layer" style={{ clipPath: `inset(${(1 - cover(1)) * 100}% 0 0 0)` }}>
              <img src="/assets/about-film.webp" alt="휴대폰을 가로로 들고 걷는 리트리버를 촬영하는 보호자" style={{ objectPosition: '50% 60%' }} />
              <div className="dim" style={{ opacity: Math.min(0.55, cover(2) * 0.55) }} />
            </div>
            {/* 3 업로드 화면 */}
            <div className="sc-layer" style={{ clipPath: `inset(${(1 - cover(2)) * 100}% 0 0 0)`, background: '#F3EFE8' }}>
              <div className="sc-panel">
                <b style={{ fontSize: 22, letterSpacing: -0.5 }}>보행 영상 분석</b>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <b style={{ fontSize: 15 }}>1. 반려견 선택</b>
                  <div style={{ display: 'flex', gap: 20 }}>
                    {['보', '콩', '두'].map((c, i) => (
                      <div key={c} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, width: 92, textAlign: 'center' }}>
                        <div className="av" style={{ width: 68, height: 68, borderRadius: '50%', background: 'var(--pri-l)', color: 'var(--pri-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, fontWeight: 800, boxShadow: i === 0 ? '0 0 0 3px #fff, 0 0 0 6px var(--pri)' : 'none' }}>
                          {c}
                        </div>
                        <span style={{ fontSize: 14, fontWeight: i === 0 ? 800 : 600, color: i === 0 ? 'var(--ink)' : 'var(--sub)' }}>{['보리', '콩이', '두부'][i]}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <b style={{ fontSize: 15 }}>2. 영상 올리기</b>
                  <div style={{ border: `2px dashed ${upP > 0 ? 'var(--pri)' : '#D9D2C7'}`, borderRadius: 16, padding: 22, display: 'flex', alignItems: 'center', gap: 16, background: upP > 0 ? 'var(--pri-l)' : '#fff', transition: 'background .3s, border-color .3s' }}>
                    <div style={{ width: 84, height: 56, borderRadius: 10, overflow: 'hidden', flex: 'none', background: '#EEE2CE', opacity: upP > 0 ? 1 : 0.4 }}>
                      <img src="/assets/about-film.webp" alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <span style={{ fontSize: 15, fontWeight: 700 }}>bori_walk_1014.mp4</span>
                      <div style={{ height: 6, borderRadius: 3, background: '#F1E7D6' }}>
                        <div style={{ height: '100%', width: `${upP}%`, borderRadius: 3, background: 'var(--pri)' }} />
                      </div>
                      <span className="tabular" style={{ fontSize: 13, color: 'var(--sub)' }}>
                        {upP >= 100 ? '업로드 완료' : upP > 0 ? `올리는 중 ${upP}%` : '영상을 끌어다 놓거나 눌러서 선택'}
                      </span>
                    </div>
                  </div>
                </div>
                <div style={{ alignSelf: 'flex-end', width: 220, height: 54, borderRadius: 12, background: upP >= 100 ? 'var(--pri)' : 'var(--disabled)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, fontWeight: 700, transition: 'background .3s' }}>
                  분석 시작
                </div>
              </div>
              <div className="dim" style={{ opacity: Math.min(0.55, cover(3) * 0.55) }} />
            </div>
            {/* 4 관절점 분석 */}
            <div className="sc-layer" style={{ clipPath: `inset(${(1 - cover(3)) * 100}% 0 0 0)`, background: '#FAF9F6' }}>
              <img src="/assets/about-kp.webp" alt="" style={{ position: 'absolute', inset: 0, objectPosition: '50% 100%', filter: 'grayscale(1) blur(6px) brightness(1.08)' }} />
              <img src="/assets/about-kp.webp" alt="관절점이 표시된 골든 리트리버" style={{ position: 'absolute', inset: 0, objectPosition: '50% 100%', clipPath: `inset(0 ${100 - kx}% 0 0)` }} />
              <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${kx}%`, width: 3, marginLeft: -1.5, background: '#fff', boxShadow: '0 0 24px 6px rgba(255,255,255,.85), 0 0 70px 18px rgba(240,122,58,.45)', opacity: anP > 0 && anP < 100 ? 1 : 0 }} />
              <div className="sc-analyze">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <b style={{ fontSize: 16 }}>분석 중입니다</b>
                  <b className="tabular" style={{ fontSize: 16, color: 'var(--pri)' }}>
                    {anP}%
                  </b>
                </div>
                <div style={{ height: 6, borderRadius: 3, background: '#F1E7D6' }}>
                  <div style={{ height: '100%', width: `${anP}%`, borderRadius: 3, background: 'var(--pri)' }} />
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {['반려견 찾는 중', '관절점 찾는 중', '보행 수치 계산 중', '보고서 만드는 중'].map((t, i) => {
                    const on = anP >= (i + 1) * 25
                    return (
                      <span key={t} style={{ height: 28, padding: '0 10px', borderRadius: 14, background: on ? 'var(--ink)' : 'var(--fill)', color: on ? '#fff' : 'var(--sub)', display: 'flex', alignItems: 'center', fontSize: 12.5, fontWeight: 600, transition: 'background .3s, color .3s' }}>
                        {t}
                      </span>
                    )
                  })}
                </div>
              </div>
              <div className="dim" style={{ opacity: Math.min(0.55, cover(4) * 0.55) }} />
            </div>
            {/* 5 보고서 */}
            <div className="sc-layer" style={{ clipPath: `inset(${(1 - cover(4)) * 100}% 0 0 0)`, background: '#F3EFE8' }}>
              <div className="sc-report">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 15, fontWeight: 800 }}>
                    <img src="/assets/logo-joint.png" alt="" style={{ width: 24, height: 24, objectFit: 'contain' }} />
                    Paw oh Paw
                  </div>
                  <span style={{ fontSize: 13, color: 'var(--sub)' }}>보행 분석 리포트</span>
                </div>
                <div style={{ height: 3, width: 56, background: 'var(--pri)' }} />
                <div>
                  <div style={{ fontSize: 30, fontWeight: 800, letterSpacing: -0.8 }}>보리의 걸음 리포트</div>
                  <div style={{ fontSize: 14, color: 'var(--sub)', marginTop: 4 }}>10월 14일 측정 · 골든 리트리버 · 7살</div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10 }}>
                  {[
                    ['좌우 차이 지수', '11.3', '%'],
                    ['뒷무릎 가동 범위', '48', '°'],
                    ['걸음 길이 왼 / 오', '54 / 52', '%'],
                  ].map(([k, v, u]) => (
                    <div key={k} style={{ background: '#FAF6F0', borderRadius: 14, padding: 18 }}>
                      <div style={{ fontSize: 12.5, color: 'var(--sub)', fontWeight: 600 }}>{k}</div>
                      <div className="tabular" style={{ fontSize: 26, fontWeight: 800, marginTop: 4 }}>
                        {v}
                        <span style={{ fontSize: 14, color: 'var(--sub)' }}>{u}</span>
                      </div>
                    </div>
                  ))}
                </div>
                <span style={{ fontSize: 12, color: 'var(--dim)' }}>보행 평가 보조 자료이며 진단을 대신하지 않습니다.</span>
              </div>
            </div>
          </div>
          {STEPS.map((st, i) => (
            <div key={i} className="sc-caption" style={{ opacity: active === i ? 1 : 0 }}>
              <p className={st.dark ? 'dark' : ''}>
                {st.words.map((w, j) => (
                  <span key={j} style={{ display: 'inline-block', marginRight: '0.28em', opacity: active === i ? 1 : 0, transform: active === i ? 'none' : 'translateY(14px)', transition: `opacity .7s ease ${j * 90}ms, transform .9s cubic-bezier(.2,.7,.2,1) ${j * 90}ms` }}>
                    {w}
                  </span>
                ))}
              </p>
            </div>
          ))}
        </div>
      </div>
      <div className="wl-intro-cta">
        <button type="button" className="web-btn pri lg" onClick={onCta}>
          {ctaLabel}
          <Icon name="chev" size={18} />
        </button>
      </div>
      <span style={{ textAlign: 'center', fontSize: 13, color: 'var(--dim2)' }}>보행 평가 보조 자료이며 진단을 대신하지 않습니다.</span>
    </section>
  )
}
