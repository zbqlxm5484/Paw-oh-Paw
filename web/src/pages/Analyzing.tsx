// analyzing.html + main.py analyzing(): 분석 중 화면. 발자국이 하나씩 찍혔다 사라지고, 상태를 물어 끝나면 회차 결과로 간다
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { staticUrl, usePage, useTitle } from '../app/page'
import { redirect, setToast, type Go } from '../app/session'
import { STEPS } from '../config'
import { activeJobs, jobOf, jobProgress, dogOf } from '../store/db'
import { api_job } from '../store/actions_impl'
import { start_job } from '../views/analysis'
import { pyround } from '../views/pyfmt'

/** 서버의 RedirectResponse: 지금 주소를 바꿔 치운다 */
function useRedirect(g: Go | null) {
  const navigate = useNavigate()
  useEffect(() => {
    if (!g) return
    if (g.toast) setToast(g.toast)
    navigate(g.to, { replace: true })
  })
}

const JY = [0, 4, -5, 3, -3, 6, -2, 4]

export default function Analyzing() {
  const { job_id = '' } = useParams()
  const navigate = useNavigate()
  const { acct, me, toast } = usePage({ login: true, jobId: job_id })
  useTitle('분석 중 · Paw oh Paw')
  const isDemo = job_id === 'demo'
  const job = acct && !isDemo ? jobOf(acct, job_id) : undefined
  const p0 = job ? jobProgress(job) : 0
  const [step, setStep] = useState(STEPS[Math.min(4, Math.trunc(p0))])
  const [pct, setPct] = useState<number | string>(pyround((p0 / 5) * 100))
  const prints = useRef<(HTMLImageElement | null)[]>([])

  let go: Go | null = null
  if (acct && !isDemo) {
    if (!job) go = redirect('/results')
    else if (job.result_id) {
      job.notified = true
      go = redirect(`/results/${job.result_id}`)
    }
  }
  useRedirect(go)

  // 화면 바로가기: 진행 중인 분석이 없으면 새로 하나 띄운다
  useEffect(() => {
    if (!acct || !isDemo) return
    const j = activeJobs(acct)[0] || start_job(acct, acct.dogs.length ? acct.dogs[0].id : '', 16, '', [])
    navigate(`/analyzing/${j.id}`, { replace: true })
  }, [acct, isDemo, navigate])

  const live = !!job && !go
  useEffect(() => {
    if (!live) return
    // 발자국이 하나씩 찍혔다 사라지는 반복 (디자인의 prints)
    const tick = window.setInterval(() => {
      const ph = Math.floor(Date.now() / 420) % 11
      prints.current.forEach((p, i) => {
        if (!p) return
        const on = ph <= 8 ? i < ph : ph === 9
        const up = i % 2 === 0
        p.style.opacity = on ? '1' : '0'
        p.style.transform = 'rotate(' + (up ? 98 : 82) + 'deg) scale(' + (on ? 1 : 0.85) + ')'
      })
    }, 100)
    // 분석 상태 조회. 끝나면 회차 결과로 이동
    let t = 0
    const poll = () => {
      try {
        const d = api_job(job_id)
        if ('done' in d && d.done && d.url) {
          navigate(d.url)
          return
        }
        setStep('step' in d ? d.step : '')
        setPct('pct' in d ? d.pct : '')
        t = window.setTimeout(poll, 400)
      } catch {
        t = window.setTimeout(poll, 1500)
      }
    }
    poll()
    return () => {
      clearInterval(tick)
      clearTimeout(t)
    }
  }, [live, job_id, navigate])

  if (!acct || !job || go) return null
  const d = dogOf(acct, job.dog)
  const dog_name = d ? d.name : ''

  return (
    <Base acct={acct} me={me} toast={toast} jobId={job.id}>
      <main style={css('max-width:none;margin:0;padding:80px 80px 96px')}>
        <div style={css('display:flex;flex-direction:column;align-items:center;gap:12px;text-align:center')}>
          <b style={css('font-size:38px;letter-spacing:-1px')}>분석 중입니다</b>
          <span style={css('font-size:17px;color:#5B6472;font-variant-numeric:tabular-nums')}>{dog_name} · <span id="anaStep">{step}</span> · <span id="anaPct">{pct}</span>%</span>
          <div style={css('position:relative;width:100%;max-width:1400px;height:340px;margin:64px 0 24px')}>
            {JY.map((jy, i) => {
              const up = i % 2 === 0
              return <img key={i} ref={(el) => { prints.current[i] = el }} className="print" src={staticUrl('assets/paw-print.png')} alt="" style={css(`position:absolute;left:${1 + i * 12.6}%;top:${(up ? 60 : 180) + jy * 2}px;width:96px;height:96px;transform:rotate(${up ? 98 : 82}deg) scale(.85);opacity:0;transition:opacity .35s ease,transform .35s ease`)} />
            })}
          </div>
        </div>
      </main>
    </Base>
  )
}
