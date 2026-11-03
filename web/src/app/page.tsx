// 화면 공통 훅과 폼. 시제품의 page()(로그인 확인·알림)와 <form method="post"> 를 React 로 옮긴 것.
import { useEffect, useState, type FormEvent, type FormHTMLAttributes, type ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useDb } from '../store/db'
import { dispatch } from '../store/actions'
import type { Account, Staff } from '../store/types'
import { ContractExpired, current, currentStaff, finished_notices, setToast, takeToast, type Go } from './session'
import { BASE } from '../config'

export interface PageCtx {
  acct?: Account
  me?: Staff
  toast: string
  query: URLSearchParams
  go: (g: Go) => void
}

/**
 * 화면마다 처음에 부른다. login=true 면 로그인 안 했을 때 로그인 화면으로 보낸다(시제품의 need_login).
 * jobId: 분석 중 화면처럼 그 작업의 완료 알림을 직접 다루는 화면이면 그 id(다른 작업 알림만 띄움).
 */
export function usePage(opts: { login?: boolean; jobId?: string } = {}): PageCtx {
  useDb()
  const navigate = useNavigate()
  const [query] = useSearchParams()
  let acct: Account | undefined
  let expired = false
  try {
    acct = current()
  } catch (e) {
    if (e instanceof ContractExpired) expired = true
    else throw e
  }
  const me = currentStaff()
  const [toast] = useState(() => {
    const t = takeToast()
    const n = acct ? finished_notices(acct, opts.jobId || '') : []
    return t || n[0] || ''
  })
  const go = (g: Go) => {
    if (g.toast) setToast(g.toast)
    navigate(g.to)
  }
  useEffect(() => {
    if (expired) navigate('/expired', { replace: true })
    else if (opts.login && !acct) {
      setToast('로그인해 주세요')
      navigate('/login', { replace: true })
    }
  })
  return { acct, me, toast, query, go }
}

/** <form method="post" action="/dogs/d1/notes"> 를 그대로 쓰면, 시제품 주소 그대로 store/actions.ts 의 처리 함수로 보낸다 */
export function PostForm({ action, children, onBefore, ...rest }: { action: string; children?: ReactNode; onBefore?: (fd: FormData) => boolean | void } & Omit<FormHTMLAttributes<HTMLFormElement>, 'action' | 'method'>) {
  const navigate = useNavigate()
  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    // 누른 제출 버튼의 name=value 도 넣는다(시제품 폼처럼. 예: 관리 화면 "회수" 버튼 revoke=1)
    const fd = new FormData(e.currentTarget, (e.nativeEvent as SubmitEvent).submitter)
    if (onBefore && onBefore(fd) === false) return
    const author = e.currentTarget.querySelector<HTMLInputElement>('input.author-inp')
    if (author && author.value.trim()) {
      try {
        localStorage.setItem('pp_author', author.value.trim())
      } catch {
        /* 무시 */
      }
    }
    const g = await dispatch(action, fd)
    if (g.toast) setToast(g.toast)
    navigate(g.to)
  }
  return (
    <form method="post" action={action} onSubmit={onSubmit} {...rest}>
      {children}
    </form>
  )
}

/** <form method="get" action="/home"> : 입력값으로 주소를 만들어 이동한다(빈 값은 뺀다) */
export function GetForm({ action, children, ...rest }: { action: string; children?: ReactNode } & Omit<FormHTMLAttributes<HTMLFormElement>, 'action' | 'method'>) {
  const navigate = useNavigate()
  return (
    <form method="get" action={action} {...rest}
      onSubmit={(e) => {
        e.preventDefault()
        submitGet(e.currentTarget, action, navigate)
      }}>
      {children}
    </form>
  )
}

export function submitGet(form: HTMLFormElement, action: string, navigate: (to: string) => void): void {
  const p = new URLSearchParams()
  new FormData(form).forEach((v, k) => {
    if (typeof v === 'string' && v !== '') p.append(k, v)
  })
  const s = p.toString()
  navigate(s ? `${action}?${s}` : action)
}

/** 시제품의 url_for('static', path=...) */
export const staticUrl = (path: string): string => `${BASE}/static/${path}`

/** 문서 제목({% block title %}) */
export function useTitle(t: string): void {
  useEffect(() => {
    document.title = t
  }, [t])
}
