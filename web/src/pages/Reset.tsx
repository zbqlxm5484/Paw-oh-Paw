// reset.html: 메일 링크의 token 으로 새 비밀번호 정하기
import { Base } from '../app/Base'
import { css } from '../app/css'
import { PostForm, useTitle } from '../app/page'
import AuthBar, { usePublicPage } from './parts/AuthBar'
import { link } from '../config'

const INP = 'height:58px;border-radius:12px;border:1px solid #ECE8E2;background:#fff;padding:0 18px;font-size:18px;color:#1B2433;outline:none'

export default function Reset() {
  useTitle('비밀번호 재설정 · Paw oh Paw')
  const { me, toast, query } = usePublicPage()
  const token = query.get('token') || ''

  // 메일 링크가 아니라 주소를 직접 열면 토큰이 없다. 폼을 보여 줘도 서버가 거절(422)하므로 바로 안내한다
  if (!token) {
    return (
      <Base me={me} toast={toast} topbar={<AuthBar />}>
        <main style={css('max-width:600px;margin:6vh auto 96px;padding:0 24px')}>
          <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:24px;padding:52px 48px;display:flex;flex-direction:column;gap:20px')}>
            <h1 style={css('margin:0;font-size:28px;font-weight:800;letter-spacing:-0.8px')}>재설정 링크가 필요합니다</h1>
            <p style={css('margin:0;font-size:18px;color:#5B6472;line-height:1.6')}>비밀번호는 메일로 받은 재설정 링크에서만 바꿀 수 있습니다. 링크는 30분 동안만 쓸 수 있으니 지났으면 다시 받아 주세요.</p>
            <a className="lk hv-orange" href={link('/forgot')} style={css('align-self:flex-start;height:52px;padding:0 22px;border-radius:14px;background:#D2601A;color:#fff;display:flex;align-items:center;font-size:15px;font-weight:700')}>재설정 링크 받기</a>
          </div>
        </main>
      </Base>
    )
  }

  return (
    <Base me={me} toast={toast} topbar={<AuthBar />}>
      <main style={css('max-width:600px;margin:6vh auto 96px;padding:0 24px')}>
        <PostForm action="/reset-password" style={css('background:#fff;border:1px solid #ECE8E2;border-radius:24px;padding:52px 48px;display:flex;flex-direction:column;gap:24px')}>
          <div style={css('display:flex;flex-direction:column;gap:8px')}><h1 style={css('margin:0;font-size:28px;font-weight:800;letter-spacing:-0.8px')}>새 비밀번호</h1><p style={css('margin:0;font-size:18px;color:#5B6472')}>새 비밀번호를 정하면 바로 로그인 화면으로 갑니다.</p></div>
          <input type="hidden" name="token" value={token} />
          <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:15px;font-weight:600')}>새 비밀번호</span><input className="inp" type="password" name="pw" autoComplete="new-password" placeholder="새 비밀번호" style={css(INP)} /></label>
          <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:15px;font-weight:600')}>새 비밀번호 확인</span><input className="inp" type="password" name="pw2" autoComplete="new-password" placeholder="새 비밀번호 확인" style={css(INP)} /></label>
          <button className="bt" type="submit" style={css('height:62px;border-radius:14px;background:#D2601A;color:#fff;border:0;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;cursor:pointer')}>비밀번호 바꾸기</button>
        </PostForm>
      </main>
    </Base>
  )
}
