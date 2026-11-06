// signup.html: 디바이스 코드 확인 → 내 계정 → 약관 동의. 코드를 고치면 다시 확인해야 한다
import { useRef, useState } from 'react'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { PostForm, useTitle } from '../app/page'
import { DEMO_CODE } from '../store/demo'
import { show_code } from '../store/db'
import { api_device_code_verify } from '../store/actions_impl'
import { ApiError } from '../api/client'
import { api, MOCK } from '../store/backend'
import AuthBar, { usePublicPage } from './parts/AuthBar'
import { link } from '../config'
import { LEGAL_PATH, TERM_LINKS } from '../legal/content'

const INP = 'height:52px;border-radius:12px;border:1px solid #ECE8E2;background:#fff;padding:0 16px;font-size:16px;color:#1B2433;outline:none'
const TERMS = ['[필수] 서비스 이용약관', '[필수] 개인정보 수집 및 이용', '[필수] 측정 기기 연동 및 위치정보 이용', '[선택] 마케팅 정보 수신']

interface Verified {
  institution: { id: string; name: string }
  /** 백엔드 192(기관당 코드 하나, 계정 수 제한 없음) 뒤에는 응답에 없다 */
  remaining_accounts?: number
}

export default function Signup() {
  useTitle('회원가입 · Paw oh Paw')
  const { me, toast } = usePublicPage()
  const demo_code = show_code(DEMO_CODE)
  const codeRef = useRef<HTMLInputElement>(null)
  const [verified, setVerified] = useState(false)
  const [inst, setInst] = useState<Verified | null>(null)
  const [msg, setMsg] = useState<{ text: string; color: string } | null>(null) // null = 처음 안내(시연용 코드 포함)
  const [terms, setTerms] = useState([false, false, false, false])
  const [, setTick] = useState(0)
  const paint = () => setTick((t) => t + 1)

  const v = (n: string): string => {
    const el = codeRef.current?.form?.elements.namedItem(n) as HTMLInputElement | null
    return el ? el.value : ''
  }
  const idOk = () => /^[a-z0-9._-]{4,50}$/.test(v('login_id'))
  const mailOk = () => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v('email').trim())
  const ok = () => verified && terms[0] && terms[1] && terms[2] && !!v('name').trim() && mailOk() && idOk() && v('pw').length >= 8 && v('pw') === v('pw2')

  const reset = () => {
    setVerified(false)
    setInst(null)
  }
  const verify = async () => {
    if (verified) return
    const code = codeRef.current?.value || ''
    // 백엔드 모드: 관리자 API 로 발급한 코드를 서버에서 확인한다. 가짜 서버 모드만 시연 코드(브라우저 저장소)로 확인
    let r: Awaited<ReturnType<typeof api.verifyCode>> | { error: string }
    if (MOCK) r = api_device_code_verify(code)
    else {
      try {
        r = await api.verifyCode(code)
      } catch (e) {
        r = { error: e instanceof ApiError ? e.message : '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.' }
      }
    }
    if ('error' in r) {
      setMsg({ text: r.error, color: '#C2412D' })
      return
    }
    setVerified(true)
    setInst(r)
    setMsg({ text: '코드가 확인됐어요. 기관은 코드로 정해져서 따로 입력하지 않아요.', color: '#2E8B57' })
  }
  const allOn = terms.every(Boolean)
  const check = (on: boolean) => (on ? '#D2601A' : '#C9C4BC')

  return (
    <Base me={me} toast={toast} topbar={<AuthBar />}>
      <main style={css('max-width:560px;margin:24px auto 96px;padding:0 24px')}>
        <PostForm action="/signup" id="soForm" style={css('background:#fff;border:1px solid #ECE8E2;border-radius:20px;padding:36px 32px;display:flex;flex-direction:column;gap:18px')}
          onBefore={() => {
            if (!verified) {
              window.ppToast('디바이스 코드를 먼저 확인해 주세요')
              return false
            }
            if (!ok()) {
              window.ppToast('입력하지 않은 항목이 있어요')
              return false
            }
          }}>
          <div style={css('display:flex;flex-direction:column;gap:8px')}><h1 style={css('margin:0;font-size:26px;font-weight:800;letter-spacing:-0.6px')}>회원가입</h1><p style={css('margin:0;font-size:15px;color:#5B6472')}>크림오프가 기관에 보내 드린 디바이스 코드로 가입해요. 같은 기관 담당자는 반려견·회차 자료를 함께 봐요.</p></div>

          <b style={css('font-size:16px;margin-top:4px')}>1. 디바이스 코드 확인</b>
          <div style={css('display:flex;gap:10px')}>
            <input className="inp" name="code" id="soCode" ref={codeRef} autoComplete="off" placeholder="XXXXX-XXXXX-XXXXX-XXXXX" onInput={reset} style={css(`${INP};flex:1;letter-spacing:1px;text-transform:uppercase`)} />
            <button type="button" id="soVerify" onClick={verify} style={css(`height:52px;padding:0 20px;border-radius:12px;border:0;background:${verified ? '#2E8B57' : '#1B2433'};color:#fff;font-size:16px;font-weight:700;cursor:pointer;flex:none`)}>{verified ? '인증됨' : '확인'}</button>
          </div>
          {msg ? (
            <span id="soCodeMsg" style={css(`font-size:13px;color:${msg.color};margin-top:-10px`)}>{msg.text}</span>
          ) : (
            <span id="soCodeMsg" style={css('font-size:13px;color:#5B6472;margin-top:-10px')}>크림오프 계약 안내 메일에 적힌 20자 코드예요.{MOCK ? <> 시연용 코드: <b style={css('cursor:pointer;color:#D2601A')} id="soDemo"
              onClick={() => {
                if (codeRef.current) codeRef.current.value = demo_code
                reset()
              }}>{demo_code}</b></> : null}</span>
          )}
          <div id="soInst" style={css(`display:${verified ? 'flex' : 'none'};height:56px;border-radius:12px;background:#F2EEE8;align-items:center;gap:12px;padding:0 18px`)}><svg width="20" height="20" viewBox="0 0 24 24" style={css('color:#2E8B57')}><use href="#w-check"></use></svg><span style={css('font-size:13px;color:#5B6472')}>기관</span><b id="soInstName" style={css('font-size:16px')}>{inst ? inst.institution.name : ''}</b><span id="soLeft" style={css('margin-left:auto;font-size:13px;color:#5B6472')}>{inst && typeof inst.remaining_accounts === 'number' ? `남은 계정 ${inst.remaining_accounts}개` : ''}</span></div>

          <fieldset id="soRest" disabled={!verified} style={css(`border:0;padding:0;margin:0;display:flex;flex-direction:column;gap:18px;opacity:${verified ? '1' : '.45'}`)}>
            <b style={css('font-size:16px;margin-top:10px')}>2. 내 계정</b>
            <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:14px;font-weight:600')}>이름</span><input className="inp so" name="name" autoComplete="name" placeholder="예) 정하늘" onInput={paint} style={css(INP)} /><span style={css('font-size:13px;color:#5B6472')}>차팅·측정 기록에 작성자로 남아요.</span></label>
            <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:14px;font-weight:600')}>이메일</span><input className="inp so" type="email" name="email" autoComplete="email" placeholder="비밀번호를 잊었을 때 재설정 링크를 받아요" onInput={paint} style={css(INP)} /></label>
            <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:14px;font-weight:600')}>아이디</span><input className="inp so" name="login_id" autoComplete="username" placeholder="영문 소문자·숫자·. _ - 4자 이상" onInput={paint} style={css(INP)} /><span id="idHint" style={css(`font-size:13px;color:#C2412D;display:${v('login_id') && !idOk() ? 'block' : 'none'}`)}>영문 소문자·숫자·. _ - 로 4~50자예요</span></label>
            <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:14px;font-weight:600')}>비밀번호</span><input className="inp so" type="password" name="pw" autoComplete="new-password" placeholder="8자 이상" onInput={paint} style={css(INP)} /></label>
            <label style={css('display:flex;flex-direction:column;gap:8px')}><span style={css('font-size:14px;font-weight:600')}>비밀번호 확인</span><input className="inp so" type="password" name="pw2" autoComplete="new-password" placeholder="한 번 더 입력" onInput={paint} style={css(INP)} /><span id="pwHint" style={css(`font-size:13px;color:#C2412D;display:${v('pw2') && v('pw') !== v('pw2') ? 'block' : 'none'}`)}>비밀번호가 달라요</span></label>
            <div style={css('display:flex;flex-direction:column;gap:4px;margin-top:4px')}>
              <b style={css('font-size:16px;margin-bottom:8px')}>약관 동의</b>
              <div id="allTerms" onClick={() => setTerms(terms.map(() => !allOn))} style={css('height:56px;border-radius:12px;background:#F2EEE8;display:flex;align-items:center;gap:14px;padding:0 18px;cursor:pointer')}><svg width="20" height="20" viewBox="0 0 24 24" style={css(`color:${check(allOn)}`)}><use href="#w-check"></use></svg><span style={css('font-size:16px;font-weight:600')}>모두 동의합니다.</span></div>
              {TERMS.map((label, i) => (
                <div key={i} className="term"
                  onClick={(e) => {
                    if ((e.target as HTMLElement).classList.contains('view')) return
                    setTerms(terms.map((t, k) => (k === i ? !t : t)))
                  }}
                  style={css('min-height:46px;display:flex;align-items:center;gap:14px;padding:0 4px 0 18px;cursor:pointer')}><input type="hidden" name={`t${i}`} value={terms[i] ? '1' : ''} /><svg width="20" height="20" viewBox="0 0 24 24" style={css(`color:${check(terms[i])};flex:none`)}><use href="#w-check"></use></svg><span style={css('flex:1;font-size:15px;color:#3A4250')}>{label}</span><a className="lk view" href={link(LEGAL_PATH[TERM_LINKS[i]])} target="_blank" rel="noreferrer" style={css('font-size:13px;color:#A0A7B2;text-decoration:underline')}>보기</a></div>
              ))}
            </div>
          </fieldset>
          <button className="bt" type="submit" id="soBtn" style={css(`height:56px;border-radius:14px;background:${ok() ? '#D2601A' : '#C3C8CF'};color:#fff;display:flex;align-items:center;justify-content:center;font-size:17px;font-weight:700;margin-top:6px`)}>회원가입</button>
          <a className="lk" href={link('/login')} style={css('align-self:center;font-size:14px;color:#5B6472')}>이미 계정이 있어요 · <b style={css('color:#1B2433')}>로그인</b></a>
        </PostForm>
      </main>
    </Base>
  )
}
