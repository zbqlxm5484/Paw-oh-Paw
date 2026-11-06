// my.html: 마이페이지. 기관·측정 기기, 등록 반려견(추가·수정·삭제), 서비스 메뉴
import { useState } from 'react'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { PostForm, usePage, useTitle } from '../app/page'
import { SEX, link } from '../config'
import { desc } from '../views/views'
import { DeleteModal, LogoutModal, PetModal } from './parts/Modals'

export default function My() {
  useTitle('마이페이지 · Paw oh Paw')
  const { acct, me, toast } = usePage({ login: true })
  // 삭제할 반려견: 시제품은 #delName 글자와 #delForm action 을 바꾼 뒤 연다
  const [del, setDel] = useState({ name: '', action: '' })
  if (!acct) return null
  const dogs = acct.dogs.map((d, i) => ({
    id: d.id,
    init: Array.from(d.name)[0] || '',
    name: d.name,
    desc: `${desc(d)} · ${SEX[d.sex || 'm'] ?? 'None'}`,
    bt: i ? '1px solid #F2EFEA' : 'none',
  }))

  return (
    <Base acct={acct} me={me} nav="my" toast={toast}
      modals={<><PetModal next_url="/my" /><LogoutModal /><DeleteModal name={del.name} action={del.action} /></>}>
      <main style={css('max-width:none;margin:0;padding:32px 80px 96px;display:flex;flex-direction:column;gap:20px')}>
        <div style={css('display:flex;flex-wrap:wrap;gap:16px;align-items:stretch')}>
          <a className="lk" href={link('/account')} style={css('flex:1 1 360px;min-width:0;background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:24px;display:flex;align-items:center;gap:16px')}>
            <div style={css('width:64px;height:64px;border-radius:50%;background:#EEE8DF;color:#A69D90;display:flex;align-items:center;justify-content:center;flex:none')}><svg width="32" height="32" viewBox="0 0 24 24"><use href="#w-org"></use></svg></div>
            <div style={css('flex:1;min-width:0')}><div style={css('font-size:22px;font-weight:800;letter-spacing:-0.5px')}>{acct.name}</div><div style={css('font-size:14.5px;color:#5B6472;margin-top:2px')}>기본 정보 보기</div></div>
            <svg width="20" height="20" viewBox="0 0 24 24" style={css('color:#A0A7B2')}><use href="#w-chev"></use></svg>
          </a>
          <div style={css('flex:1 1 300px;min-width:0;border-radius:18px;background:#F3EEE6;padding:20px 24px;display:flex;align-items:center;justify-content:space-between;gap:12px')}>
            <div><div style={css('font-size:16px;font-weight:700')}>측정 기기</div><div style={css('font-size:14px;color:#5B6472;margin-top:2px;font-variant-numeric:tabular-nums')}>{acct.dev && acct.dev !== '-' ? acct.dev : '측정 기기 정보는 아직 서버에 없어요'}</div></div>
            {acct.dev && acct.dev !== '-' ? <span style={css('height:34px;padding:0 14px;border-radius:10px;background:#E8F3EC;color:#2E8B57;display:flex;align-items:center;gap:6px;font-size:14px;font-weight:700')}><span style={css('width:7px;height:7px;border-radius:4px;background:#2E8B57')}></span>양호</span> : <span style={css('font-size:13.5px;color:#8E949C')}>등록된 기기 없음</span>}
          </div>
        </div>
        <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:24px 26px')}>
          <div style={css('display:flex;align-items:center;justify-content:space-between;margin-bottom:10px')}><b style={css('font-size:20px;letter-spacing:-0.4px')}>등록 반려견 <span style={css('color:#A0A7B2;font-weight:600;font-size:16px')}>{dogs.length}마리</span></b><span data-pet="new" style={css('height:38px;padding:0 14px;border-radius:10px;background:#FCEEE3;color:#B4501A;display:flex;align-items:center;font-size:14px;font-weight:700;cursor:pointer')}>+ 반려견 추가</span></div>
          {/* 한 번에 다섯 마리(줄 높이 76px × 5)까지 보이고 나머지는 스크롤 */}
          <div className="dog-scroll" style={css('max-height:380px;overflow-y:auto;overscroll-behavior:contain;padding-right:4px')}>
          {dogs.map((d) => (
            <div key={d.id} style={css(`display:flex;align-items:center;gap:14px;min-height:76px;border-top:${d.bt}`)}>
              <div style={css('width:46px;height:46px;border-radius:50%;background:#FCEEE3;color:#A8481A;display:flex;align-items:center;justify-content:center;font-weight:700;flex:none')}>{d.init}</div>
              <div style={css('flex:1;min-width:0')}><div style={css('font-size:16px;font-weight:700')}>{d.name}</div><div style={css('font-size:13.5px;color:#5B6472;margin-top:2px')}>{d.desc}</div></div>
              <span data-pet={d.id} style={css('height:36px;padding:0 12px;border-radius:9px;border:1px solid #E2DCD3;display:flex;align-items:center;font-size:14px;font-weight:600;cursor:pointer')}>수정</span>
              <span className="del-btn" data-id={d.id} data-name={d.name}
                onClick={() => {
                  setDel({ name: d.name, action: `/dogs/${d.id}/delete` })
                  window.ppOpen('delModal')
                }}
                style={css('height:36px;padding:0 12px;border-radius:9px;display:flex;align-items:center;font-size:14px;font-weight:600;color:#C2412D;cursor:pointer')}>삭제</span>
            </div>
          ))}
          </div>
          {dogs.length === 0 && <div style={css('font-size:15px;color:#5B6472;padding:20px 0')}>등록된 반려견이 없어요.</div>}
        </div>
        <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:8px 22px;display:flex;flex-direction:column')}>
          <b style={css('font-size:17px;padding:14px 0 6px')}>서비스</b>
          <PostForm action="/my/notif" style={css('margin:0')}>
            <button className="bt" type="submit" style={css('width:100%;background:none;display:flex;align-items:center;gap:14px;min-height:56px;padding:0;color:inherit')}><svg width="22" height="22" viewBox="0 0 24 24"><use href="#w-bell"></use></svg><span style={css('flex:1;font-size:15.5px')}>분석 완료 알림</span><span style={css(`width:50px;height:30px;border-radius:15px;background:${acct.notif_on ? '#D2601A' : '#DDD7CE'};position:relative;transition:background .2s`)}><span style={css(`position:absolute;top:2px;left:${acct.notif_on ? 22 : 2}px;width:26px;height:26px;border-radius:13px;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.2);transition:left .2s`)}></span></span></button>
          </PostForm>
          <a className="lk" href={link('/about')} style={css('display:flex;align-items:center;gap:14px;min-height:56px')}><svg width="22" height="22" viewBox="0 0 24 24"><use href="#w-doc"></use></svg><span style={css('flex:1;font-size:16px')}>도움말 · 서비스 소개</span><svg width="18" height="18" viewBox="0 0 24 24"><use href="#w-chev"></use></svg></a>
          <a className="lk" href={link('/support')} style={css('display:flex;align-items:center;gap:14px;min-height:56px')}><svg width="22" height="22" viewBox="0 0 24 24"><use href="#w-headset"></use></svg><span style={css('flex:1;font-size:15.5px')}>고객센터</span><svg width="18" height="18" viewBox="0 0 24 24" style={css('color:#A0A7B2')}><use href="#w-chev"></use></svg></a>
          <div data-open="logoutModal" style={css('display:flex;align-items:center;min-height:52px;font-size:15px;color:#5B6472;cursor:pointer')}>로그아웃</div>
        </div>
      </main>
    </Base>
  )
}
