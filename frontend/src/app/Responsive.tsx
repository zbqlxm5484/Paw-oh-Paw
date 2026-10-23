import type { ReactNode } from 'react'

import { useIsDesktop } from './useIsDesktop'

/** 같은 주소에서 폭에 따라 다른 화면을 그린다: 넓으면 웹 v2, 좁으면 앱 v5. */
export function Responsive({ mobile, web }: { mobile: ReactNode; web: ReactNode }) {
  const desktop = useIsDesktop()
  return <>{desktop ? web : mobile}</>
}
