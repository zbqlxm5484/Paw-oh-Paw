// 앱 보고서 · 수의사용 '무릎을 가장 굽힌 순간·가장 편 순간'(285, 웹 pages/parts/AngleFrames.tsx 와 같은 구성):
// 이 회차 결과 영상(관절점·골격을 그리고 얼굴을 가린 영상)에서 대표 보행의 무릎 각도가 가장 작은·큰 프레임을 잘라 그림 두 장으로 싣는다(쪽마다 한 촬영).
// 영상은 보이지 않게 불러 그 시각으로 옮긴 뒤 canvas 로 찍어 jpeg 그림(<img>)으로 넣는다(화면 그대로 PDF 에도 나온다).
// 결과 영상이 없거나(만드는 중·실패), 각도가 없거나, 영상을 못 찍으면 칸을 통째로 뺀다. 측정한 프레임만 싣는다.
import { useEffect, useState } from 'react'
import { fileUrl } from '../../api/labels'
import { getAngles, getShot } from '../../api/results'
import { getSession } from '../../api/sessions'
import { loadAngleFrames, seekSec, type FrameShot } from './angleFrames'
import { GAIT_KO } from './gaitClip'

const H2: React.CSSProperties = { margin: 0, fontSize: '15px', fontWeight: 800, letterSpacing: '-0.3px' }
const SIDE: Record<string, string> = { LEFT: '왼쪽', RIGHT: '오른쪽' }
/** 영상 하나를 찍는 데 기다리는 시간. 넘으면 그 촬영은 뺀다 */
const SHOT_TIMEOUT_MS = 20000

/** 영상을 frames 의 프레임들로 옮겨 가며 찍는다(가로 640 이하 jpeg). 하나라도 못 찍으면 reject */
function captureFrames(url: string, fps: number, frames: number[]): Promise<string[]> {
  return new Promise((resolve, reject) => {
    const v = document.createElement('video')
    const out: string[] = []
    let done = false
    const finish = (err: unknown, val?: string[]) => {
      if (done) return
      done = true
      window.clearTimeout(timer)
      v.removeAttribute('src')
      v.load()
      if (err) reject(err)
      else resolve(val!)
    }
    const timer = window.setTimeout(() => finish(new Error('timeout')), SHOT_TIMEOUT_MS)
    const next = () => {
      if (out.length === frames.length) return finish(null, out)
      v.currentTime = seekSec(frames[out.length], fps, v.duration)
    }
    v.crossOrigin = 'anonymous'
    v.muted = true
    v.playsInline = true
    v.preload = 'auto'
    v.onloadedmetadata = next
    v.onseeked = () => {
      try {
        if (!v.videoWidth || !v.videoHeight) throw new Error('no frame')
        const w = Math.min(640, v.videoWidth)
        const c = document.createElement('canvas')
        c.width = w
        c.height = Math.round((w * v.videoHeight) / v.videoWidth)
        c.getContext('2d')!.drawImage(v, 0, 0, c.width, c.height)
        out.push(c.toDataURL('image/jpeg', 0.85)) // 교차 출처로 막히면 여기서 SecurityError
        next()
      } catch (e) {
        finish(e)
      }
    }
    v.onerror = () => finish(new Error('video error'))
    v.src = url
  })
}

type Row = FrameShot & { imgs: [string, string] }

export function AppAngleFrames({ sessionId, gait }: { sessionId: string; gait: string | null }) {
  const [rows, setRows] = useState<{ id: string; v: Row[] | null } | null>(null)
  useEffect(() => {
    let alive = true
    ;(async () => {
      const shots = await loadAngleFrames({ session: getSession, angles: getAngles, shot: getShot }, sessionId, gait)
      const got: Row[] = []
      for (const s of shots) {
        const url = fileUrl(s.videoUrl)
        if (!url) continue
        try {
          const imgs = await captureFrames(url, s.fps, [s.ex.flex.frame, s.ex.ext.frame])
          got.push({ ...s, imgs: [imgs[0], imgs[1]] })
        } catch {
          /* 이 촬영은 뺀다 */
        }
      }
      return got.length ? got : null
    })()
      .catch(() => null)
      .then((v) => alive && setRows({ id: sessionId, v }))
    return () => {
      alive = false
    }
  }, [sessionId, gait])
  const cur = rows && rows.id === sessionId ? rows.v : null
  if (!cur) return null
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <h3 style={H2}>무릎을 가장 굽힌 순간 · 가장 편 순간 <span style={{ fontSize: '12px', fontWeight: 600, color: '#5B6472' }}>{GAIT_KO[cur[0].gait] ?? cur[0].gait}</span></h3>
      <span style={{ fontSize: '12px', color: '#5B6472', lineHeight: 1.5 }}>결과 영상(관절점·골격 표시, 사람 얼굴 가림)에서 유효 통과 중 무릎 각도가 가장 작은 프레임과 가장 큰 프레임을 그대로 옮겼습니다.</span>
      {cur.map((x) => (
        <div key={x.shotId} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <b style={{ fontSize: '13px' }}>{SIDE[x.side] ?? x.side} 뒷다리 무릎{x.seqNo != null ? <span style={{ fontWeight: 600, color: '#5B6472', marginLeft: 6 }}>{x.seqNo}번 촬영</span> : null}</b>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            {([['가장 굽힌 순간', x.ex.flex, x.imgs[0]], ['가장 편 순간', x.ex.ext, x.imgs[1]]] as const).map(([label, f, img]) => (
              <figure key={label} style={{ margin: 0, display: 'flex', flexDirection: 'column', gap: '4px', minWidth: 0 }}>
                <img src={img} alt={`${SIDE[x.side] ?? ''} 뒷다리 무릎 ${label}`} style={{ width: '100%', display: 'block', borderRadius: 8, background: '#1B2433' }} />
                <figcaption style={{ display: 'flex', flexDirection: 'column', gap: '1px', fontSize: '12px', fontVariantNumeric: 'tabular-nums' }}>
                  <span><b>{label}</b> <b style={{ fontSize: '14px' }}>{f.deg.toFixed(1)}°</b></span>
                  <span style={{ color: '#5B6472', fontSize: '12px' }}>{f.sec.toFixed(2)}초 · {f.frame}프레임</span>
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      ))}
    </section>
  )
}
