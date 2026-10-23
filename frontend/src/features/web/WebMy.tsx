import { useNavigate } from 'react-router-dom'

import { useDogs } from '../../api/dogs'
import { dogDesc } from '../../api/labels'
import { useAuth } from '../../app/auth'
import { Icon } from '../../components/Icon'

/** 웹 v2 마이페이지. 측정 기기·알림·고객센터는 API 가 없어 두지 않는다. 로그아웃은 상단 계정 메뉴에 있다. */
export function WebMy() {
  const { staff } = useAuth()
  const nav = useNavigate()
  const dogsQ = useDogs({ size: 100 })
  const dogs = dogsQ.data?.items ?? []
  return (
    <main className="web-main" style={{ gap: 20 }}>
      <button type="button" className="web-card" style={{ padding: 24, display: 'flex', alignItems: 'center', gap: 16, cursor: 'pointer', textAlign: 'left', font: 'inherit', color: 'inherit', width: '100%' }} onClick={() => nav('/account')}>
        <div style={{ width: 64, height: 64, borderRadius: '50%', background: '#EEE8DF', color: '#A69D90', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
          <Icon name="org" size={32} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.5 }}>{staff?.institution.name ?? '기관'}</div>
          <div style={{ fontSize: 14.5, color: 'var(--sub)', marginTop: 2 }}>
            {staff?.name ?? ''} · 기본 정보 보기
          </div>
        </div>
        <Icon name="chev" size={20} style={{ color: 'var(--dim)' }} />
      </button>

      <div className="web-card" style={{ padding: '24px 26px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <b style={{ fontSize: 20, letterSpacing: -0.4 }}>
            등록 반려견 <span style={{ color: 'var(--dim)', fontWeight: 600, fontSize: 16 }}>{dogs.length}마리</span>
          </b>
          <button type="button" className="web-btn" style={{ height: 38, background: 'var(--pri-l)', borderColor: 'transparent', color: 'var(--pri-d)', fontWeight: 700 }} onClick={() => nav('/dogs/new')}>
            + 등록
          </button>
        </div>
        {dogs.map((d, i) => (
          <div key={d.id} style={{ display: 'flex', alignItems: 'center', gap: 14, minHeight: 76, borderTop: i ? '1px solid var(--line2)' : 'none' }}>
            <div className="avatar" style={{ width: 46, height: 46, fontSize: 17 }}>
              {d.name.charAt(0)}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 16, fontWeight: 700 }}>{d.name}</div>
              <div style={{ fontSize: 13.5, color: 'var(--sub)', marginTop: 2 }}>{dogDesc(d)}</div>
            </div>
            <button type="button" className="web-btn" style={{ height: 36, padding: '0 12px', fontSize: 14 }} onClick={() => nav(`/?dog=${d.id}`)}>
              보기
            </button>
            <button type="button" className="web-btn" style={{ height: 36, padding: '0 12px', fontSize: 14 }} onClick={() => nav(`/dogs/${d.id}/edit`)}>
              수정
            </button>
          </div>
        ))}
        {dogsQ.isSuccess && dogs.length === 0 && <div style={{ fontSize: 15, color: 'var(--sub)', padding: '20px 0' }}>등록된 반려견이 없어요.</div>}
      </div>
    </main>
  )
}

/** 웹 v2 기본 정보. 수정·탈퇴 API 가 없어 보기만 한다. */
export function WebAccount() {
  const { staff } = useAuth()
  const nav = useNavigate()
  const rows: [string, string][] = [
    ['기관', staff?.institution.name ?? '-'],
    ['기관 코드', staff?.institution.code ?? '-'],
    ['담당자', staff?.name ?? '-'],
    ['아이디', staff?.login_id ?? '-'],
    ['권한', staff?.role === 'ADMIN' ? '관리자' : '담당자'],
  ]
  return (
    <main className="web-main narrow" style={{ maxWidth: 860, gap: 24, padding: '40px 40px 96px' }}>
      <button type="button" className="web-back" style={{ fontSize: 16 }} onClick={() => nav('/my')}>
        <Icon name="back" size={18} />
        마이페이지
      </button>
      <h1 className="web-h1" style={{ fontSize: 38 }}>
        기본 정보
      </h1>
      <div className="web-card" style={{ borderRadius: 22, padding: '8px 36px' }}>
        {rows.map(([k, v], i) => (
          <div key={k} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, minHeight: 76, borderTop: i ? '1px solid var(--line2)' : 'none' }}>
            <span style={{ fontSize: 17, color: 'var(--sub)' }}>{k}</span>
            <span style={{ fontSize: 18, fontWeight: 600, textAlign: 'right' }}>{v}</span>
          </div>
        ))}
      </div>
      <span style={{ fontSize: 14, color: 'var(--dim)' }}>계정 정보 수정과 탈퇴는 기관 관리자에게 요청해 주세요.</span>
    </main>
  )
}
