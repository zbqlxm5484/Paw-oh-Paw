// 서비스 소개. 화면을 고정(pin)한 장면 안에서 스크롤 위치에 맞춰 요소가 움직인다(GSAP ScrollTrigger, scrub).
// 구조: 사진·화면이 화면을 거의 채우고 글자는 그 위(왼쪽 위)에 얹힌다. 다음 장면은 이전 장면 위로 덮으며 올라온다.
// 간격 토큰 12 / 24 / 40 / 64 만 쓰고, 글자 위계는 라벨(15/700) → 제목(28~44/700/-0.03em) → 본문(16~19/500) 세 단계다.
import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { staticUrl, usePage, useTitle } from '../app/page'
import { link } from '../config'

gsap.registerPlugin(ScrollTrigger)

const INK = '#191F28', INK2 = '#4E5968', INK3 = '#6B7684', ORANGE = '#D2601A', PAPER = '#FAF9F6', CREAM = '#F0E4D8'
const T = {
  hero: `margin:0;font-size:clamp(42px,5vw,66px);line-height:1.25;font-weight:700;letter-spacing:-0.02em;color:${INK};text-wrap:balance`,
  h2: `margin:0;font-size:clamp(30px,3.2vw,46px);line-height:1.3;font-weight:600;letter-spacing:-0.02em;color:${INK};text-wrap:balance;word-break:keep-all`,
  sub: `margin:0;font-size:clamp(16px,1.25vw,19px);line-height:1.6;font-weight:400;letter-spacing:-0.01em;color:${INK2};text-wrap:pretty;word-break:keep-all`,
  label: `margin:0;font-size:15px;line-height:1.4;font-weight:700;letter-spacing:-0.01em;color:${ORANGE}`,
}
// 고정 장면의 스크럽 길이(vh). 이 길이만큼 아래 여백을 두고, 그 뒤 100vh 동안 다음 장면이 위로 덮는다
const LEN: Record<string, number> = { 's-intro': 156, 's-size': 728, 's-emr': 770, 's-rep': 1550 }
const SCENE = 'position:relative;height:100vh;height:100dvh;overflow:hidden'
const sceneStyle = (id: string, z: number, extra = '') => css(`${SCENE};z-index:${z};margin-bottom:${LEN[id]}vh;${extra}`)
// 사진 위에 얹는 글 블록(왼쪽 위)
const OVER = 'position:absolute;left:40px;top:calc(68px + 24px);width:min(560px,calc(100% - 128px));display:flex;flex-direction:column;gap:12px;z-index:3'
// 왼쪽 글 + 오른쪽 화면 캡처 장면의 격자
// 가운데 정렬 장면: 머리글(라벨+제목) 한 덩어리가 위 가운데, 그 아래 남은 높이를 매체가 채운다
const HEAD_C = 'position:absolute;top:calc(68px + 24px);left:32px;right:32px;display:flex;flex-direction:column;align-items:center;gap:10px;text-align:center;z-index:3'
const MEDIA_C = 'position:absolute;top:calc(68px + 24px + 76px);left:32px;right:32px;bottom:32px;display:flex;align-items:center;justify-content:center'

// 로그인 전 상단 바. 맨 위에서만 보인다
function GuestBar({ loggedIn }: { loggedIn: boolean }) {
  return (
    <header id="ab-bar" style={css('position:fixed;top:0;left:0;right:0;z-index:50;transition:opacity .25s ease,transform .25s ease')}>
      <div style={css('height:68px;padding:0 40px;display:flex;align-items:center;justify-content:space-between;gap:16px')}>
        <a className="lk" href={link('/')} style={css(`display:flex;align-items:center;gap:8px;font-size:18px;font-weight:800;letter-spacing:-0.4px;color:${INK}`)}><img src={staticUrl('assets/logo.png')} alt="" style={css('width:30px;height:30px;object-fit:contain')} />Paw oh Paw</a>
        <nav style={css('display:flex;align-items:center;gap:6px')}>
          {loggedIn ? (
            <a className="lk" href={link('/home')} style={css(`height:40px;padding:0 16px;border-radius:10px;background:${INK};color:#fff;display:flex;align-items:center;font-size:15px;font-weight:700`)}>홈으로</a>
          ) : (
            <>
              <a className="lk" href={link('/login')} style={css(`height:40px;padding:0 14px;display:flex;align-items:center;font-size:15px;font-weight:600;color:${INK}`)}>로그인</a>
              <a className="lk" href={link('/signup')} style={css(`height:40px;padding:0 16px;border-radius:10px;background:${INK};color:#fff;display:flex;align-items:center;font-size:15px;font-weight:700`)}>회원가입</a>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}

// 체급 장면: 파일, 라벨, 기준, (예전 x 자리, 안 씀), 키(vh)
const DOGS: [string, string, string, number, number][] = [
  ['about-dog-large.png', '대형', '25kg 이상', 22, 48],
  ['about-dog-medium.png', '중형', '10 ~ 25kg', 53, 35],
  ['about-dog-small.png', '소형', '10kg 미만', 80, 24],
]
// 분석 장면: 관절점(사진 4:3 좌표, 0~1) 과 뼈대 선
// 대형견 사진(about-dog-large.png, 체급 장면의 그 강아지) 기준 0~1. 모핑된 강아지 위에 그대로 그린다
const KP: Record<string, [number, number]> = {
  nose: [0.97, 0.22], eye: [0.91, 0.12], withers: [0.74, 0.14], back: [0.52, 0.22], hip: [0.3, 0.3], tail: [0.18, 0.36],
  shoulder: [0.78, 0.3], elbowF: [0.8, 0.46], carpusF: [0.81, 0.75], fpawF: [0.93, 0.93],
  elbowB: [0.55, 0.5], carpusB: [0.53, 0.72], fpawB: [0.56, 0.95],
  stifleB: [0.25, 0.5], hockB: [0.14, 0.66], hpawB: [0.085, 0.925],
  stifleF: [0.35, 0.5], hockF: [0.37, 0.7], hpawF: [0.43, 0.95],
}
// 모핑 목표: 화면 안에서 강아지가 차지할 상자(화면 비율 0~1, 4:3 상자 기준으로 가운데 정렬)
const ANA_DOG = { l: 0.0223, t: 0.1359, w: 0.9401, h: 0.6723 }
const BONES: [string, string][] = [
  ['nose', 'eye'], ['eye', 'withers'], ['withers', 'back'], ['back', 'hip'], ['hip', 'tail'],
  ['withers', 'shoulder'], ['shoulder', 'elbowF'], ['elbowF', 'carpusF'], ['carpusF', 'fpawF'],
  ['shoulder', 'elbowB'], ['elbowB', 'carpusB'], ['carpusB', 'fpawB'],
  ['hip', 'stifleB'], ['stifleB', 'hockB'], ['hockB', 'hpawB'],
  ['hip', 'stifleF'], ['stifleF', 'hockF'], ['hockF', 'hpawF'],
]
const JOINT = new Set(['elbowF', 'elbowB', 'carpusF', 'carpusB', 'stifleB', 'stifleF', 'hockB', 'hockF'])
const METRICS: [string, number, string][] = [['무릎 가동 범위', 32, '°'], ['고관절 가동 범위', 17, '°'], ['입각기 비율', 61, '%'], ['좌우 대칭 점수', 73, '점']]
const PASSES: ('ok' | 'no')[] = ['ok', 'ok', 'no', 'ok', 'ok', 'ok', 'no', 'ok']
const TRUST: [string, string][] = [
  ['측정 품질 공개', '쓴 걸음과 뺀 걸음, 뺀 이유를 그대로 보여 줍니다.'],
  ['기관별 분리', '다른 기관의 자료는 서로 볼 수 없습니다.'],
  ['암호화', '전송은 HTTPS, 비밀번호는 복호화할 수 없게 저장합니다.'],
  ['보관과 삭제', '계약 기간 동안 보관하고, 지운 자료는 30일 뒤 영구 삭제합니다.'],
]

export default function About() {
  useTitle('서비스 소개 · Paw oh Paw')
  const { acct, me, toast } = usePage()
  const img = staticUrl('assets/')
  const root = useRef<HTMLDivElement>(null)
  const video = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    // React 는 muted 속성을 DOM 에 쓰지 않아 자동 재생이 막힐 수 있다. 직접 켜고 재생한다
    const v = video.current
    if (v) { v.muted = true; v.defaultMuted = true; v.play().catch(() => undefined) }

    const q = gsap.utils.selector(root)
    const mm = gsap.matchMedia()
    mm.add('(prefers-reduced-motion: reduce)', () => {
      gsap.set(q('.in-line, .sz-dog, .sz-tag, .kp-dot, .an-pass, #an-panel, #an-done, #em-shot, #em-row, #em-card, #rp-compare, .rp-card, .tr-up, .end-up'), { opacity: 1, x: 0, y: 0, scale: 1 })
      gsap.set(q('.kp-bone'), { opacity: 0.95 })
      gsap.set(q('#an-head'), { opacity: 1 })
      gsap.set(q('#em-cover'), { top: '100%' })
      gsap.set(q('#em-detail'), { xPercent: 0 })
      gsap.set(q('#rp-report, #rp-3d'), { yPercent: 0, xPercent: 0 })
      gsap.set(q('#rp-tip'), { opacity: 1 })
      q('.an-num').forEach((el) => { el.textContent = (el as HTMLElement).dataset.v ?? '' })
    })
    mm.add('(prefers-reduced-motion: no-preference)', () => {
      // 고정: 스크럽 길이 + 다음 장면이 덮는 100vh 동안 잡아 둔다. 스크럽은 스크럽 길이 동안만
      const pinScene = (id: string) => {
        ScrollTrigger.create({ trigger: `#${id}`, start: 'top top', end: `+=${LEN[id] + 100}%`, pin: true, pinSpacing: false })
        return { trigger: `#${id}`, start: 'top top', end: `+=${LEN[id]}%`, scrub: 0.6 }
      }
      // 장면 사이에서 멈추면 다음 장면 머리에 딱 맞춘다
      ;['#s-size', '#s-emr', '#s-rep', '#s-trust'].forEach((sel) => ScrollTrigger.create({ trigger: sel, start: 'top bottom', end: 'top top', snap: { snapTo: [0, 1], duration: { min: 0.25, max: 0.6 }, delay: 0.05, ease: 'power2.inOut' } }))
      // 상단바는 맨 위에서만
      ScrollTrigger.create({ start: 40, end: 999999, onToggle: (st) => { const bar = document.getElementById('ab-bar'); if (bar) { bar.style.opacity = st.isActive ? '0' : '1'; bar.style.transform = st.isActive ? 'translateY(-8px)' : 'none'; bar.style.pointerEvents = st.isActive ? 'none' : 'auto' } } })

      // 1. 도입: 영상은 처음부터. 스크롤하면 글자가 위로 빠지고 영상이 살짝 당겨진다
      gsap.timeline({ scrollTrigger: pinScene('s-intro') })
        .to(q('.in-line'), { y: -48, opacity: 0, stagger: 0.06, duration: 0.5, ease: 'power2.in' }, 0.3)
        .to(q('#in-video'), { scale: 1.06, duration: 1.2, ease: 'none' }, 0)

      // 2. 체급: 세 마리가 오른쪽에서 차례로 걸어 들어와 서고, 머리 위에 체급 표가 선다
      const tl2 = gsap.timeline({ scrollTrigger: pinScene('s-size') })
      DOGS.forEach((_, i) => {
        tl2.fromTo(q(`#sz-dog-${i}`), { x: 160, opacity: 0 }, { x: 0, opacity: 1, duration: 0.7, ease: 'power3.out' }, i * 0.45)
          .fromTo(q(`#sz-tag-${i}`), { y: 14, opacity: 0 }, { y: 0, opacity: 1, duration: 0.35, ease: 'back.out(1.6)' }, i * 0.45 + 0.5)
      })
      const big = q<HTMLElement>('#sz-dog-0')[0], row = big.parentElement!
      // 화면 안쪽(위 6%·좌우 2%·아래 4% 여백)에 4:3 상자를 가운데 두고, 그 안의 강아지 자리(화면 px)
      const target = () => {
        const W = window.innerWidth * 0.96, H = window.innerHeight * 0.90, ar = 4 / 3
        let w = W, h = H
        if (w / h > ar) w = h * ar; else h = w / ar
        const l = window.innerWidth * 0.02 + (W - w) / 2, t = window.innerHeight * 0.06 + (H - h) / 2
        return { l: l + ANA_DOG.l * w, t: t + ANA_DOG.t * h, w: ANA_DOG.w * w, h: ANA_DOG.h * h }
      }
      // 대형견의 변형 전 중심(행 안의 위치로 계산해 scroll 중 refresh 돼도 흔들리지 않는다)
      const base = () => { const rr = row.getBoundingClientRect(); return { cx: rr.left + big.offsetLeft + big.offsetWidth / 2, cy: rr.top + big.offsetTop + big.offsetHeight / 2, w: big.offsetWidth, h: big.offsetHeight } }
      // 가로·세로를 따로 맞춰 사진 속 강아지 상자와 픽셀 단위로 겹친다(비율 차이 7% 는 늘려서 흡수)
      const mScale = () => target().w / base().w
      const mX = () => { const t = target(); return t.l + t.w / 2 - base().cx }
      const mY = () => { const t = target(); return t.t + t.h / 2 - base().cy }
      tl2.scrollTrigger!.vars.invalidateOnRefresh = true
      tl2.to(q('#sz-dog-1, #sz-dog-2, .sz-tag, #sz-head'), { opacity: 0, duration: 0.4 }, '+=0.3')
        .to(big, { x: mX, y: mY, scale: mScale, duration: 1.0, ease: 'power2.inOut' }, '<')   // 대형견이 분석 사진 속 강아지 자리로
        .to(q('#sz-dim'), { opacity: 1, duration: 0.8 }, '<0.2')

        // 같은 강아지 위에 관절점이 켜지고 뼈대가 이어진다
        .fromTo(q('#an-head'), { y: 16, opacity: 0 }, { y: 0, opacity: 1, duration: 0.4, ease: 'power3.out' }, '-=0.2')
        .fromTo(q('.kp-dot'), { attr: { r: 0 }, opacity: 0 }, { attr: { r: 7.5 }, opacity: 1, stagger: 0.06, duration: 0.3, ease: 'back.out(2)' }, '-=0.2')
        .fromTo(q('.kp-bone'), { opacity: 0 }, { opacity: 0.95, stagger: 0.05, duration: 0.25, ease: 'none' }, '-=0.6')
        .fromTo(q('#an-panel'), { x: 32, opacity: 0 }, { x: 0, opacity: 1, duration: 0.5, ease: 'power3.out' }, '-=0.4')
      q('.an-step').forEach((el, i) => tl2.to(el, { backgroundColor: '#FFF1E6', color: '#B4501A', duration: 0.3 }, `>-0.3+=${i * 0.45}`))
      q('.an-pass').forEach((el, i) => tl2.fromTo(el, { scaleY: 0 }, { scaleY: 1, duration: 0.18, ease: 'power2.out' }, `>-0.3+=${i * 0.12}`))
      q('.an-num').forEach((el, i) => {
        const o = { v: 0 }, target = Number((el as HTMLElement).dataset.v)
        tl2.to(o, { v: target, duration: 0.8, ease: 'power2.out', onUpdate: () => { el.textContent = String(Math.round(o.v)) } }, `>-0.6+=${i * 0.15}`)
      })
      tl2.fromTo(q('#an-done'), { y: 12, opacity: 0 }, { y: 0, opacity: 1, duration: 0.4 }, '+=0.2').to({}, { duration: 0.8 })

      // 4. EMR: 홈 화면이 아래에서 올라오고 설명 칩이 차례로 붙는다
      const tl4 = gsap.timeline({ scrollTrigger: pinScene('s-emr') })
      // 처음엔 지금 크기로 올라오고, 더 내리면 화면을 꽉 채우도록 커진 뒤 그 안에서 상호작용한다
      const wrap = q<HTMLElement>('#em-wrap')[0]
      // 창 비율이 달라도 양옆 여백 없이 덮되, 위는 잘리지 않게 위쪽에 맞춘다(남는 건 아래만 잘림)
      const fillScale = () => Math.max(window.innerWidth / wrap.offsetWidth, window.innerHeight / wrap.offsetHeight)
      const fillY = () => { const r = wrap.getBoundingClientRect(), sc = fillScale(); return -(r.top + r.height / 2 - (r.height * sc) / 2) }
      tl4.scrollTrigger!.vars.invalidateOnRefresh = true
      tl4.fromTo(q('#em-shot'), { y: 80, opacity: 0, scale: 0.97 }, { y: 0, opacity: 1, scale: 1, duration: 0.9, ease: 'power3.out' }, 0.1)
        .to(q('#em-head'), { opacity: 0, y: -20, duration: 0.5, ease: 'power2.in' }, 1.2)
        .to(wrap, { scale: fillScale, y: fillY, duration: 1.0, ease: 'power2.inOut' }, 1.2)                        // 전체 화면으로
        .to(q('#em-shot'), { borderRadius: '0px', duration: 0.6 }, 1.5)
        .fromTo(q('#em-cover'), { top: '29%' }, { top: '100%', duration: 1.2, ease: 'steps(8)' }, 2.4)           // 표가 한 줄씩
        .fromTo(q('#em-cursor'), { left: '70%', top: '95%', opacity: 0 }, { left: '82.5%', top: '48.1%', opacity: 1, duration: 0.8, ease: 'power2.inOut' }, 3.7)  // 커서가 '기록 작성'으로
        .to(q('#em-cursor'), { scale: 0.85, duration: 0.1, yoyo: true, repeat: 1 }, 4.55)                        // 누름
        .to(q('#em-row'), { opacity: 1, duration: 0.2 }, 4.6)
        .to(q('#em-cursor'), { opacity: 0, duration: 0.2 }, 6.1)
        .fromTo(q('#em-detail'), { xPercent: 100 }, { xPercent: 0, duration: 0.7, ease: 'power3.out' }, 6.3)      // 상세 화면으로(1.5초 머문 뒤)
        .fromTo(q('#em-card'), { y: 16, opacity: 0, scale: 0.96 }, { y: 0, opacity: 1, scale: 1, duration: 0.5, ease: 'back.out(1.4)' }, 7.1)  // 오늘 진료 기록
        .to({}, { duration: 1.0 })

      // 5. 보고서·경과: 보고서가 올라오고, 옆으로 경과 비교가 들어온다
      const tl5 = gsap.timeline({ scrollTrigger: pinScene('s-rep') })
      const rwrap = q<HTMLElement>('#rp-wrap')[0]
      const rScale = () => Math.max(window.innerWidth / rwrap.offsetWidth, window.innerHeight / rwrap.offsetHeight)
      const rY = () => { const r = rwrap.getBoundingClientRect(), sc = rScale(); return -(r.top + r.height / 2 - (r.height * sc) / 2) }
      const applyCut = () => {
        const sc = rScale()
        const cx = Math.max(0, (rwrap.offsetWidth * sc - window.innerWidth) / (2 * sc)), cy = Math.max(0, (rwrap.offsetHeight * sc - window.innerHeight) / sc)
        rwrap.style.setProperty('--cutx', `${cx}px`); rwrap.style.setProperty('--cuty', `${cy}px`)
      }
      applyCut(); ScrollTrigger.addEventListener('refresh', applyCut)
      tl5.scrollTrigger!.vars.invalidateOnRefresh = true
      tl5.fromTo(q('#rp-compare'), { y: 60, opacity: 0 }, { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out' }, 0.1)
        .to(q('#rp-head'), { opacity: 0, y: -20, duration: 0.5, ease: 'power2.in' }, 1.1)
        .to(rwrap, { scale: rScale, y: rY, borderRadius: '0px', duration: 1.0, ease: 'power2.inOut' }, 1.1)    // 전체 화면으로
        .fromTo(q('#rp-report'), { yPercent: 100 }, { yPercent: 0, duration: 0.8, ease: 'power3.out' }, 4.0)
        .fromTo(q('#rp-card-2'), { y: 16, opacity: 0, scale: 0.96 }, { y: 0, opacity: 1, scale: 1, duration: 0.5, ease: 'back.out(1.4)' }, 4.8)
        .to(q('#rp-report-img'), { y: () => { const box = q<HTMLElement>('#rp-vet-box')[0]; return -Math.max(0, box.offsetWidth * (2587 / 1366) - box.offsetHeight * 0.88) }, duration: 5.0, ease: 'none' }, 5.1)   // 보호자용 PDF 를 천천히 끝까지 스크롤
        .fromTo(q('#rp-3d'), { xPercent: 100 }, { xPercent: 0, duration: 0.8, ease: 'power3.out' }, 11.9)
        .fromTo(q('#rp-card-3'), { y: 16, opacity: 0, scale: 0.96 }, { y: 0, opacity: 1, scale: 1, duration: 0.5, ease: 'back.out(1.4)' }, 14.0)
        .fromTo(q('#rp-cursor'), { left: '60%', top: '95%', opacity: 0 }, { left: '32.3%', top: '45.6%', opacity: 1, duration: 0.7, ease: 'power2.inOut' }, 12.8)   // 뒷다리에 마우스(0.93 축소 반영)
        .fromTo(q('#rp-tip'), { y: 8, opacity: 0 }, { y: 0, opacity: 1, duration: 0.35, ease: 'back.out(1.6)' }, 13.5)
        .to({}, { duration: 1.2 })

      // 6. 신뢰 카드와 마무리
      gsap.fromTo(q('.tr-up'), { y: 28, opacity: 0 }, { y: 0, opacity: 1, stagger: 0.1, duration: 0.7, ease: 'power3.out', scrollTrigger: { trigger: '#s-trust', start: 'top 72%' } })
      gsap.fromTo(q('.end-up'), { y: 28, opacity: 0 }, { y: 0, opacity: 1, stagger: 0.12, duration: 0.7, ease: 'power3.out', scrollTrigger: { trigger: '#s-end', start: 'top 72%' } })
    })

    // 화면 캡처 캔버스: 상자 안에서 비율을 지키며 최대 크기로
    const fit = () => {
      q<HTMLElement>('[data-ratio]').forEach((el) => {
        const box = el.parentElement!, r = Number(el.dataset.ratio)
        const w = Math.min(box.clientWidth, box.clientHeight * r)
        el.style.width = `${Math.floor(w)}px`
        el.style.height = `${Math.floor(w / r)}px`
      })
      ScrollTrigger.refresh()
    }
    fit()
    window.addEventListener('resize', fit)
    const onLoad = () => fit()
    q('img').forEach((el) => el.addEventListener('load', onLoad))
    return () => { mm.revert(); ScrollTrigger.getAll().forEach((t) => t.kill()); window.removeEventListener('resize', fit); q('img').forEach((el) => el.removeEventListener('load', onLoad)) }
  }, [])

  const P = (k: string) => KP[k]
  return (
    <Base acct={acct} me={me} nav="about" toast={toast} topbar={<GuestBar loggedIn={!!acct} />}>
      <div ref={root} style={css(`width:100vw;margin-left:calc(50% - 50vw);overflow:hidden;background:${PAPER}`)}>

        {/* 1. 도입: 영상이 화면을 채우고 글자가 그 위에 */}
        <section id="s-intro" style={sceneStyle('s-intro', 1, `background:${CREAM}`)}>
          <video ref={video} id="in-video" src={`${img}landing-walk.mp4`} autoPlay muted loop playsInline preload="auto" style={css('position:absolute;top:-120px;left:0;width:calc(100% + 200px);height:calc(100% + 120px);max-width:none;object-fit:cover;pointer-events:none')}></video>
          <div style={css('position:absolute;inset:0;background:linear-gradient(180deg,rgba(250,249,246,.55) 0%,rgba(250,249,246,.15) 45%,rgba(250,249,246,.6) 100%);pointer-events:none')}></div>
          <div style={css('position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:0 40px;gap:24px')}>
            <h1 style={css(T.hero)}>
              <span className="in-line" style={css('display:block')}>걷는 영상 하나로</span>
              <span className="in-line" style={css('display:block')}>강아지의 보행을</span>
              <span className="in-line" style={css(`display:block;color:${ORANGE}`)}>숫자로 봅니다</span>
            </h1>
          </div>
        </section>

        {/* 2. 체급: 크림 배경을 화면 가득, 세 마리가 바닥 선 위에 선다 */}
        <section id="s-size" style={sceneStyle('s-size', 2, `background:linear-gradient(180deg,#F6EDE3 0%,${CREAM} 60%,#E6D8C8 100%)`)}>
          <div style={css('position:absolute;left:0;right:0;bottom:10%;height:1px;background:rgba(25,31,40,.08)')}></div>
          <div id="sz-dim" style={css('position:absolute;inset:0;background:rgba(15,20,25,.6);opacity:0;pointer-events:none;z-index:1')}></div>
          <div style={css('position:absolute;left:32px;right:32px;bottom:10%;display:flex;align-items:flex-end;justify-content:center;gap:3vw')}>
          {DOGS.map(([file, name, rule, , h], i) => (
            <div key={name} className="sz-dog" id={`sz-dog-${i}`} style={css(`position:relative;height:${h}vh;display:flex;flex-direction:column;align-items:center;opacity:0;transform-origin:50% 50%;z-index:${i === 0 ? 2 : 0}`)}>
              <div className="sz-tag" id={`sz-tag-${i}`} style={css('position:absolute;bottom:calc(100% + 20px);left:50%;transform:translateX(-50%);background:rgba(255,255,255,.94);border-radius:14px;padding:10px 16px;box-shadow:0 12px 30px -12px rgba(25,31,40,.35);display:flex;flex-direction:column;align-items:center;gap:2px;min-width:112px;opacity:0')}>
                <b style={css(`font-size:17px;line-height:1.3;font-weight:700;letter-spacing:-0.02em;color:${INK}`)}>{name}</b>
                <span style={css(`font-size:13px;line-height:1.4;font-weight:500;color:${INK2};white-space:nowrap`)}>{rule}</span>
              </div>
              <img src={`${img}${file}`} alt={`${name}견이 옆으로 걷는 모습`} style={css('height:100%;width:auto;display:block;filter:drop-shadow(0 18px 24px rgba(25,31,40,.18))')} />
              {i === 0 && (
                <svg viewBox="0 0 654 373" preserveAspectRatio="none" style={css('position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:visible')}>
                  {BONES.map(([a, b], k) => (
                    <line key={k} className="kp-bone" x1={P(a)[0] * 654} y1={P(a)[1] * 373} x2={P(b)[0] * 654} y2={P(b)[1] * 373} stroke="#fff" strokeWidth="2.5" strokeLinecap="round" opacity="0" vectorEffect="non-scaling-stroke" />
                  ))}
                  {Object.entries(KP).map(([k, [x, y]]) => (
                    <circle key={k} className="kp-dot" cx={x * 654} cy={y * 373} r="7.5" fill={k.includes('paw') ? '#4BD1FF' : JOINT.has(k) ? '#FFD23F' : '#FF8A5C'} stroke="#fff" strokeWidth="2" opacity="0" vectorEffect="non-scaling-stroke" />
                  ))}
                </svg>
              )}
            </div>
          ))}
          </div>
          {/* 모핑 뒤 분석 글·수치 */}
          <div id="an-head" style={css(OVER + ';opacity:0;z-index:3')}>
            <h2 style={css(T.h2 + ';color:#fff')}>관절점을 프레임마다<br />추적합니다</h2>
          </div>
          <div style={css('position:absolute;left:40px;right:40px;bottom:32px;display:flex;flex-direction:column;gap:10px;z-index:3')}>
            <div style={css('display:flex;gap:6px;align-items:flex-end;height:24px;max-width:720px')}>
              {PASSES.map((p, i) => <div key={i} className="an-pass" style={css(`flex:1;height:${p === 'ok' ? '24px' : '12px'};border-radius:5px;transform-origin:bottom;transform:scaleY(0);background:${p === 'ok' ? 'rgba(255,154,92,.9)' : 'rgba(255,255,255,.25)'}`)}></div>)}
            </div>
          </div>
          <div id="an-panel" style={css(`position:absolute;right:40px;top:calc(68px + 24px);width:min(300px,32%);background:rgba(255,255,255,.96);color:${INK};border-radius:18px;padding:20px;display:flex;flex-direction:column;gap:16px;box-shadow:0 24px 60px -20px rgba(0,0,0,.6);opacity:0;z-index:3`)}>
            <div style={css('display:flex;gap:6px;flex-wrap:wrap')}>
              {['영상 확인', '관절점 찾기', '걸음 나누기', '각도 계산'].map((n) => <span key={n} className="an-step" style={css('height:28px;padding:0 10px;border-radius:8px;background:#F1EDE6;color:#7A808A;display:flex;align-items:center;font-size:12.5px;font-weight:700')}>{n}</span>)}
            </div>
            <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:12px 16px')}>
              {METRICS.map(([n, v, u]) => (
                <div key={n} style={css('display:flex;flex-direction:column;gap:2px')}>
                  <span style={css(`font-size:12px;line-height:1.4;font-weight:600;color:${INK3}`)}>{n}</span>
                  <b style={css('font-size:26px;line-height:1.2;font-weight:700;letter-spacing:-0.02em;font-variant-numeric:tabular-nums')}><span className="an-num" data-v={v}>0</span>{u}</b>
                </div>
              ))}
            </div>
            <div id="an-done" style={css('font-size:13px;line-height:1.4;font-weight:600;color:#B4501A;opacity:0')}>분석 완료 · 보고서를 만들고 있습니다</div>
          </div>
          <div id="sz-head" style={css(HEAD_C)}>
            <h2 style={css(T.h2)}>소형견부터 대형견까지</h2>
          </div>
        </section>

        {/* 4. EMR: 왼쪽 글, 오른쪽에 홈 화면 크게 */}
        <section id="s-emr" style={sceneStyle('s-emr', 4, `background:${PAPER}`)}>
          <div id="em-head" style={css(HEAD_C)}>
            <h2 style={css(T.h2)}>진료 차트처럼 익숙하게</h2>
          </div>
          <div style={css(MEDIA_C + ';z-index:4')}>
            <div id="em-wrap" data-ratio="1.7778" style={css('position:relative;transform-origin:50% 50%')}>
              <div id="em-shot" style={css('position:absolute;inset:0;border-radius:20px;overflow:hidden;background:#fff;box-shadow:0 30px 70px -30px rgba(25,31,40,.35);border:1px solid #ECE8E2;opacity:0')}>
                <img src={`${img}about-home-169.jpg`} alt="환자 목록·바이탈·진료 기록이 있는 홈 화면" style={css('position:absolute;inset:0;width:100%;height:100%;object-fit:cover')} />
                {/* 표를 한 줄씩 채우는 덮개(아래로 밀려 내려간다) */}
                <div id="em-cover" style={css('position:absolute;left:0;right:0;top:29%;bottom:0;background:#FAF9F6')}></div>
                {/* 누른 줄 강조 */}
                <div id="em-row" style={css('position:absolute;left:13.2%;width:73.6%;top:45.4%;height:5.6%;border-radius:8px;background:rgba(210,96,26,.1);border:1.5px solid rgba(210,96,26,.55);opacity:0')}></div>
                {/* 누른 뒤 열리는 반려견 상세 화면 */}
                <div id="em-detail" style={css('position:absolute;inset:0;background:#fff;transform:translateX(100%);box-shadow:-20px 0 40px -20px rgba(25,31,40,.3)')}>
                  <img src={`${img}about-dog-detail-169.jpg`} alt="보리 상세 화면: 환자 정보·바이탈·진료 기록" style={css('position:absolute;inset:0;width:100%;height:100%;object-fit:cover')} />
                </div>
                {/* 차팅 카드 */}
                <div id="em-card" style={css(`position:absolute;left:38%;top:44%;width:30%;background:#fff;border:1px solid #ECE8E2;border-radius:14px;box-shadow:0 24px 50px -20px rgba(25,31,40,.4);padding:14px 16px;display:flex;flex-direction:column;gap:8px;opacity:0;color:${INK}`)}>
                  <b style={css('font-size:14px;font-weight:700')}>보리 · 오늘 진료 기록</b>
                  <div style={css('display:grid;grid-template-columns:repeat(4,1fr);gap:6px')}>
                    {[['체중', '28.1kg'], ['체온', '38.6℃'], ['심박', '92'], ['혈압', '142/84']].map(([k, v]) => <div key={k} style={css('background:#FAF7F2;border-radius:8px;padding:6px 8px;display:flex;flex-direction:column;gap:2px')}><span style={css('font-size:10px;color:#8E949C;font-weight:600')}>{k}</span><b style={css('font-size:12.5px;font-weight:700')}>{v}</b></div>)}
                  </div>
                  {[['S', '산책 후 오른뒤를 들고 서는 시간이 줄었다고 함'], ['O', '보행 측정 대칭 점수 73점 (직전 64점)'], ['A', 'TPLO 후 회복 순조'], ['P', '2주 뒤 재측정']].map(([k, v]) => <div key={k} style={css('display:flex;gap:8px;font-size:11.5px;line-height:1.4')}><b style={css('width:14px;color:#B4501A')}>{k}</b><span style={css('color:#3A4250')}>{v}</span></div>)}
                  <div id="em-save" style={css(`align-self:flex-end;height:26px;padding:0 10px;border-radius:7px;background:${ORANGE};color:#fff;font-size:11.5px;font-weight:700;display:flex;align-items:center`)}>저장</div>
                </div>
                {/* 커서 */}
                <svg id="em-cursor" viewBox="0 0 24 24" style={css('position:absolute;left:70%;top:95%;width:22px;height:22px;opacity:0;filter:drop-shadow(0 2px 4px rgba(0,0,0,.35))')}><path d="M5 3l14 8-6 1.5L11 20z" fill="#191F28" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" /></svg>
              </div>
            </div>
          </div>
        </section>

        {/* 5. 보고서·경과: 왼쪽 글, 오른쪽에 보고서와 경과 비교 */}
        <section id="s-rep" style={sceneStyle('s-rep', 5, 'background:#F3EDE4')}>
          <div id="rp-head" style={css(HEAD_C)}>
            <h2 style={css(T.h2)}>경과 비교부터 3D 모델까지</h2>
          </div>
          <div style={css(MEDIA_C + ';z-index:4')}>
            <div id="rp-wrap" data-ratio="1.7778" style={css('position:relative;transform-origin:50% 50%;border-radius:20px;overflow:hidden;background:#fff;box-shadow:0 30px 70px -30px rgba(25,31,40,.35);border:1px solid #ECE8E2')}>
              <div id="rp-compare" style={css('position:absolute;inset:0;opacity:0')}>
                <img src={`${img}about-compare-169.jpg`} alt="기준 회차 대비 경과 비교 화면" style={css('position:absolute;inset:0;width:100%;height:100%;object-fit:cover')} />
              </div>
              <div id="rp-report" style={css('position:absolute;inset:0;background:#3C3F43;transform:translateY(100%);box-shadow:0 -20px 40px -20px rgba(25,31,40,.3);overflow:hidden')}>
                {/* PDF 뷰어처럼 보호자용 한 장만 가운데에, 스크롤하면 페이지가 올라간다 */}
                <div id="rp-vet-box" style={css('position:absolute;left:50%;top:3%;bottom:0;width:46%;transform:translateX(-50%);overflow:hidden')}>
                  <img id="rp-report-img" src={`${img}about-report-owner-full.jpg`} alt="보호자용 보고서 전체" style={css('position:absolute;left:0;top:0;width:100%;height:auto;display:block;background:#fff;box-shadow:0 10px 40px rgba(0,0,0,.45)')} />
                </div>
                <div id="rp-card-2" className="rp-card" style={css(`position:absolute;width:24%;background:#fff;border:1px solid #ECE8E2;border-radius:14px;box-shadow:0 24px 50px -20px rgba(25,31,40,.4);padding:14px 16px;display:flex;flex-direction:column;gap:8px;opacity:0;color:${INK};left:calc(1.5% + var(--cutx, 0px));top:12%`)}>
                  <span style={css('font-size:11px;font-weight:700;color:#B4501A;letter-spacing:.02em')}>보고서</span>
                  <b style={css('font-size:14px;font-weight:700;line-height:1.35')}>보호자용과 수의사용을 따로 만듭니다</b>
                  <div style={css('display:flex;gap:7px;font-size:11.5px;line-height:1.45;color:#3A4250')}><span style={css('color:#B4501A;font-weight:700')}>·</span><span>보호자용은 주요 결과 한 줄과 그림으로</span></div><div style={css('display:flex;gap:7px;font-size:11.5px;line-height:1.45;color:#3A4250')}><span style={css('color:#B4501A;font-weight:700')}>·</span><span>수의사용은 관절별 수치와 보행 주기 그래프로</span></div><div style={css('display:flex;gap:7px;font-size:11.5px;line-height:1.45;color:#3A4250')}><span style={css('color:#B4501A;font-weight:700')}>·</span><span>PDF 로 바로 내려받습니다</span></div>
                </div>
              </div>
              <div id="rp-3d" style={css('position:absolute;inset:0;background:#fff;transform:translateX(100%);box-shadow:-20px 0 40px -20px rgba(25,31,40,.3)')}>
                <div style={css('position:absolute;inset:0;background:#FAF9F5')}></div>
                <div style={css('position:absolute;inset:0;transform:scale(.93);transform-origin:50% 0')}>
                <img src={`${img}about-3d-169.jpg`} alt="3D 보행 모델 화면" style={css('position:absolute;inset:0;width:100%;height:100%;object-fit:cover')} />
                <div id="rp-tip" style={css(`position:absolute;left:31%;top:49%;transform:translate(8px,-100%);background:${INK};color:#fff;border-radius:10px;padding:8px 12px;font-size:13px;line-height:1.4;font-weight:700;box-shadow:0 10px 24px -10px rgba(0,0,0,.5);white-space:nowrap;opacity:0`)}>오른뒤 무릎 <span style={css('color:#FF9A5C')}>32°</span> · 왼뒤 53°</div>
                <div id="rp-card-3" className="rp-card" style={css(`position:absolute;width:24%;background:#fff;border:1px solid #ECE8E2;border-radius:14px;box-shadow:0 24px 50px -20px rgba(25,31,40,.4);padding:14px 16px;display:flex;flex-direction:column;gap:8px;opacity:0;color:${INK};right:calc(5.5% + var(--cutx, 0px) / 0.93);top:63%;width:25%`)}>
                  <span style={css('font-size:11px;font-weight:700;color:#B4501A;letter-spacing:.02em')}>3D 모델</span>
                  <b style={css('font-size:14px;font-weight:700;line-height:1.35')}>측정한 수치로 다시 걷습니다</b>
                  <div style={css('display:flex;gap:7px;font-size:11.5px;line-height:1.45;color:#3A4250')}><span style={css('color:#B4501A;font-weight:700')}>·</span><span>덜 쓰는 다리를 붉게 표시합니다</span></div><div style={css('display:flex;gap:7px;font-size:11.5px;line-height:1.45;color:#3A4250')}><span style={css('color:#B4501A;font-weight:700')}>·</span><span>다리에 마우스를 올리면 각도를 보여줍니다</span></div><div style={css('display:flex;gap:7px;font-size:11.5px;line-height:1.45;color:#3A4250')}><span style={css('color:#B4501A;font-weight:700')}>·</span><span>기준 회차를 겹쳐 볼 수 있습니다</span></div>
                </div>
                </div>
              </div>
              {/* 커서 */}
              <svg id="rp-cursor" viewBox="0 0 24 24" style={css('position:absolute;left:60%;top:95%;width:22px;height:22px;opacity:0;z-index:5;filter:drop-shadow(0 2px 4px rgba(0,0,0,.35))')}><path d="M5 3l14 8-6 1.5L11 20z" fill="#191F28" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" /></svg>
            </div>
          </div>
        </section>

        {/* 6. 신뢰 */}
        <section id="s-trust" style={css(`position:relative;z-index:6;background:${PAPER};padding:120px 32px 0;display:flex;flex-direction:column;align-items:center;gap:32px`)}>
          <div className="tr-up" style={css('display:flex;flex-direction:column;align-items:center;gap:12px;text-align:center;opacity:0')}>
            <h2 style={css(T.h2)}>숨기지 않고, 섞지 않고, 지웁니다</h2>
          </div>
          <div style={css('width:min(1312px,100%);display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px')}>
            {TRUST.map(([h, p]) => (
              <div key={h} className="tr-up" style={css('background:#fff;border:1px solid #ECE8E2;border-radius:20px;padding:28px 24px;display:flex;flex-direction:column;gap:10px;opacity:0')}>
                <b style={css(`font-size:18px;line-height:1.35;font-weight:700;letter-spacing:-0.02em;color:${INK}`)}>{h}</b>
                <span style={css(`font-size:15px;line-height:1.6;font-weight:500;color:${INK2}`)}>{p}</span>
              </div>
            ))}
          </div>
        </section>

        {/* 7. 마무리 */}
        <section id="s-end" style={css(`position:relative;z-index:6;background:${PAPER};padding:140px 64px 120px;display:flex;flex-direction:column;align-items:center;gap:24px;text-align:center`)}>
          <h2 className="end-up" style={css(T.h2 + ';opacity:0')}>분석은 수의사의 판단을 돕습니다.</h2>
          <a className="end-up lk hv-orange" href={link(acct ? '/upload' : '/signup')} style={css(`margin-top:16px;height:56px;padding:0 28px;border-radius:14px;background:${ORANGE};color:#fff;display:flex;align-items:center;gap:8px;font-size:17px;font-weight:700;opacity:0`)}>{acct ? '보행 분석 시작하기' : '기관으로 시작하기'}<svg width="18" height="18" viewBox="0 0 24 24"><use href="#w-chev"></use></svg></a>
        </section>
      </div>
    </Base>
  )
}
