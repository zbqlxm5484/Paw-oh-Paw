/** 아직 이식하지 않은 화면의 자리. screenPlan 4~11단계에서 채운다. */
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../app/auth'
import { Icon } from '../components/Icon'
import { Button, Card, Empty, Sheet, TopBar } from '../components/ui'

function Placeholder({ title, step, children }: { title: string; step: string; children?: React.ReactNode }) {
  return (
    <div className="screen">
      <div className="topbar" style={{ padding: '0 20px' }}>
        <b className="topbar-title">{title}</b>
      </div>
      <div className="scroll screen-body with-tabs">
        <Empty>
          아직 만들지 않은 화면이에요.
          <br />
          <span className="small">docs/frontend/screenPlan.md {step}</span>
        </Empty>
        {children}
      </div>
    </div>
  )
}

export function StoryPlaceholder() {
  return <Placeholder title="서비스 소개" step="10단계" />
}

export function ResultsPlaceholder() {
  return <Placeholder title="분석 결과" step="7단계" />
}

export function CapturePlaceholder() {
  const nav = useNavigate()
  const loc = useLocation()
  const st = loc.state as { dogId?: string; sessionId?: string | null } | null
  return (
    <div className="screen">
      <TopBar title="보행 분석" />
      <div className="scroll screen-body">
        <Empty>
          측정 화면은 다음 단계(4~5단계)에서 붙어요.
          {st?.dogId && (
            <>
              <br />
              <span className="small">반려견 {st.dogId.slice(0, 8)}… {st.sessionId ? '· 진행 중 회차 있음' : ''}</span>
            </>
          )}
        </Empty>
      </div>
      <div className="sticky-footer">
        <Button variant="secondary" onClick={() => nav(-1)}>
          돌아가기
        </Button>
      </div>
    </div>
  )
}

/** 마이페이지 최소판: 담당자·기관 표시와 로그아웃. 나머지는 10단계. */
export function MyPage() {
  const { staff, logout } = useAuth()
  const nav = useNavigate()
  const [sheet, setSheet] = useState(false)
  return (
    <div className="screen">
      <div className="topbar" style={{ padding: '0 20px' }}>
        <b className="topbar-title">마이페이지</b>
      </div>
      <div className="scroll screen-body with-tabs" style={{ gap: 14 }}>
        <Card className="info-card">
          <b>{staff?.institution.name ?? '기관'}</b>
          <div className="info-row">
            <span className="k">담당자</span>
            <div className="v">
              <span>{staff?.name ?? '-'}</span>
            </div>
          </div>
          <div className="info-row">
            <span className="k">아이디</span>
            <div className="v">
              <span>{staff?.login_id ?? '-'}</span>
            </div>
          </div>
          <div className="info-row">
            <span className="k">기관 코드</span>
            <div className="v">
              <span>{staff?.institution.code ?? '-'}</span>
            </div>
          </div>
          <div className="info-row">
            <span className="k">권한</span>
            <div className="v">
              <span>{staff?.role === 'ADMIN' ? '관리자' : '담당자'}</span>
            </div>
          </div>
        </Card>
        <Card className="card-rows">
          <button type="button" className="row-item" onClick={() => nav('/')}>
            <div className="row-icon" style={{ background: 'var(--pri-l)', color: 'var(--pri)' }}>
              <Icon name="paw" size={22} />
            </div>
            <div style={{ flex: 1 }}>
              <div className="row-title">등록 반려견</div>
              <div className="row-sub">홈에서 반려견을 등록하고 수정해요</div>
            </div>
            <Icon name="chev" size={18} style={{ color: 'var(--dim)' }} />
          </button>
          <button type="button" className="row-item" onClick={() => setSheet(true)}>
            <div className="row-icon" style={{ background: 'var(--fill)', color: 'var(--ink2)' }}>
              <Icon name="x" size={22} />
            </div>
            <div style={{ flex: 1 }}>
              <div className="row-title">로그아웃</div>
            </div>
          </button>
        </Card>
      </div>
      <Sheet open={sheet} onClose={() => setSheet(false)}>
        <b className="sheet-title">로그아웃할까요?</b>
        <div className="sheet-actions">
          <Button variant="ghost" onClick={() => setSheet(false)}>
            취소
          </Button>
          <Button
            variant="dark"
            onClick={() => {
              setSheet(false)
              logout()
              nav('/login', { replace: true })
            }}
          >
            로그아웃
          </Button>
        </div>
      </Sheet>
    </div>
  )
}
