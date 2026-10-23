import { useDeferredValue, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useDogs } from '../../api/dogs'
import { dogDesc, fmtMonthDay } from '../../api/labels'
import type { DogOut } from '../../api/types'
import { useAuth } from '../../app/auth'
import { useToast } from '../../app/toast'
import { Icon } from '../../components/Icon'
import { Avatar, Button, Card, Empty } from '../../components/ui'
import './dogs.css'

/** S1 홈·반려견 목록. 디자인 v5 `home`. */
export function HomePage() {
  const { staff } = useAuth()
  const nav = useNavigate()
  const toast = useToast()
  const [q, setQ] = useState('')
  const dq = useDeferredValue(q.trim())
  const { data, isPending, isError, error } = useDogs({ q: dq || undefined, size: 100 })

  const dogsList = data?.items ?? []
  const total = data?.total ?? 0
  const searching = dq.length > 0
  const noDogs = !isPending && !searching && total === 0
  const measuring = dogsList.find((d) => d.open_session_id)

  function goCapture() {
    if (noDogs) {
      toast('먼저 반려견을 등록해 주세요')
      nav('/dogs/new')
      return
    }
    nav('/capture')
  }

  return (
    <div className="screen">
      <div className="home-head">
        <div>
          <div className="home-kind">{staff?.institution.name ?? '기관'}</div>
          <div className="home-name">{staff ? `${staff.name} 담당자` : ''}</div>
        </div>
        <div style={{ display: 'flex' }}>
          <button type="button" className="icon-btn" aria-label="알림" onClick={() => toast('알림은 다음 단계에서 붙어요')}>
            <Icon name="bell" />
          </button>
          <button type="button" className="icon-btn" aria-label="마이페이지" onClick={() => nav('/my')}>
            <Icon name="user" />
          </button>
        </div>
      </div>

      <div style={{ padding: '0 20px 14px' }}>
        <label className="search">
          <Icon name="search" size={20} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="반려견 이름 검색" aria-label="반려견 이름 검색" />
        </label>
      </div>

      <div className="scroll with-tabs" style={{ padding: '0 20px 12px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {noDogs && (
          <Card className="first-dog">
            <Icon name="paw" size={36} style={{ color: 'var(--pri)' }} />
            <b style={{ fontSize: 19, letterSpacing: -0.4 }}>첫 반려견을 등록해 주세요</b>
            <span style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--sub)' }}>이름·견종·체중만 있으면 바로 보행 측정을 시작할 수 있어요.</span>
            <Button size="md" style={{ width: 'auto', padding: '0 18px', marginTop: 6 }} onClick={() => nav('/dogs/new')}>
              반려견 등록하기
            </Button>
          </Card>
        )}

        <Card className="card-rows" >
          {measuring && (
            <button type="button" className="row-item" onClick={() => nav(`/sessions/${measuring.open_session_id}`)}>
              <div className="row-icon" style={{ background: '#141B22' }}>
                <span className="live-dot" />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="row-title">{measuring.name} 측정 중</div>
                <div className="row-sub">진행 중인 회차가 있어요. 눌러서 이어서 측정하거나 분석 상태를 봐요.</div>
              </div>
              <Icon name="chev" size={18} style={{ color: 'var(--dim)' }} />
            </button>
          )}
          <button type="button" className="row-item" onClick={goCapture}>
            <div className="row-icon" style={{ background: 'var(--pri)', color: '#fff' }}>
              <Icon name="cam" size={22} />
            </div>
            <div style={{ flex: 1 }}>
              <div className="row-title">보행 촬영</div>
              <div className="row-sub">영상을 찍거나 갤러리에서 불러와 바로 분석해요</div>
            </div>
            <Icon name="chev" size={18} style={{ color: 'var(--dim)' }} />
          </button>
          <button type="button" className="row-item" onClick={() => nav('/results')}>
            <div className="row-icon" style={{ background: 'var(--pri-l)', color: 'var(--pri)' }}>
              <Icon name="doc" size={22} />
            </div>
            <div style={{ flex: 1 }}>
              <div className="row-title">분석 결과 · 보고서</div>
              <div className="row-sub">회차 결과 · 보호자용 · 수의사용</div>
            </div>
            <Icon name="chev" size={18} style={{ color: 'var(--dim)' }} />
          </button>
        </Card>

        {(total > 0 || searching) && (
          <>
            <div className="section-title">
              <b>
                등록 반려견<span className="count">{searching ? `${total}마리 검색됨` : `${total}마리`}</span>
              </b>
              <Button size="sm" className="btn-soft" onClick={() => nav('/dogs/new')}>
                + 등록
              </Button>
            </div>
            {isError && <Empty>{error instanceof Error ? error.message : '목록을 불러오지 못했어요'}</Empty>}
            {dogsList.map((d) => (
              <DogRow key={d.id} dog={d} onOpen={() => nav(`/dogs/${d.id}`)} />
            ))}
            {!isPending && searching && dogsList.length === 0 && (
              <div style={{ padding: '28px 12px', textAlign: 'center', fontSize: 14, color: 'var(--sub)' }}>‘{dq}’ 이름의 반려견이 없어요</div>
            )}
          </>
        )}
        {isPending && (
          <>
            <div className="skeleton" />
            <div className="skeleton" />
          </>
        )}
      </div>
    </div>
  )
}

function DogRow({ dog, onOpen }: { dog: DogOut; onOpen: () => void }) {
  const meta = dog.session_count
    ? `마지막 측정 ${dog.last_measured_on ? fmtMonthDay(dog.last_measured_on) : '진행 중'} · ${dog.session_count}회차`
    : '아직 측정 기록이 없어요'
  return (
    <Card className="dog-row" onClick={onOpen}>
      <Avatar name={dog.name} />
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <b style={{ fontSize: 16.5, letterSpacing: -0.3 }}>{dog.name}</b>
          {dog.open_session_id && <span className="live-chip">측정 중</span>}
        </div>
        <span className="ellipsis" style={{ fontSize: 13, color: 'var(--sub)' }}>
          {dogDesc(dog)}
        </span>
        <span className="tabular" style={{ fontSize: 12.5, color: 'var(--dim2)' }}>
          {meta}
        </span>
      </div>
      <Icon name="chev" size={18} style={{ color: 'var(--dim)', flex: 'none' }} />
    </Card>
  )
}
