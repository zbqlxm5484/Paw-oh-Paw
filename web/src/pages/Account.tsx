// account.html: 기본 정보(기관·아이디·가입일·계약) + 내 정보·비밀번호 바꾸기
import { Base } from '../app/Base'
import { css } from '../app/css'
import { PostForm, usePage, useTitle } from '../app/page'
import { staffOf } from '../store/db'
import { link } from '../config'

const INP = 'height:52px;border-radius:12px;border:1px solid #ECE8E2;background:#fff;padding:0 16px;font-size:16px;color:#1B2433;outline:none'

export default function Account() {
  useTitle('기본 정보 · Paw oh Paw')
  const { acct, me, toast } = usePage({ login: true, creamoff: true }) // 관리자도 비밀번호·내 정보는 바꾼다
  if (!acct || !me) return null
  const ends = acct.contract_ends
  const rows: [string, string][] = [
    ['기관', acct.name],
    ['아이디', me.login_id],
    ['가입일', me.joined || acct.joined],
    ['계약 종료일', ends ? `${ends.slice(0, 4)}년 ${parseInt(ends.slice(5, 7), 10)}월 ${parseInt(ends.slice(8), 10)}일까지` : '기한 없음'],
    ['같은 기관 담당자', `${staffOf(acct.id).filter((x) => x.active).length}명 · 반려견·회차 자료를 함께 봐요`],
  ]

  return (
    <Base acct={acct} me={me} nav="my" toast={toast}>
      <main style={css('max-width:860px;margin:0 auto;padding:40px 40px 96px;display:flex;flex-direction:column;gap:24px')}>
        <a className="lk" href={link('/my')} style={css('align-self:flex-start;display:flex;align-items:center;gap:4px;font-size:16px;font-weight:600;color:#5B6472')}><svg width="18" height="18" viewBox="0 0 24 24"><use href="#w-back"></use></svg>마이페이지</a>
        <div style={css('display:flex;align-items:center;justify-content:space-between')}><h1 style={css('margin:0;font-size:38px;font-weight:800;letter-spacing:-1px')}>기본 정보</h1></div>
        <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:22px;padding:8px 36px')}>
          {rows.map(([k, v], i) => (
            <div key={k} style={css(`display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:76px;border-top:${i ? '1px solid #F2EFEA' : 'none'}`)}><span style={css('font-size:17px;color:#5B6472')}>{k}</span><span style={css('font-size:18px;font-weight:600;text-align:right')}>{v}</span></div>
          ))}
        </div>
        <PostForm action="/account/profile" style={css('background:#fff;border:1px solid #ECE8E2;border-radius:22px;padding:28px 36px;display:flex;flex-direction:column;gap:16px')}>
          <b style={css('font-size:19px')}>내 정보</b>
          <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:15px;color:#5B6472')}>이름 (기록의 작성자로 남아요)</span><input name="name" defaultValue={me.name} style={css(INP)} /></label>
          <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:15px;color:#5B6472')}>이메일 (비밀번호 재설정 링크를 받아요)</span><input type="email" name="email" defaultValue={me.email} style={css(INP)} /></label>
          <button type="submit" style={css('align-self:flex-end;height:48px;padding:0 22px;border-radius:12px;border:0;background:#1B2433;color:#fff;font-size:16px;font-weight:700;cursor:pointer')}>저장</button>
        </PostForm>
        <PostForm action="/account/password" style={css('background:#fff;border:1px solid #ECE8E2;border-radius:22px;padding:28px 36px;display:flex;flex-direction:column;gap:16px')}>
          <b style={css('font-size:19px')}>비밀번호 변경</b>
          <input type="password" name="current_pw" autoComplete="current-password" placeholder="현재 비밀번호" style={css(INP)} />
          <input type="password" name="pw" autoComplete="new-password" placeholder="새 비밀번호 (8자 이상)" style={css(INP)} />
          <input type="password" name="pw2" autoComplete="new-password" placeholder="새 비밀번호 확인" style={css(INP)} />
          <button type="submit" style={css('align-self:flex-end;height:48px;padding:0 22px;border-radius:12px;border:0;background:#1B2433;color:#fff;font-size:16px;font-weight:700;cursor:pointer')}>바꾸기</button>
        </PostForm>
        <span data-toast="회원 탈퇴는 고객센터로 문의해 주세요" style={css('font-size:15px;color:#A0A7B2;cursor:pointer')}>회원 탈퇴</span>
      </main>
    </Base>
  )
}
