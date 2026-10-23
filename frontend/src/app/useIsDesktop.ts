import { useSyncExternalStore } from 'react'

/** 웹 v2 디자인을 쓰는 폭. 이보다 좁으면 앱 v5 화면이 나온다. */
export const DESKTOP_QUERY = '(min-width: 1024px)'

const mql = typeof window !== 'undefined' && 'matchMedia' in window ? window.matchMedia(DESKTOP_QUERY) : null

function subscribe(cb: () => void) {
  mql?.addEventListener('change', cb)
  return () => mql?.removeEventListener('change', cb)
}

export function useIsDesktop(): boolean {
  return useSyncExternalStore(subscribe, () => mql?.matches ?? false, () => false)
}
