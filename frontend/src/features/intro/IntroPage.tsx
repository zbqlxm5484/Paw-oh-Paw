import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../../app/auth'
import { DogSkeleton } from '../../components/DogSkeleton'
import { Icon } from '../../components/Icon'
import './intro.css'

/** 디자인 v5 `story` 의 네 장. 그림(story-1~3.png)은 저장소에 없어 SVG 로 대신한다. */
const PAGES = [
  { title: '반려견을 평소처럼 걷게 합니다.', body: '매트 위를 왕복해 걷게 해요. 뛰거나 멈추지 않고 일직선으로 걸을 때 가장 잘 측정돼요.' },
  { title: '반려견이 걷는 모습을 옆에서 촬영합니다.', body: '휴대폰을 가로로 들고, 걷는 방향과 직각에서 몸 전체가 보이게 찍어요.' },
  { title: 'AI 모델이 관절점을 찾고,\n보행 패턴을 분석합니다.', body: '관절 22곳을 찾아 가동 범위, 걸음 길이, 입각기 비율을 계산해요.' },
  { title: '결과를 보고서로 받아\nPDF로 저장할 수 있습니다.', body: '보호자용과 수의사용 두 판본을 자동으로 만들어요. 회차가 쌓이면 재활 경과도 비교해요.' },
]

export function IntroPage() {
  const nav = useNavigate()
  const { loggedIn } = useAuth()
  const ref = useRef<HTMLDivElement>(null)
  const [page, setPage] = useState(0)

  function go(i: number) {
    const el = ref.current
    if (!el) return
    el.scrollTo({ left: i * el.clientWidth, behavior: 'smooth' })
  }
  function onScroll() {
    const el = ref.current
    if (!el) return
    setPage(Math.round(el.scrollLeft / Math.max(1, el.clientWidth)))
  }
  const last = page >= PAGES.length - 1

  return (
    <div className={`screen${loggedIn ? ' with-tabs' : ''}`} style={{ paddingBottom: loggedIn ? 96 : 0 }}>
      <div className="topbar" style={{ justifyContent: 'space-between', paddingRight: 20 }}>
        <div className="topbar-left">
          {!loggedIn && (
            <button type="button" className="icon-btn" onClick={() => nav(-1)} aria-label="뒤로">
              <Icon name="back" />
            </button>
          )}
          <b className="topbar-title" style={{ paddingLeft: loggedIn ? 12 : 0 }}>
            서비스 소개
          </b>
        </div>
      </div>
      <div className="dots" aria-hidden="true">
        {PAGES.map((_, i) => (
          <span key={i} className={i === page ? 'on' : ''} />
        ))}
      </div>
      <div ref={ref} onScroll={onScroll} className="story scroll">
        {PAGES.map((p, i) => (
          <section key={i} className="story-page">
            <div className="story-visual">
              <Illustration i={i} />
            </div>
            <div className="story-text">
              <span className="num tabular">{String(i + 1).padStart(2, '0')}</span>
              <b>{p.title}</b>
              <span className="body">{p.body}</span>
            </div>
          </section>
        ))}
      </div>
      <div className="story-nav">
        <button type="button" className="story-prev" onClick={() => go(page - 1)} disabled={page === 0}>
          <Icon name="back" size={16} />
          이전
        </button>
        <button type="button" className={`story-next${last ? ' pri' : ''}`} onClick={() => (last ? nav(loggedIn ? '/capture' : '/login') : go(page + 1))}>
          {last ? (loggedIn ? '촬영하기' : '시작하기') : '다음'}
          <Icon name="chev" size={16} />
        </button>
      </div>
    </div>
  )
}

function Illustration({ i }: { i: number }) {
  if (i === 0)
    return (
      <svg viewBox="0 0 320 240" className="ill">
        <rect x="20" y="150" width="280" height="40" rx="6" fill="#E7DED0" />
        <rect x="36" y="158" width="248" height="24" rx="4" fill="#D9CDB9" />
        <g transform="translate(70 60) scale(0.55)">
          <DogBody />
        </g>
        <g fill="var(--pri)" opacity=".7">
          <circle cx="60" cy="205" r="4" />
          <circle cx="110" cy="212" r="4" />
          <circle cx="160" cy="205" r="4" />
          <circle cx="210" cy="212" r="4" />
          <circle cx="260" cy="205" r="4" />
        </g>
      </svg>
    )
  if (i === 1)
    return (
      <svg viewBox="0 0 320 240" className="ill">
        <rect x="24" y="36" width="272" height="168" rx="16" fill="#141B22" />
        <rect x="40" y="52" width="240" height="136" rx="8" fill="#1F2A36" />
        <g transform="translate(78 78) scale(0.5)">
          <DogBody light />
        </g>
        <rect x="40" y="52" width="240" height="136" rx="8" fill="none" stroke="var(--pri)" strokeWidth="2" strokeDasharray="8 6" />
        <circle cx="268" cy="64" r="5" fill="#E5604D" />
        <text x="246" y="68" fontSize="10" fill="#fff" fontWeight="700" textAnchor="end">REC</text>
        <text x="160" y="222" fontSize="12" fill="var(--sub)" textAnchor="middle">가로로 · 옆모습 · 몸 전체</text>
      </svg>
    )
  if (i === 2)
    return (
      <svg viewBox="0 0 320 240" className="ill">
        <rect x="24" y="36" width="272" height="168" rx="16" fill="#141B22" />
        <g transform="translate(44 44)">
          <DogSkeleton width={232} height={152} />
        </g>
        <text x="160" y="222" fontSize="12" fill="var(--sub)" textAnchor="middle">관절점 22곳 · 가동 범위 · 걸음 길이</text>
      </svg>
    )
  return (
    <svg viewBox="0 0 320 240" className="ill">
      <rect x="70" y="20" width="180" height="210" rx="6" fill="#fff" stroke="var(--line)" />
      <rect x="86" y="40" width="30" height="3" fill="var(--pri)" />
      <rect x="86" y="54" width="110" height="10" rx="2" fill="#1B2433" />
      <rect x="86" y="70" width="80" height="6" rx="2" fill="#C9C4BC" />
      <rect x="86" y="90" width="148" height="14" rx="2" fill="#1B2433" />
      {[0, 1, 2, 3].map((r) => (
        <g key={r}>
          <rect x="86" y={108 + r * 16} width="148" height="12" rx="2" fill={r % 2 ? '#fff' : '#FAF8F5'} />
          <rect x="92" y={112 + r * 16} width="50" height="4" rx="1" fill="#5B6472" />
          <rect x="160" y={112 + r * 16} width="22" height="4" rx="1" fill="#3B6FE0" />
          <rect x="196" y={112 + r * 16} width="22" height="4" rx="1" fill="#E5604D" />
        </g>
      ))}
      <polyline points="90,200 110,186 130,196 150,180 170,192 190,178 210,190 230,182" fill="none" stroke="#3B6FE0" strokeWidth="2" />
      <polyline points="90,204 110,194 130,200 150,188 170,198 190,186 210,196 230,190" fill="none" stroke="#E5604D" strokeWidth="2" strokeDasharray="4 3" />
      <text x="160" y="226" fontSize="10" fill="var(--dim)" textAnchor="middle">보행 평가 보조 자료이며 진단을 대신하지 않습니다.</text>
    </svg>
  )
}

/** 단순한 개 옆모습. 디자인의 비글 일러스트 대신 쓴다. */
function DogBody({ light = false }: { light?: boolean }) {
  const c = light ? '#F2A65A' : '#D2601A'
  const d = light ? '#FCEEE3' : '#B4501A'
  return (
    <g>
      <ellipse cx="160" cy="110" rx="90" ry="46" fill={c} />
      <circle cx="248" cy="78" r="34" fill={c} />
      <ellipse cx="262" cy="92" rx="22" ry="14" fill={d} />
      <path d="M232 52 q-10 -34 14 -40 q6 20 2 40z" fill={d} />
      <circle cx="256" cy="72" r="4" fill="#1B2433" />
      <path d="M70 100 q-30 -24 -22 -52" stroke={c} strokeWidth="14" fill="none" strokeLinecap="round" />
      {[96, 126, 200, 228].map((x, i) => (
        <rect key={i} x={x} y="140" width="18" height="60" rx="8" fill={i % 2 ? d : c} />
      ))}
    </g>
  )
}
