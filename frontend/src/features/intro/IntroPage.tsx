import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../../app/auth'
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
  // 디자인 v5 story 네 장: 그림 1·2·3 은 디자인 자산, 4 는 보고서 견본 카드
  if (i === 0) return <img src="/assets/story-1.png" alt="반려견이 매트 위를 걷는 모습" />
  if (i === 1) return <img src="/assets/story-2.png" alt="휴대폰을 가로로 들고 촬영하는 모습" />
  if (i === 2) return <img src="/assets/story-3.png" alt="관절점이 표시된 반려견" />
  return <ReportMock />
}

/** 디자인 4번째 장의 보고서 견본 카드 */
function ReportMock() {
  const rows: [string, string, string, string][] = [
    ['무릎 ROM', '66°', '58°', '8°'],
    ['고관절 ROM', '44°', '41°', '3°'],
    ['팔꿈치 ROM', '52°', '50°', '2°'],
    ['걸음 길이', '41%', '38%', '3%p'],
  ]
  return (
    <div className="report-mock">
      <div className="rm-head">
        <span className="rm-brand">
          <img src="/assets/logo-joint.png" alt="" />
          Paw oh Paw
        </span>
        <span className="rm-kind">보행 분석 리포트</span>
      </div>
      <div className="rm-bar" />
      <div>
        <div className="rm-title">보리의 걸음 리포트</div>
        <div className="rm-sub">10월 14일 측정 · 골든 리트리버 · 7살</div>
      </div>
      <div className="rm-table">
        <div className="rm-tr head">
          <span>지표</span>
          <span>왼쪽</span>
          <span>오른쪽</span>
          <span>차이</span>
        </div>
        {rows.map((r, idx) => (
          <div className={`rm-tr${idx % 2 ? '' : ' alt'}`} key={r[0]}>
            {r.map((c, j) => (
              <span key={j}>{c}</span>
            ))}
          </div>
        ))}
      </div>
      <svg viewBox="0 0 320 150" className="rm-chart" aria-hidden="true">
        <g stroke="#ECE8E2" strokeDasharray="3 4">
          <line x1="24" y1="20" x2="310" y2="20" />
          <line x1="24" y1="75" x2="310" y2="75" />
          <line x1="24" y1="130" x2="310" y2="130" />
        </g>
        <polyline points={knee(53)} fill="none" stroke="#3B6FE0" strokeWidth="3" />
        <polyline points={knee(46)} fill="none" stroke="#E5604D" strokeWidth="3" strokeDasharray="6 5" />
      </svg>
      <span className="rm-foot">보행 평가 보조 자료이며 진단을 대신하지 않습니다.</span>
    </div>
  )
}

/** 디자인의 무릎 각도 곡선(knee()) */
function knee(depth: number): string {
  const gs = (p: number, c: number, w: number) => Math.exp(-(((p - c) / w) ** 2))
  const pts: string[] = []
  for (let i = 0; i <= 40; i++) {
    const p = i / 40
    const a = 150 - 16 * gs(p, 0.12, 0.07) - depth * gs(p, 0.7, 0.11)
    pts.push(`${(24 + p * 286).toFixed(1)},${(130 - ((a - 90) / 60) * 110).toFixed(1)}`)
  }
  return pts.join(' ')
}
