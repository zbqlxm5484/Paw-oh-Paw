import { request } from './client'
import type { LoginIn, StaffOut, TokenOut } from './types'

export function login(body: LoginIn): Promise<TokenOut> {
  return request<TokenOut>('/auth/login', { method: 'POST', body, auth: false })
}

export function me(): Promise<StaffOut> {
  return request<StaffOut>('/auth/me')
}
