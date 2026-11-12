import { request } from './client'
import type { DeviceCodeVerifyOut, LoginIn, SignupIn, StaffOut, TokenOut } from './types'

export function login(body: LoginIn): Promise<TokenOut> {
  return request<TokenOut>('/auth/login', { method: 'POST', body, auth: false })
}

export function me(): Promise<StaffOut> {
  return request<StaffOut>('/auth/me')
}

/** 담당자 이름·이메일·알림 설정 수정(보낸 필드만). 계약 만료(GUEST)는 403 CONTRACT_EXPIRED */
export function updateMe(body: { name?: string; email?: string; notif_on?: boolean }): Promise<StaffOut> {
  return request<StaffOut>('/auth/me', { method: 'PATCH', body })
}

/** 회원 탈퇴(192): 계정을 중지한다. 400 PASSWORD_MISMATCH, 기관의 마지막 활성 계정이면 409 LAST_ACCOUNT. 계약 만료(GUEST)도 된다 */
export function withdraw(password: string): Promise<void> {
  return request<void>('/auth/me', { method: 'DELETE', body: { password } })
}

/** 비밀번호 변경. 현재 비밀번호가 틀리면 400 PASSWORD_MISMATCH, 새 비밀번호 규칙(8자 이상, 현재와 다름)은 422. 받은 토큰은 그대로 쓴다 */
export function changePassword(current_password: string, new_password: string): Promise<StaffOut> {
  return request<StaffOut>('/auth/password', { method: 'PATCH', body: { current_password, new_password } })
}

/** 내 기관의 측정 기기(271): 가린 코드와 발급 시각. 쓸 수 있는 코드가 없으면 device 가 null */
export function myDevice(): Promise<{ device: { code_masked: string; issued_at: string } | null }> {
  return request<{ device: { code_masked: string; issued_at: string } | null }>('/auth/me/device')
}

/** 디바이스 코드 확인: 기관명. 404 DEVICE_CODE_INVALID (192 뒤에는 남은 계정 수·409 가 없다) */
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
