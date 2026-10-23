import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { useAuth } from '../../app/auth'
import { useToast } from '../../app/toast'
import { Button, Field, Input, TopBar } from '../../components/ui'

/**
 * 로그인(api-spec 4절). 디자인 v5 `login` 화면에 기관 코드 칸을 더했다(screenPlan 6절 #1).
 * 어느 칸이 틀렸는지는 표시하지 않는다(명세).
 */
export function LoginPage() {
  const { login } = useAuth()
  const toast = useToast()
  const nav = useNavigate()
  const loc = useLocation()
  const from = (loc.state as { from?: string } | null)?.from ?? '/'

  const [code, setCode] = useState('')
  const [id, setId] = useState('')
  const [pw, setPw] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const ready = code.trim().length >= 1 && id.trim().length >= 1 && pw.length >= 1

  async function submit(e?: FormEvent) {
    e?.preventDefault()
    if (!ready) {
      toast('기관 코드, 아이디, 비밀번호를 입력해 주세요')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const staff = await login({ institution_code: code.trim(), login_id: id.trim(), password: pw })
      toast(`${staff.institution.name} ${staff.name}님, 반가워요`)
      nav(from, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="screen" onSubmit={submit}>
      <TopBar onBack={() => nav('/login', { replace: true })} />
      <div className="scroll screen-body" style={{ gap: 20 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <h1>로그인</h1>
          <p style={{ fontSize: 15, color: 'var(--sub)' }}>동물병원·재활센터 계정으로 로그인해요.</p>
        </div>
        <Field label="기관 코드">
          <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="예) HANBIT" autoComplete="organization" autoCapitalize="characters" maxLength={20} />
        </Field>
        <Field label="아이디">
          <Input value={id} onChange={(e) => setId(e.target.value)} placeholder="관리자가 만들어 준 아이디" autoComplete="username" maxLength={50} />
        </Field>
        <Field label="비밀번호" hint={error ?? undefined} hintTone="bad">
          <Input type="password" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="비밀번호" autoComplete="current-password" invalid={!!error} />
        </Field>
        <p style={{ fontSize: 14, color: 'var(--sub)', lineHeight: 1.6 }}>
          계정은 기관 관리자가 만들어요. 아이디나 비밀번호를 잊었으면 관리자에게 문의해 주세요.
        </p>
      </div>
      <div className="sticky-footer" style={{ borderTop: 0 }}>
        <Button type="submit" dim={!ready} disabled={busy}>
          {busy ? '로그인 중…' : '로그인'}
        </Button>
      </div>
    </form>
  )
}
