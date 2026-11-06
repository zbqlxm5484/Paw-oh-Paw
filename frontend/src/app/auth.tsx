import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import * as authApi from '../api/auth'
import { onAuthLost, tokenStore } from '../api/client'
import type { LoginIn, SignupIn, StaffOut } from '../api/types'

interface AuthState {
  /** 토큰이 있고 아직 만료되지 않았다 */
  loggedIn: boolean
  /** 새로고침 뒤 /auth/me 로 확인하는 중 */
  checking: boolean
  staff: StaffOut | null
  login: (body: LoginIn) => Promise<StaffOut>
  /** 기기 번호로 가입. 응답이 로그인과 같아 바로 로그인 상태가 된다 */
  signup: (body: SignupIn) => Promise<StaffOut>
  logout: () => void
  /** 내 정보 수정·비밀번호 변경 응답으로 화면의 담당자 정보를 바꾼다 */
  setStaff: (s: StaffOut) => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const [staff, setStaff] = useState<StaffOut | null>(null)
  const [loggedIn, setLoggedIn] = useState<boolean>(() => !!tokenStore.get() && !tokenStore.isExpired())
  const [checking, setChecking] = useState<boolean>(loggedIn)

  const logout = useCallback(() => {
    tokenStore.clear()
    setStaff(null)
    setLoggedIn(false)
    qc.clear()
  }, [qc])

  // 새로고침: 토큰이 남아 있으면 /auth/me 로 아직 쓸 수 있는지 확인한다(api-spec 4절)
  useEffect(() => {
    if (!loggedIn) return
    let alive = true
    authApi
      .me()
      .then((s) => {
        if (alive) setStaff(s)
      })
      .catch(() => {
        if (alive) logout()
      })
      .finally(() => {
        if (alive) setChecking(false)
      })
    return () => {
      alive = false
    }
    // 처음 한 번만
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 401 AUTH_REQUIRED·AUTH_EXPIRED, 403 ACCOUNT_DISABLED → 로그인 풀기
  useEffect(() => onAuthLost(() => logout()), [logout])

  const enter = (out: { access_token: string; expires_at: string; staff: StaffOut }) => {
    tokenStore.set(out.access_token, out.expires_at)
    setStaff(out.staff)
    setLoggedIn(true)
    setChecking(false)
    return out.staff
  }
  const login = useCallback(async (body: LoginIn) => enter(await authApi.login(body)), [])
  const signup = useCallback(async (body: SignupIn) => enter(await authApi.signup(body)), [])

  const value = useMemo<AuthState>(() => ({ loggedIn, checking, staff, login, signup, logout, setStaff }), [loggedIn, checking, staff, login, signup, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth 는 AuthProvider 안에서만 쓴다')
  return ctx
}
