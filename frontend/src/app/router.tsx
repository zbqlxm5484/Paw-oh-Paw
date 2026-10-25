import { Navigate, Outlet, createBrowserRouter, useLocation, useNavigate } from 'react-router-dom'

import { LoginPage } from '../features/auth/LoginPage'
import { DogDetailPage } from '../features/dogs/DogDetailPage'
import { HomePage } from '../features/dogs/HomePage'
import { PetFormPage } from '../features/dogs/PetFormPage'
import { IntroPage } from '../features/intro/IntroPage'
import { WelcomePage } from '../features/intro/WelcomePage'
import { MyPage } from '../features/placeholders'
import { ComparePage } from '../features/results/ComparePage'
import { ReportPage } from '../features/results/ReportPage'
import { ResultsPage } from '../features/results/ResultsPage'
import { SessionResultPage } from '../features/results/SessionResultPage'
import { SessionShotsPage, ShotDetailPage } from '../features/results/ShotsPage'
import { CaptureSelectPage } from '../features/sessions/CaptureSelectPage'
import { SessionPage } from '../features/sessions/SessionPage'
import { IntroStage } from '../features/web/IntroStage'
import { WebCompare } from '../features/web/WebCompare'
import { WebDetail } from '../features/web/WebDetail'
import { WebHome } from '../features/web/WebHome'
import { WebLanding } from '../features/web/WebLanding'
import { WebAccount, WebMy } from '../features/web/WebMy'
import { WebResults } from '../features/web/WebResults'
import { WebSession, WebUpload } from '../features/web/WebUpload'
import { useAuth } from './auth'
import { AppFrame, TabLayout } from './Layout'
import { Responsive } from './Responsive'
import { AppProto } from '../design/app/AppProto'
import { WebProto } from '../design/web/WebProto'

/** 로그인이 필요한 화면. 토큰 확인 중이면 빈 화면, 없으면 랜딩(첫 진입) 또는 로그인으로. */
function RequireAuth() {
  const { loggedIn, checking } = useAuth()
  const loc = useLocation()
  if (checking) return <div className="screen" />
  if (!loggedIn) return loc.pathname === '/' ? <Navigate to="/welcome" replace /> : <Navigate to="/login" replace state={{ from: loc.pathname }} />
  return <Outlet />
}

/** 이미 로그인했으면 로그인 화면 대신 홈으로 */
function GuestOnly() {
  const { loggedIn, checking } = useAuth()
  if (checking) return <div className="screen" />
  if (loggedIn) return <Navigate to="/" replace />
  return <Outlet />
}

/** 폰 화면 컴포넌트를 웹에서 가운데 카드로 */
function Card({ children, wide }: { children: React.ReactNode; wide?: boolean }) {
  return (
    <main className="web-main narrow" style={wide ? { maxWidth: 960 } : undefined}>
      <div className="as-card-host" style={{ display: 'flex' }}>
        {children}
      </div>
    </main>
  )
}

/** 웹에서 서비스 소개는 스크롤 스테이지만 보여 준다 */
function WebIntroPage() {
  const { loggedIn } = useAuth()
  const nav = useNavigate()
  return <IntroStage ctaLabel={loggedIn ? '영상 올리기' : '기관으로 시작하기'} onCta={() => nav(loggedIn ? '/capture' : '/login')} />
}

/** 웹에서는 반려견 상세가 홈의 선택 패널이다 */
function DogRedirect() {
  const loc = useLocation()
  const id = loc.pathname.split('/')[2]
  return <Navigate to={`/?dog=${id}`} replace />
}

export const router = createBrowserRouter([
  // 디자인 원본 그대로 옮긴 화면(이식 중 비교용)
  { path: '/design-web', element: <WebProto /> },
  { path: '/design-app', element: <div style={{ display: 'flex', gap: 56, padding: '48px 56px', alignItems: 'flex-start', background: '#E9E6E1', minHeight: '100vh' }}><AppProto /></div> },
  {
    element: <AppFrame />,
    children: [
      {
        element: <GuestOnly />,
        children: [
          { path: '/welcome', element: <Responsive mobile={<WelcomePage />} web={<WebLanding />} /> },
          { path: '/login', element: <Responsive mobile={<LoginPage />} web={<Card><LoginPage /></Card>} /> },
        ],
      },
      // 로그인 여부와 상관없이 볼 수 있는 화면
      {
        children: [{ path: '/intro', element: <Responsive mobile={<IntroPage />} web={<WebIntroPage />} /> }],
      },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <TabLayout />,
            children: [
              { path: '/', element: <Responsive mobile={<HomePage />} web={<WebHome />} /> },
              { path: '/story', element: <Responsive mobile={<IntroPage />} web={<WebIntroPage />} /> },
              { path: '/results', element: <Responsive mobile={<ResultsPage />} web={<WebResults />} /> },
              { path: '/my', element: <Responsive mobile={<MyPage />} web={<WebMy />} /> },
            ],
          },
          { path: '/account', element: <Responsive mobile={<Navigate to="/my" replace />} web={<WebAccount />} /> },
          { path: '/dogs/new', element: <Responsive mobile={<PetFormPage mode="new" />} web={<Card><PetFormPage mode="new" /></Card>} /> },
          { path: '/dogs/:dogId', element: <Responsive mobile={<DogDetailPage />} web={<DogRedirect />} /> },
          { path: '/dogs/:dogId/edit', element: <Responsive mobile={<PetFormPage mode="edit" />} web={<Card><PetFormPage mode="edit" /></Card>} /> },
          { path: '/capture', element: <Responsive mobile={<CaptureSelectPage />} web={<WebUpload />} /> },
          { path: '/sessions/:sessionId', element: <Responsive mobile={<SessionPage />} web={<WebSession />} /> },
          { path: '/sessions/:sessionId/result', element: <Responsive mobile={<SessionResultPage />} web={<WebDetail />} /> },
          { path: '/sessions/:sessionId/report', element: <Responsive mobile={<ReportPage />} web={<Card wide><ReportPage /></Card>} /> },
          { path: '/sessions/:sessionId/shots', element: <Responsive mobile={<SessionShotsPage />} web={<Card wide><SessionShotsPage /></Card>} /> },
          { path: '/shots/:shotId', element: <Responsive mobile={<ShotDetailPage />} web={<Card wide><ShotDetailPage /></Card>} /> },
          { path: '/dogs/:dogId/compare', element: <Responsive mobile={<ComparePage />} web={<WebCompare />} /> },
        ],
      },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
