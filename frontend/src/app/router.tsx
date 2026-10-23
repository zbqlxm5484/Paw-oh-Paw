import { Navigate, Outlet, createBrowserRouter, useLocation } from 'react-router-dom'

import { LoginPage } from '../features/auth/LoginPage'
import { DogDetailPage } from '../features/dogs/DogDetailPage'
import { HomePage } from '../features/dogs/HomePage'
import { PetFormPage } from '../features/dogs/PetFormPage'
import { MyPage, StoryPlaceholder } from '../features/placeholders'
import { ComparePage } from '../features/results/ComparePage'
import { ReportPage } from '../features/results/ReportPage'
import { ResultsPage } from '../features/results/ResultsPage'
import { SessionResultPage } from '../features/results/SessionResultPage'
import { SessionShotsPage, ShotDetailPage } from '../features/results/ShotsPage'
import { CaptureSelectPage } from '../features/sessions/CaptureSelectPage'
import { SessionPage } from '../features/sessions/SessionPage'
import { useAuth } from './auth'
import { AppFrame, TabLayout } from './Layout'

/** 로그인이 필요한 화면. 토큰 확인 중이면 빈 화면, 없으면 로그인으로. */
function RequireAuth() {
  const { loggedIn, checking } = useAuth()
  const loc = useLocation()
  if (checking) return <div className="screen" />
  if (!loggedIn) return <Navigate to="/login" replace state={{ from: loc.pathname }} />
  return <Outlet />
}

/** 이미 로그인했으면 로그인 화면 대신 홈으로 */
function GuestOnly() {
  const { loggedIn, checking } = useAuth()
  if (checking) return <div className="screen" />
  if (loggedIn) return <Navigate to="/" replace />
  return <Outlet />
}

export const router = createBrowserRouter([
  {
    element: <AppFrame />,
    children: [
      {
        element: <GuestOnly />,
        children: [{ path: '/login', element: <LoginPage /> }],
      },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <TabLayout />,
            children: [
              { path: '/', element: <HomePage /> },
              { path: '/story', element: <StoryPlaceholder /> },
              { path: '/results', element: <ResultsPage /> },
              { path: '/my', element: <MyPage /> },
            ],
          },
          { path: '/dogs/new', element: <PetFormPage mode="new" /> },
          { path: '/dogs/:dogId', element: <DogDetailPage /> },
          { path: '/dogs/:dogId/edit', element: <PetFormPage mode="edit" /> },
          { path: '/capture', element: <CaptureSelectPage /> },
          { path: '/sessions/:sessionId', element: <SessionPage /> },
          { path: '/sessions/:sessionId/result', element: <SessionResultPage /> },
          { path: '/sessions/:sessionId/report', element: <ReportPage /> },
          { path: '/sessions/:sessionId/shots', element: <SessionShotsPage /> },
          { path: '/shots/:shotId', element: <ShotDetailPage /> },
          { path: '/dogs/:dogId/compare', element: <ComparePage /> },
        ],
      },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
