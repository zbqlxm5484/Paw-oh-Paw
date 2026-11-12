// expired.html: 계약이 끝난 기관 담당자(GUEST)는 로그인은 되고 이 화면만 보인다. ?demo=1 은 만료 기관 예시 계정(s_exp)
import { useEffect } from 'react'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { PostForm, useTitle } from '../app/page'
import { currentStaff, need_login } from '../app/session'
import { db, getAccount } from '../store/db'
import AuthBar, { usePublicPage } from './parts/AuthBar'
import { SUPPORT } from '../legal/content'

export default function Expired() {
  useTitle('이용 계약 만료 · Paw oh Paw')
  const { me, toast, query, go } = usePublicPage()
  const demo = query.get('demo') || ''
  const s = demo ? db.staff['s_exp'] : currentStaff()
  useEffect(() => {
    if (!s) go(need_login())
  })
  if (!s) return null
  const acct = getAccount(s.inst)
  const inst = acct ? acct.name : ''
  const ends = acct ? acct.contract_ends || '' : ''

  return (
    <Base me={me} toast={toast} topbar={<AuthBar />}>
      <main style={css('max-width:600px;margin:8vh auto 96px;padding:0 24px')}>
        <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:24px;padding:52px 48px;display:flex;flex-direction:column;gap:20px')}>
          <span style={css('align-self:flex-start;height:30px;padding:0 12px;border-radius:999px;background:#FBEAE6;color:#C2412D;font-size:14px;font-weight:700;display:flex;align-items:center')}>계약 만료</span>
          <h1 style={css('margin:0;font-size:28px;font-weight:800;letter-spacing:-0.8px')}>{inst}의 이용 계약이 만료되었습니다</h1>
          <p style={css('margin:0;font-size:18px;color:#5B6472;line-height:1.6')}>{ends ? `계약 종료일은 ${ends.slice(0, 4)}년 ${parseInt(ends.slice(5, 7), 10)}월 ${parseInt(ends.slice(8), 10)}일이었습니다. ` : ''}지금은 반려견·측정 자료를 볼 수 없습니다. 재계약하면 같은 계정으로 바로 다시 쓸 수 있고, 그동안의 자료는 그대로 보관됩니다.</p>
          <div style={css('border-radius:14px;background:#F2EEE8;padding:18px 20px;display:flex;flex-direction:column;gap:6px;font-size:15px;color:#3A4250')}><b>고객센터</b><span>{SUPPORT.email}{SUPPORT.placeholder ? ' (준비 중)' : ''}</span></div>
          <div style={css('display:flex;gap:10px;align-items:center')}><span style={css('font-size:14px;color:#5B6472')}>{s.name} · {s.login_id}</span>
            <PostForm action="/logout" style={css('margin-left:auto')}><button type="submit" style={css('height:48px;padding:0 22px;border-radius:12px;border:1px solid #E2DCD3;background:#fff;font-size:15px;font-weight:600;cursor:pointer')}>로그아웃</button></PostForm></div>
        </div>
      </main>
    </Base>
  )
}
