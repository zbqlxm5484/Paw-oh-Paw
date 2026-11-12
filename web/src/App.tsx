// 주소는 웹 시제품(prototype/)과 같다. 화면마다 템플릿 하나를 옮긴 컴포넌트가 있다.
import { useEffect } from 'react'
import { BASE } from './config'
import { BrowserRouter, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import { JUMPS } from './app/jumps'
import { setLogin } from './app/session'
import { resetDemo } from './store/demo'
import { db } from './store/db'
import { DEMO_STAFF } from './store/demo'
import Landing from './pages/Landing'
import About from './pages/About'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Forgot from './pages/Forgot'
import Reset from './pages/Reset'
import Expired from './pages/Expired'
import NotFound from './pages/NotFound'
import Admin from './pages/Admin'
import Home from './pages/Home'
import DogPage from './pages/Dog'
import Upload from './pages/Upload'
import Analyzing from './pages/Analyzing'
import Results from './pages/Results'
import Report from './pages/Report'
import ReportPrint from './pages/ReportPrint'
import Gait3d from './pages/Gait3d'
import Legal from './pages/Legal'
import Compare from './pages/Compare'
import My from './pages/My'
import AccountPage from './pages/Account'

/** 화면 바로가기(디자인 검토용). 로그인이 필요한 화면은 데모 기관으로 들어간다 */
function Jump() {
  const { idx } = useParams()
  const navigate = useNavigate()
  useEffect(() => {
    const [, url, need] = JUMPS[Number(idx)] || ['', '/', false]
    if (!need) setLogin(null)
    else {
      if (!db.accounts.demo?.results.some((r) => r.id === 'r1')) resetDemo()
      setLogin(DEMO_STAFF)
    }
    navigate(url, { replace: true })
  }, [idx, navigate])
  return null
}

function Pages() {
  const loc = useLocation()
  // 주소가 바뀌면 화면을 새로 만든다(시제품은 화면마다 서버가 새로 그린다)
  return (
    <Routes location={loc} key={loc.key}>
      <Route path="/" element={<Landing />} />
      <Route path="/about" element={<About />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/forgot" element={<Forgot />} />
      <Route path="/reset-password" element={<Reset />} />
      <Route path="/expired" element={<Expired />} />
      <Route path="/admin" element={<Admin />} />
      <Route path="/terms" element={<Legal kind="terms" />} />
      <Route path="/privacy" element={<Legal kind="privacy" />} />
      <Route path="/support" element={<Legal kind="support" />} />
      <Route path="/jump/:idx" element={<Jump />} />
      <Route path="/home" element={<Home />} />
      <Route path="/dogs/:dog_id" element={<DogPage />} />
      <Route path="/upload" element={<Upload />} />
      <Route path="/analyzing/:job_id" element={<Analyzing />} />
      <Route path="/results" element={<Results />} />
      <Route path="/results/:rid" element={<Report />} />
      <Route path="/results/:rid/report" element={<Report />} />
      <Route path="/results/:rid/3d" element={<Gait3d />} />
      <Route path="/print/reports/:rid" element={<ReportPrint />} />
      <Route path="/compare/:dog_id" element={<Compare />} />
      <Route path="/my" element={<My />} />
      <Route path="/account" element={<AccountPage />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter basename={BASE || undefined}>
      <Pages />
    </BrowserRouter>
  )
}
