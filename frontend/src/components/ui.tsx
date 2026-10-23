/** 디자인 v5 에서 반복되는 작은 조각들. 스타일은 ui.css. */
import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from 'react'
import { useNavigate } from 'react-router-dom'

import type { Tone } from '../api/labels'
import { Icon } from './Icon'
import './ui.css'

/* ---------- 상단 바 ---------- */
export function TopBar({ title, right, onBack }: { title?: ReactNode; right?: ReactNode; onBack?: () => void }) {
  const nav = useNavigate()
  const back = onBack ?? (() => (window.history.length > 1 ? nav(-1) : nav('/')))
  return (
    <div className="topbar">
      <div className="topbar-left">
        <button type="button" className="icon-btn" onClick={back} aria-label="뒤로">
          <Icon name="back" />
        </button>
        {title && <b className="topbar-title">{title}</b>}
      </div>
      {right && <div className="topbar-right">{right}</div>}
    </div>
  )
}

/* ---------- 버튼 ---------- */
type BtnVariant = 'primary' | 'secondary' | 'dark' | 'danger' | 'ghost'
interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: BtnVariant
  /** 비활성처럼 보이지만 누를 수는 있다(디자인: 누르면 토스트로 안내) */
  dim?: boolean
  size?: 'lg' | 'md' | 'sm'
}
export function Button({ variant = 'primary', dim, size = 'lg', className = '', children, ...rest }: BtnProps) {
  return (
    <button type="button" className={`btn btn-${variant} btn-${size}${dim ? ' dim' : ''} ${className}`} {...rest}>
      {children}
    </button>
  )
}

/* ---------- 입력 ---------- */
interface FieldProps {
  label: ReactNode
  hint?: ReactNode
  hintTone?: 'sub' | 'bad'
  right?: ReactNode
  children: ReactNode
}
export function Field({ label, hint, hintTone = 'sub', right, children }: FieldProps) {
  return (
    <label className="field">
      <span className="field-head">
        <span className="field-label">{label}</span>
        {right && <span className="field-right">{right}</span>}
      </span>
      {children}
      {hint && <span className={`field-hint ${hintTone}`}>{hint}</span>}
    </label>
  )
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }>(function Input(
  { className = '', invalid, ...rest },
  ref,
) {
  return <input ref={ref} className={`input${invalid ? ' invalid' : ''} ${className}`} {...rest} />
})

export function Textarea({ className = '', ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`input textarea ${className}`} {...rest} />
}

/* ---------- 선택 칩(성별·체급·관심 다리) ---------- */
export function PickGrid({ cols, children }: { cols: number; children: ReactNode }) {
  return (
    <div className="pick-grid" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
      {children}
    </div>
  )
}
export function Pick({ on, children, onClick }: { on: boolean; children: ReactNode; onClick: () => void }) {
  return (
    <button type="button" className={`pick${on ? ' on' : ''}`} onClick={onClick} aria-pressed={on}>
      {children}
    </button>
  )
}

/* ---------- 카드·배지·아바타 ---------- */
export function Card({ className = '', children, onClick, style }: { className?: string; children: ReactNode; onClick?: () => void; style?: React.CSSProperties }) {
  if (onClick)
    return (
      <button type="button" className={`card card-btn ${className}`} onClick={onClick} style={style}>
        {children}
      </button>
    )
  return (
    <div className={`card ${className}`} style={style}>
      {children}
    </div>
  )
}

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function Avatar({ name, size = 48 }: { name: string; size?: number }) {
  return (
    <div className="avatar" style={{ width: size, height: size, fontSize: Math.round(size * 0.36) }} aria-hidden="true">
      {name.trim().charAt(0) || '?'}
    </div>
  )
}

export function Tag({ children }: { children: ReactNode }) {
  return <span className="tag">{children}</span>
}

/* ---------- 빈 상태 ---------- */
export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>
}

/* ---------- 바텀 시트 ---------- */
export function Sheet({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  if (!open) return null
  return (
    <>
      <div className="sheet-dim" onClick={onClose} />
      <div className="sheet" role="dialog" aria-modal="true">
        {children}
      </div>
    </>
  )
}
