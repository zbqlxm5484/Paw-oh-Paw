// my.html: 마이페이지. 기관·측정 기기, 등록 반려견(추가·수정·삭제), 서비스 메뉴
import { useCallback, useEffect, useState } from 'react'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { PostForm, usePage, useTitle } from '../app/page'
import { SEX, link } from '../config'
import { desc } from '../views/views'
import { DeleteModal, LogoutModal, OpenModal, PetModal } from './parts/Modals'
import { dayLabel, daysLeft, listTrash, restoreTrash, type TrashItem } from '../store/trash'
import type { Account } from '../store/types'

/** 반려견 복구 팝업: 휴지통(30일 보관)의 반려견을 한 마리씩 되돌린다 */
function TrashModal({ acct, items, onDone }: { acct: Account; items: TrashItem[]; onDone: () => void }) {
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState('')
  const restore = async (t: TrashItem) => {
    if (busy) return
    setBusy(t.id); setMsg('')
    try {
      await restoreTrash(acct, t.id)
      setMsg(`${t.name}을(를) 복구했습니다`)
      onDone()
    } catch (e) {
      setMsg(e instanceof Error && e.message ? e.message : '복구하지 못했습니다')
    } finally {
      setBusy('')
    }
  }
  return (
    <OpenModal id="trashModal">
      <b style={css('font-size:22px;letter-spacing:-0.5px')}>반려견 복구</b>
      <span style={css('font-size:15px;line-height:1.5;color:#5B6472')}>지운 반려견은 측정 이력·보고서와 함께 30일 동안 보관됩니다. 복구하면 모두 그대로 돌아옵니다.</span>
      {msg ? <span role="status" style={css('font-size:14px;color:#2E8B57;font-weight:600')}>{msg}</span> : null}
      {items.length ? (
        <div style={css('display:flex;flex-direction:column')}>
          {items.map((t, i) => {
            const left = daysLeft(t.purgeAt)
            return (
              <div key={t.id} style={css(`display:flex;align-items:center;gap:12px;min-height:68px;border-top:${i ? '1px solid #F2EFEA' : 'none'}`)}>
                <div style={css('flex:1;min-width:0')}>
                  <div style={css('font-size:15px;font-weight:700')}>{t.name} <span style={css('font-weight:500;color:#5B6472;font-size:14px')}>· {t.breed}</span></div>
                  <div style={css(`font-size:14px;margin-top:2px;color:${left <= 7 ? '#B4501A' : '#5B6472'}`)}>{dayLabel(t.deletedAt)} 삭제 · {left ? `${left}일 뒤 완전히 삭제` : '곧 완전히 삭제'}</div>
                </div>
                <button type="button" className="bt tap" disabled={!!busy} onClick={() => restore(t)} style={css(`height:44px;padding:0 16px;border-radius:10px;border:1px solid #E2DCD3;background:#fff;font-size:14px;font-weight:700;color:#B4501A;cursor:pointer;opacity:${busy && busy !== t.id ? '0.5' : '1'}`)}><span style={css('position:relative;top:-3px')}>{busy === t.id ? '복구 중…' : '복구'}</span></button>
              </div>
            )
          })}
        </div>
      ) : <span style={css('font-size:15px;color:#5B6472;padding:8px 0')}>휴지통이 비어 있습니다.</span>}
      <div data-close="" style={css('height:52px;border-radius:14px;background:#F2EEE8;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:600;cursor:pointer')}>닫기</div>
    </OpenModal>
  )
}

export default function My() {
  useTitle('마이페이지 · Paw oh Paw')
  const { acct, me, toast } = usePage({ login: true })
  // 삭제할 반려견: 시제품은 #delName 글자와 #delForm action 을 바꾼 뒤 연다
  const [del, setDel] = useState({ name: '', action: '', desc: '' })
  // 11-09 QA: 이름이 같은 반려견이 여럿이라 검색으로 좁힌다(이름·견종·동물번호·생년)
  const [mq, setMq] = useState('')
  // 휴지통 목록: 마이페이지를 열 때, 반려견을 지우거나 복구한 뒤 다시 읽는다
  const [trash, setTrash] = useState<TrashItem[]>([])
  const nDogs = acct?.dogs.length ?? 0
  const loadTrash = useCallback(() => { if (acct) listTrash(acct).then(setTrash).catch(() => setTrash([])) }, [acct])
  useEffect(() => { loadTrash() }, [loadTrash, nDogs])
  if (!acct) return null
  const kw = mq.trim()
  const dogs = acct.dogs.filter((d) => !kw || `${d.name} ${d.breed} ${d.no} ${d.birth}`.includes(kw)).map((d, i) => ({
    id: d.id,
    init: Array.from(d.name)[0] || '',
    name: d.name,
    desc: `${desc(d)} · ${SEX[d.sex || 'm'] ?? 'None'}`,
    bt: i ? '1px solid #F2EFEA' : 'none',
  }))

  return (
    <Base acct={acct} me={me} nav="my" toast={toast}
      modals={<><PetModal next_url="/my" /><LogoutModal /><TrashModal acct={acct} items={trash} onDone={loadTrash} /><DeleteModal name={del.name} action={del.action} desc={del.desc} /></>}>
      <main style={css('max-width:none;margin:0;padding:32px 80px 96px;display:flex;flex-direction:column;gap:20px')}>
        <div style={css('display:flex;flex-wrap:wrap;gap:16px;align-items:stretch')}>
          <a className="lk" href={link('/account')} style={css('flex:1 1 360px;min-width:0;background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:24px;display:flex;align-items:center;gap:16px')}>
            <div style={css('width:64px;height:64px;border-radius:50%;background:#EEE8DF;color:#A69D90;display:flex;align-items:center;justify-content:center;flex:none')}><svg width="32" height="32" viewBox="0 0 24 24"><use href="#w-org"></use></svg></div>
            <div style={css('flex:1;min-width:0')}><div style={css('font-size:22px;font-weight:800;letter-spacing:-0.5px')}>{acct.name}</div><div style={css('font-size:15px;color:#5B6472;margin-top:2px')}>기본 정보 보기</div></div>
            <svg width="20" height="20" viewBox="0 0 24 24" style={css('color:#5B6472')}><use href="#w-chev"></use></svg>
          </a>
          <div style={css('flex:1 1 300px;min-width:0;border-radius:18px;background:#F3EEE6;padding:20px 24px;display:flex;align-items:center;justify-content:space-between;gap:12px')}>
            <div><div style={css('font-size:15px;font-weight:700')}>측정 기기</div><div style={css('font-size:14px;color:#5B6472;margin-top:2px;font-variant-numeric:tabular-nums')}>{acct.dev && acct.dev !== '-' ? acct.dev : '등록된 측정 기기가 없습니다'}</div></div>
            {acct.dev && acct.dev !== '-' ? <span style={css('height:34px;padding:0 14px;border-radius:10px;background:#E8F3EC;color:#2E8B57;display:flex;align-items:center;gap:6px;font-size:14px;font-weight:700')}><span style={css('width:7px;height:7px;border-radius:4px;background:#2E8B57')}></span>양호</span> : <span style={css('font-size:14px;color:#5B6472')}>등록된 기기 없음</span>}
          </div>
        </div>
        <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:24px 26px')}>
          <div style={css('display:flex;align-items:center;justify-content:space-between;margin-bottom:10px')}><b style={css('font-size:18px;letter-spacing:-0.4px')}>등록 반려견 <span style={css('color:#5B6472;font-weight:600;font-size:15px')}>{acct.dogs.length}마리</span></b><span style={css('display:flex;gap:8px;align-items:center')}><span data-pet="new" style={css('height:38px;padding:0 14px;border-radius:10px;background:#FCEEE3;color:#B4501A;display:flex;align-items:center;font-size:14px;font-weight:700;cursor:pointer')}>+ 반려견 추가</span>{trash.length ? <span data-open="trashModal" role="button" style={css('height:38px;padding:0 14px;border-radius:10px;border:1px solid #E2DCD3;background:#fff;color:#3A4250;display:flex;align-items:center;font-size:14px;font-weight:700;cursor:pointer')}>반려견 복구 <span style={css('color:#B4501A;margin-left:4px')}>{trash.length}</span></span> : null}</span></div>
          <label style={css('height:42px;border-radius:12px;border:1px solid #E2DCD3;background:#fff;display:flex;align-items:center;gap:8px;padding:0 14px;margin-bottom:6px;color:#5B6472')}>
            <svg width="17" height="17" viewBox="0 0 24 24" style={{ flex: 'none' }}><circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.8"></circle><path d="M16 16l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"></path></svg>
            <input value={mq} onChange={(e) => setMq(e.target.value)} placeholder="이름 · 견종 · 동물번호 · 생년으로 찾기" style={css('flex:1;min-width:0;border:none;outline:none;font-size:15px;background:transparent;color:#1B2433;font-family:inherit')} />
          </label>
          {/* 한 번에 다섯 마리(줄 높이 76px × 5)까지 보이고 나머지는 스크롤 */}
          <div className="dog-scroll" style={css('max-height:380px;overflow-y:auto;overscroll-behavior:contain;padding-right:4px')}>
          {dogs.map((d) => (
            <div key={d.id} style={css(`display:flex;align-items:center;gap:14px;min-height:76px;border-top:${d.bt}`)}>
              <div style={css('width:46px;height:46px;border-radius:50%;background:#FCEEE3;color:#A8481A;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700;flex:none')}>{d.init}</div>
              <div style={css('flex:1;min-width:0')}><div style={css('font-size:15px;font-weight:700')}>{d.name}</div><div style={css('font-size:14px;color:#5B6472;margin-top:2px')}>{d.desc}</div></div>
              <span data-pet={d.id} style={css('height:36px;padding:0 12px;border-radius:9px;border:1px solid #E2DCD3;display:flex;align-items:center;font-size:14px;font-weight:600;cursor:pointer')}>수정</span>
              <span className="del-btn" data-id={d.id} data-name={d.name}
                onClick={() => {
                  setDel({ name: d.name, action: `/dogs/${d.id}/delete`, desc: d.desc })
                  window.ppOpen('delModal')
                }}
                style={css('height:36px;padding:0 12px;margin-left:8px;border-radius:9px;border:1px solid #E2DCD3;display:flex;align-items:center;font-size:14px;font-weight:600;color:#B4501A;cursor:pointer')}>삭제</span>
            </div>
          ))}
          </div>
          {dogs.length === 0 && <div style={css('font-size:15px;color:#5B6472;padding:20px 0')}>{kw ? `‘${kw}’ 에 맞는 반려견이 없습니다.` : '등록된 반려견이 없습니다.'}</div>}
        </div>
        <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:8px 22px;display:flex;flex-direction:column')}>
          <b style={css('font-size:18px;padding:14px 0 6px')}>서비스</b>
          <PostForm action="/my/notif" style={css('margin:0')}>
            <button className="bt" type="submit" style={css('width:100%;background:none;display:flex;align-items:center;gap:14px;min-height:56px;padding:0;color:inherit')}><svg width="22" height="22" viewBox="0 0 24 24"><use href="#w-bell"></use></svg><span style={css('flex:1;font-size:15px')}>분석 완료 알림</span><span style={css(`width:50px;height:30px;border-radius:15px;background:${acct.notif_on ? '#D2601A' : '#DDD7CE'};position:relative;transition:background .2s`)}><span style={css(`position:absolute;top:2px;left:${acct.notif_on ? 22 : 2}px;width:26px;height:26px;border-radius:13px;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.2);transition:left .2s`)}></span></span></button>
          </PostForm>
          <a className="lk" href={link('/about')} style={css('display:flex;align-items:center;gap:14px;min-height:56px')}><svg width="22" height="22" viewBox="0 0 24 24"><use href="#w-doc"></use></svg><span style={css('flex:1;font-size:15px')}>도움말 · 서비스 소개</span><svg width="18" height="18" viewBox="0 0 24 24"><use href="#w-chev"></use></svg></a>
          <a className="lk" href={link('/support')} style={css('display:flex;align-items:center;gap:14px;min-height:56px')}><svg width="22" height="22" viewBox="0 0 24 24"><use href="#w-headset"></use></svg><span style={css('flex:1;font-size:15px')}>고객센터</span><svg width="18" height="18" viewBox="0 0 24 24" style={css('color:#5B6472')}><use href="#w-chev"></use></svg></a>
          <div data-open="logoutModal" style={css('display:flex;align-items:center;min-height:52px;font-size:15px;color:#5B6472;cursor:pointer')}>로그아웃</div>
        </div>
      </main>
    </Base>
  )
}
