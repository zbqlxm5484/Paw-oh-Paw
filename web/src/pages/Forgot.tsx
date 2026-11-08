// forgot.html: 아이디를 넣으면 재설정 링크(시제품은 메일 서버가 없어 링크를 화면에 보여 준다)
import { Base } from '../app/Base'
import { css } from '../app/css'
import { PostForm, useTitle } from '../app/page'
import AuthBar, { usePublicPage } from './parts/AuthBar'
import { link } from '../config'

export default function Forgot() {
  useTitle('비밀번호 찾기 · Paw oh Paw')
  const { me, toast, query } = usePublicPage()
  const sent = query.get('sent') || ''
  const resetLink = query.get('link') || ''

  return (
    <Base me={me} toast={toast} topbar={<AuthBar />}>
      <main style={css('max-width:600px;margin:6vh auto 96px;padding:0 24px')}>
        {sent ? (
          <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:24px;padding:52px 48px;display:flex;flex-direction:column;gap:20px')}>
            <h1 style={css('margin:0;font-size:32px;font-weight:800;letter-spacing:-0.8px')}>메일을 확인해 주세요</h1>
            <p style={css('margin:0;font-size:17px;color:#5B6472;line-height:1.6')}>가입한 아이디라면 등록된 이메일로 비밀번호 재설정 링크를 보냈습니다. 링크는 30분 동안 쓸 수 있습니다.</p>
            {resetLink && <div style={css('border-radius:12px;background:#F2EEE8;padding:14px 18px;font-size:14px;color:#5B6472')}>시제품에는 메일 서버가 없어 링크를 여기에 보여 줍니다 · <a className="lk" href={link(resetLink)} style={css('font-weight:700;color:#D2601A')}>재설정 링크 열기</a></div>}
            <a className="lk" href={link('/login')} style={css('font-size:15px;font-weight:600;color:#1B2433')}>로그인으로 돌아가기</a>
          </div>
        ) : (
          <PostForm action="/forgot" style={css('background:#fff;border:1px solid #ECE8E2;border-radius:24px;padding:52px 48px;display:flex;flex-direction:column;gap:24px')}>
            <div style={css('display:flex;flex-direction:column;gap:8px')}><h1 style={css('margin:0;font-size:32px;font-weight:800;letter-spacing:-0.8px')}>비밀번호 찾기</h1><p style={css('margin:0;font-size:17px;color:#5B6472')}>아이디를 입력하시면 가입할 때 등록한 이메일로 재설정 링크를 보내드립니다.</p></div>
            <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:16px;font-weight:600')}>아이디</span><input className="inp" name="login_id" autoComplete="username" placeholder="아이디" style={css('height:60px;border-radius:12px;border:1px solid #ECE8E2;background:#fff;padding:0 18px;font-size:17px;color:#1B2433;outline:none')} /></label>
            <button className="bt" type="submit" style={css('height:62px;border-radius:14px;background:#D2601A;color:#fff;border:0;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;cursor:pointer')}>재설정 링크 받기</button>
            <a className="lk" href={link('/login')} style={css('align-self:center;font-size:14px;color:#5B6472')}>로그인으로 돌아가기</a>
          </PostForm>
        )}
      </main>
    </Base>
  )
}
