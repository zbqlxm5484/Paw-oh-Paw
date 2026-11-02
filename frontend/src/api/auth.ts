import { request } from './client'
import type { DeviceCodeVerifyOut, LoginIn, SignupIn, StaffOut, TokenOut } from './types'

export function login(body: LoginIn): Promise<TokenOut> {
  return request<TokenOut>('/auth/login', { method: 'POST', body, auth: false })
}

export function me(): Promise<StaffOut> {
  return request<StaffOut>('/auth/me')
}

/** 디바이스 코드 확인: 기관명·남은 계정 수. 404 DEVICE_CODE_INVALID, 409 DEVICE_CODE_FULL */
export function verifyDeviceCode(code: string): Promise<DeviceCodeVerifyOut> {
  return request<DeviceCodeVerifyOut>('/auth/device-codes/verify', { method: 'POST', body: { code }, auth: false })
}

/** 회원가입(CLIENT). 응답은 로그인과 같다 */
export function signup(body: SignupIn): Promise<TokenOut> {
  return request<TokenOut>('/auth/signup', { method: 'POST', body, auth: false })
}

/** 재설정 링크 메일. 계정이 있든 없든 204, 메일 서버가 없으면 503 MAIL_UNAVAILABLE */
export function requestPasswordReset(login_id: string): Promise<void> {
  return request<void>('/auth/password-reset/request', { method: 'POST', body: { login_id }, auth: false })
}

/** 링크의 토큰으로 비밀번호 바꾸기. 400 RESET_TOKEN_INVALID */
export function confirmPasswordReset(token: string, new_password: string): Promise<void> {
  return request<void>('/auth/password-reset/confirm', { method: 'POST', body: { token, new_password }, auth: false })
}
