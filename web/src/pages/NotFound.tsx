// 없는 주소. 라우트에 없는 주소를 열면 빈 화면이 아니라 안내와 돌아갈 길을 보여 준다
import { Base } from '../app/Base'
import { css } from '../app/css'
import { useTitle } from '../app/page'
import { link } from '../config'
import AuthBar, { usePublicPage } from './parts/AuthBar'

export default function NotFound() {
  useTitle('없는 페이지 · Paw oh Paw')
  const { me, toast } = usePublicPage()
  const home = me ? '/home' : '/'

  return (
    <Base me={me} toast={toast} topbar={<AuthBar />}>
      <main style={css('max-width:600px;margin:8vh auto 96px;padding:0 24px')}>
        <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:24px;padding:52px 48px;display:flex;flex-direction:column;gap:20px')}>
          <span style={css('align-self:flex-start;height:30px;padding:0 12px;border-radius:999px;background:#F2EEE8;color:#5B6472;font-size:14px;font-weight:700;display:flex;align-items:center')}>404</span>
          <h1 style={css('margin:0;font-size:30px;font-weight:800;letter-spacing:-0.8px')}>없는 페이지입니다</h1>
          <p style={css('margin:0;font-size:17px;color:#5B6472;line-height:1.6')}>주소가 바뀌었거나 잘못 적혔습니다. 아래 버튼으로 돌아가 주세요.</p>
          <a className="lk hv-orange" href={link(home)} style={css('align-self:flex-start;height:52px;padding:0 22px;border-radius:14px;background:#D2601A;color:#fff;display:flex;align-items:center;font-size:16px;font-weight:700')}>{me ? '홈으로' : '첫 화면으로'}</a>
        </div>
      </main>
    </Base>
  )
}
