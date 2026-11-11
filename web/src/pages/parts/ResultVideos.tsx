// 회차 결과 화면의 '결과 영상' 칸(285 QA): 백엔드가 만든 결과 영상(관절점·골격을 그리고 사람 얼굴은 가린 영상)을 바로 재생한다.
// GET /sessions/{id} 의 촬영 목록에서 분석이 끝난 촬영을 골라 GET /shots/{id} 의 video_url(서명 주소)을 <video> 에 넣는다.
// 결과 영상은 워커가 분석 뒤에 따로 만든다: PENDING 이면 만드는 중 안내(5초마다 다시 묻기), FAILED 면 만들지 못했다는 안내.
// 보고서 종이 밖(no-print)이라 인쇄·PDF 에는 나오지 않는다. 백엔드 회차에서만 쓴다(시연 데이터 회차는 결과 영상이 없다).
import { useEffect, useState } from 'react'
import { api, fileHref, type ShotDetailOut, type ShotOut } from '../../api/client'
import { css } from '../../app/css'

const SIDE: Record<string, string> = { LEFT: '왼쪽', RIGHT: '오른쪽' }
const VALIDITY: Record<string, [string, string, string]> = {
  VALID: ['유효', '#E8F3EC', '#2E7D4F'],
  PARTIAL: ['일부 유효', '#FCEEE3', '#A8481A'],
  INVALID: ['무효', '#F1ECE5', '#5B6472'],
}

/** 촬영 하나의 카메라 쪽: 통과들의 camera_side 중 많은 쪽 */
function sideOf(s: ShotOut): string | null {
  const n: Record<string, number> = {}
  for (const p of s.passes ?? []) n[p.camera_side] = (n[p.camera_side] ?? 0) + 1
  const best = Object.entries(n).sort((a, b) => b[1] - a[1])[0]
  return best ? best[0] : null
}

export function ResultVideos({ sessionId }: { sessionId: string }) {
  const [shots, setShots] = useState<ShotOut[] | null | undefined>(undefined)
  const [pick, setPick] = useState<string | null>(null)
  const [detail, setDetail] = useState<{ id: string; v: ShotDetailOut | null } | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let alive = true
    api.session(sessionId)
      .then((s) => {
        if (!alive) return
        const done = s.shots.filter((x) => x.status === 'DONE').sort((a, b) => a.seq_no - b.seq_no)
        setShots(done)
        setPick((p) => p ?? done[0]?.id ?? null)
      })
      .catch(() => alive && setShots(null))
    return () => {
      alive = false
    }
  }, [sessionId])

  useEffect(() => {
    if (!pick) return
    let alive = true
    let timer: number | undefined
    api.shot(pick)
      .then((v) => {
        if (!alive) return
        setDetail({ id: pick, v })
        if (v.video_status === 'PENDING') timer = window.setTimeout(() => setTick((n) => n + 1), 5000)
      })
      .catch(() => alive && setDetail({ id: pick, v: null }))
    return () => {
      alive = false
      if (timer) window.clearTimeout(timer)
    }
  }, [pick, tick])

  if (shots === undefined) return null
  if (shots === null || !shots.length) return null
  const cur = detail && detail.id === pick ? detail.v : undefined
  const status = cur?.video_status

  let body
  if (cur === undefined) body = <span style={css('font-size:14px;color:#8E949C')}>불러오는 중입니다</span>
  else if (cur === null) body = <span style={css('font-size:14px;color:#5B6472')}>결과 영상을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</span>
  else if (status === 'READY' && cur.video_url)
    body = (
      <video key={cur.id} src={fileHref(cur.video_url)} controls playsInline preload="metadata"
        onError={() => setTick((n) => n + 1)} // 서명 주소가 지났으면 새로 받는다
        style={css('width:100%;max-height:420px;border-radius:12px;background:#1B2433;display:block')} />
    )
  else if (status === 'FAILED') body = <span style={css('font-size:14px;color:#5B6472')}>이 촬영은 결과 영상을 만들지 못했습니다. 수치와 보고서는 그대로 볼 수 있습니다.</span>
  else body = <span style={css('font-size:14px;color:#5B6472')}>결과 영상을 만드는 중입니다. 잠시 뒤 자동으로 나타납니다.</span>

  return (
    <section className="no-print" style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:18px 20px;display:flex;flex-direction:column;gap:12px')}>
      <div style={css('display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap')}>
        <b style={css('font-size:16px')}>결과 영상</b>
        <span style={css('font-size:12.5px;color:#8E949C')}>AI가 찾은 관절점과 골격을 영상 위에 그렸습니다. 사람 얼굴은 가렸습니다</span>
      </div>
      <div style={css('display:flex;gap:8px;flex-wrap:wrap')}>
        {shots.map((s) => {
          const on = s.id === pick
          const side = sideOf(s)
          const val = s.validity ? VALIDITY[s.validity] : null
          return (
            <button key={s.id} type="button" onClick={() => setPick(s.id)}
              style={css(`height:34px;padding:0 12px;border-radius:9px;border:1px solid ${on ? '#D2601A' : '#E2DCD3'};background:${on ? '#FFF4EC' : '#fff'};color:${on ? '#A8481A' : '#3A4250'};font-size:13px;font-weight:${on ? 700 : 600};display:flex;align-items:center;gap:6px;cursor:pointer`)}>
              {s.seq_no}번{side ? ` · ${SIDE[side] ?? side}` : ''}
              {val ? <span style={css(`padding:1px 6px;border-radius:6px;background:${val[1]};color:${val[2]};font-size:11.5px;font-weight:700`)}>{val[0]}</span> : null}
            </button>
          )
        })}
      </div>
      {body}
    </section>
  )
}
