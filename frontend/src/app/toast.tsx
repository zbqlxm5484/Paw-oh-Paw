import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

type ToastFn = (message: string) => void
const ToastContext = createContext<ToastFn>(() => {})

/** 디자인의 토스트: 화면 아래 2.2초 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [msg, setMsg] = useState('')
  const timer = useRef<number | undefined>(undefined)

  const toast = useCallback<ToastFn>((m) => {
    window.clearTimeout(timer.current)
    setMsg(m)
    timer.current = window.setTimeout(() => setMsg(''), 2200)
  }, [])

  useEffect(() => () => window.clearTimeout(timer.current), [])

  const value = useMemo(() => toast, [toast])
  return (
    <ToastContext.Provider value={value}>
      {children}
      {msg && (
        <div className="toast" role="status" aria-live="polite">
          <span>{msg}</span>
        </div>
      )}
    </ToastContext.Provider>
  )
}

export function useToast(): ToastFn {
  return useContext(ToastContext)
}
