// _authbar.html: 로그인 전 화면(로그인·가입·비밀번호·만료·관리)의 상단 바. 같은 화면들이 쓰는 usePublicPage 도 여기 둔다.
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { css } from '../../app/css'
import { staticUrl } from '../../app/page'
import { currentStaff, setToast, takeToast, type Go } from '../../app/session'
import { useDb } from '../../store/db'
import { link } from '../../config'

export default function AuthBar() {
  return (
    <header style={css('padding:25px 25px 0;display:flex;align-items:center;justify-content:space-between')}>
      <a className="lk" href={link('/')} style={css('display:flex;align-items:center;min-height:44px;gap:8px;font-size:18px;font-weight:800;letter-spacing:-0.4px')}><img src={staticUrl('assets/logo.png')} alt="" style={css('width:30px;height:30px;object-fit:contain')} />Paw oh Paw</a>
    </header>
  )
}

export { AuthBar }

/**
 * current() 를 부르지 않는 화면용(main.py 의 page(request, ...) 에 acct 없이 넘기는 곳).
 * usePage 는 계약 만료면 /expired 로 보내는데, 시제품의 로그인·가입·만료·관리 화면은 그러지 않는다.
 * 알림은 쿠키(여기선 sessionStorage) 것만, 분석 완료 알림은 없다. 이동은 303 처럼 기록을 바꿔 낀다.
 */
export function usePublicPage() {
  useDb()
  const navigate = useNavigate()
  const [query] = useSearchParams()
  const [toast] = useState(takeToast)
  const me = currentStaff()
  const go = (g: Go) => {
    if (g.toast) setToast(g.toast)
    navigate(g.to, { replace: true })
  }
  return { toast, query, me, go }
}
