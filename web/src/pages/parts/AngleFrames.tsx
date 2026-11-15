// 수의사용 보고서 '무릎을 가장 굽힌 순간·가장 편 순간'(285): 이 회차 결과 영상(관절점·골격을 그리고 얼굴을 가린 영상)에서
// 대표 보행의 무릎 각도가 가장 작은 프레임과 가장 큰 프레임을 잘라 그림 두 장으로 싣는다(쪽마다 한 촬영).
// 영상은 보이지 않게 불러 그 시각으로 옮긴 뒤 canvas 로 찍고, 그림(jpeg dataURL)을 <img> 로 넣어 인쇄·PDF 에도 그대로 나온다.
// 결과 영상이 없거나(만드는 중·실패), 각도가 없거나, 영상을 못 찍으면(교차 출처 등) 칸을 통째로 뺀다. 측정한 프레임만 싣는다.
import { useEffect, useState } from 'react'
import { api, fileHref } from '../../api/client'
import { css } from '../../app/css'
import { loadAngleFrames, seekSec, type FrameShot } from '../../views/angleFrames'
import { GAIT_KO } from '../../views/gaitClip'

const H2 = 'margin:0;font-size:18px;font-weight:800;letter-spacing:-0.3px'
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

/** 쪽마다 한 줄: 가장 굽힌 순간 · 가장 편 순간. undefined = 읽는 중, null = 뺌 */
export function AngleFrames({ sessionId, gait, onSettled }: { sessionId: string; gait: string | null; onSettled?: () => void }) {
  const [rows, setRows] = useState<{ id: string; v: Row[] | null } | null>(null)
  useEffect(() => {
    let alive = true
    ;(async () => {
      const shots = await loadAngleFrames({ session: (id) => api.session(id), angles: (id) => api.angles(id), shot: (id) => api.shot(id) }, sessionId, gait)
      const got: Row[] = []
      for (const s of shots) {
        try {
          const imgs = await captureFrames(fileHref(s.videoUrl), s.fps, [s.ex.flex.frame, s.ex.ext.frame])
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
  const cur = rows && rows.id === sessionId ? rows.v : undefined
  useEffect(() => {
    if (cur !== undefined) onSettled?.()
  }, [cur, onSettled])
  if (!cur) return null
  return (
    <section className="rep-sec" style={css('display:flex;flex-direction:column;gap:10px')}>
      <h2 style={css(H2)}>무릎을 가장 굽힌 순간, 가장 편 순간 <span style={css('font-size:13px;font-weight:600;color:#5B6472')}>{GAIT_KO[cur[0].gait] ?? cur[0].gait}</span></h2>
      <span style={css('font-size:13px;color:#5B6472;line-height:1.5')}>결과 영상(관절점·골격 표시, 사람 얼굴 가림)에서 유효 통과 중 무릎 각도가 가장 작은 프레임과 가장 큰 프레임을 그대로 옮겼습니다.</span>
      {cur.map((x) => (
        <div key={x.shotId} style={css('display:flex;flex-direction:column;gap:6px')}>
          <b style={css('font-size:14px')}>{SIDE[x.side] ?? x.side} 뒷다리 무릎{x.seqNo != null ? <span style={css('font-weight:600;color:#5B6472;margin-left:6px')}>{x.seqNo}번 촬영</span> : null}</b>
          <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:12px')}>
            {([['가장 굽힌 순간', x.ex.flex, x.imgs[0]], ['가장 편 순간', x.ex.ext, x.imgs[1]]] as const).map(([label, f, img]) => (
              <figure key={label} style={css('margin:0;display:flex;flex-direction:column;gap:6px;min-width:0')}>
                <img src={img} alt={`${SIDE[x.side] ?? ''} 뒷다리 무릎 ${label}`} style={css('width:100%;display:block;border-radius:10px;background:#1B2433')} />
                <figcaption style={css('display:flex;justify-content:space-between;gap:8px;font-size:13px;font-variant-numeric:tabular-nums')}>
                  <span><b>{label}</b> <b style={css('font-size:15px')}>{f.deg.toFixed(1)}°</b></span>
                  <span style={css('color:#5B6472')}>{f.sec.toFixed(2)}초, {f.frame}프레임</span>
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      ))}
    </section>
  )
}
