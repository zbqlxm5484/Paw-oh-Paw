// reset.html: 메일 링크의 token 으로 새 비밀번호 정하기
import { Base } from '../app/Base'
import { css } from '../app/css'
import { PostForm, useTitle } from '../app/page'
import AuthBar, { usePublicPage } from './parts/AuthBar'

const INP = 'height:58px;border-radius:12px;border:1px solid #ECE8E2;background:#fff;padding:0 18px;font-size:17px;color:#1B2433;outline:none'

export default function Reset() {
  useTitle('비밀번호 재설정 · Paw oh Paw')
  const { me, toast, query } = usePublicPage()
  const token = query.get('token') || ''

  return (
    <Base me={me} toast={toast} topbar={<AuthBar />}>
      <main style={css('max-width:560px;margin:6vh auto 96px;padding:0 24px')}>
        <PostForm action="/reset-password" style={css('background:#fff;border:1px solid #ECE8E2;border-radius:24px;padding:48px 44px;display:flex;flex-direction:column;gap:22px')}>
          <div style={css('display:flex;flex-direction:column;gap:8px')}><h1 style={css('margin:0;font-size:28px;font-weight:800;letter-spacing:-0.6px')}>새 비밀번호</h1><p style={css('margin:0;font-size:16px;color:#5B6472')}>새 비밀번호를 정하면 바로 로그인 화면으로 가요.</p></div>
          <input type="hidden" name="token" value={token} />
          <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:16px;font-weight:600')}>새 비밀번호</span><input className="inp" type="password" name="pw" autoComplete="new-password" placeholder="8자 이상" style={css(INP)} /></label>
          <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:16px;font-weight:600')}>새 비밀번호 확인</span><input className="inp" type="password" name="pw2" autoComplete="new-password" style={css(INP)} /></label>
          <button className="bt" type="submit" style={css('height:60px;border-radius:14px;background:#D2601A;color:#fff;border:0;font-size:18px;font-weight:700;cursor:pointer')}>비밀번호 바꾸기</button>
        </PostForm>
      </main>
    </Base>
  )
}
