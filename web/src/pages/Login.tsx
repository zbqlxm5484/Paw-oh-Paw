// login.html: 아이디 + 비밀번호(기관 코드 없음). 둘 다 넣어야 버튼이 주황색
import { useState } from 'react'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { PostForm, useTitle } from '../app/page'
import AuthBar, { usePublicPage } from './parts/AuthBar'

export default function Login() {
  useTitle('로그인 · Paw oh Paw')
  const { me, toast } = usePublicPage()
  const [id, setId] = useState('')
  const [pw, setPw] = useState('')
  const ok = () => id.length >= 1 && pw.length >= 1

  return (
    <Base me={me} toast={toast} topbar={<AuthBar />}>
      <main style={css('max-width:600px;margin:6vh auto 96px;padding:0 24px')}>
        <PostForm action="/login" id="loginForm" style={css('background:#fff;border:1px solid #ECE8E2;border-radius:24px;padding:52px 48px;display:flex;flex-direction:column;gap:24px')}
          onBefore={() => {
            if (!ok()) {
              window.ppToast('아이디와 비밀번호를 입력해 주세요')
              return false
            }
          }}>
          <div style={css('display:flex;flex-direction:column;gap:8px')}><h1 style={css('margin:0;font-size:32px;font-weight:800;letter-spacing:-0.8px')}>로그인</h1><p style={css('margin:0;font-size:17px;color:#5B6472')}>동물병원·재활센터 계정으로 로그인해요.</p></div>
          <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:16px;font-weight:600')}>아이디</span><input className="inp" name="login_id" id="liId" autoComplete="username" placeholder="가입할 때 만든 아이디 (기관 코드는 넣지 않아요)" onInput={(e) => setId(e.currentTarget.value)} style={css('height:60px;border-radius:12px;border:1px solid #ECE8E2;background:#fff;padding:0 18px;font-size:17px;color:#1B2433;outline:none')} /></label>
          <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:16px;font-weight:600')}>비밀번호</span><input className="inp" type="password" name="password" id="liPw" autoComplete="current-password" placeholder="비밀번호" onInput={(e) => setPw(e.currentTarget.value)} style={css('height:60px;border-radius:12px;border:1px solid #ECE8E2;background:#fff;padding:0 18px;font-size:17px;color:#1B2433;outline:none')} /></label>
          <button className="bt" type="submit" id="liBtn" style={css(`height:62px;border-radius:14px;background:${ok() ? '#D2601A' : '#C3C8CF'};color:#fff;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700`)}>로그인</button>
          <div style={css('display:flex;justify-content:space-between;align-items:center')}><a className="lk" href="/forgot" style={css('font-size:15px;color:#5B6472')}>비밀번호를 잊으셨나요?</a><a className="lk" href="/signup" style={css('font-size:15px;font-weight:600;color:#D2601A')}>디바이스 코드로 회원가입</a></div>
        </PostForm>
        <PostForm action="/login/demo" style={css('margin-top:16px;text-align:center')}><button type="submit" style={css('border:0;background:none;font-size:15px;color:#5B6472;text-decoration:underline;cursor:pointer')}>시연용 예시 기관으로 둘러보기</button></PostForm>
      </main>
    </Base>
  )
}
