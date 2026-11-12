// 회차·촬영 썸네일. 기본 관절 그림은 쓰지 않는다.
// 이 기기에서 올린 영상이면 올릴 때 뽑아 둔 그림(camera.shotThumbs), 아니면 서버 결과 영상(서명 주소, VITE_API_BASE 붙임)을
// 보이지 않게 불러 앞부분 프레임을 한 번만 그림으로 뽑아 기억해 둔다(camera.serverThumbs). 그 뒤로는 영상을 다시 안 불러온다.
// 영상 자체는 화면에 절대 보이지 않는다(로딩 중 검은 칸이 보이던 문제). 그림이 준비되기 전에는 옅게 반짝이는 자리표시(pp-skel),
// 그림을 못 뽑으면(CORS·검은 프레임뿐·오류) 반짝임 없는 자리표시만 둔다. 분석에 실패한 촬영은 결과 영상이 안 생기므로 묻지 않는다.
import { useEffect, useRef, useState } from 'react'
import { fileUrl } from '../../api/labels'
import { useShot } from '../../api/results'
import { useSession } from '../../api/sessions'
import type { ShotOut } from '../../api/types'
import { captureFrame, serverThumbs, shotThumbs } from '../../app/camera'

const BOX: React.CSSProperties = { background: '#E9E4DC', overflow: 'hidden', display: 'block', objectFit: 'cover' }
/** 프레임을 뽑아 볼 시점(초). 맨 앞은 검은 프레임인 영상이 많아 조금 뒤부터 */
const TRY_AT = [0.5, 1.5]

/** 촬영 하나의 썸네일 */
export function ShotThumb({ shot, style }: { shot: Pick<ShotOut, 'id' | 'status'> | undefined; style: React.CSSProperties }) {
  const id = shot?.id
  const cached = id ? shotThumbs[id] || serverThumbs[id] : undefined
  const q = useShot(id && !cached && shot?.status !== 'FAILED' ? id : undefined)
  const url = fileUrl(q.data?.video_url)
  const [img, setImg] = useState<string | undefined>(cached)
  const [gaveUp, setGaveUp] = useState(false)
  const tries = useRef(0)
  const vref = useRef<HTMLVideoElement>(null)
  useEffect(() => { setImg(cached); setGaveUp(false); tries.current = 0 }, [cached, id])
  const box = { ...BOX, ...style }
  if (img) return <img src={img} alt="" style={box} />
  if (!url || !id || gaveUp) return <span className={gaveUp || !url ? undefined : 'pp-skel'} style={box} />
  const seekNext = () => {
    const v = vref.current
    if (!v) return
    const t = TRY_AT[tries.current]
    if (t === undefined) { setGaveUp(true); return }
    v.currentTime = Math.min(t, Math.max(0, (v.duration || t) - 0.05))
  }
  return (
    <span className="pp-skel" style={{ ...box, position: 'relative' }}>
      <video ref={vref} src={url} muted playsInline preload="auto" crossOrigin="anonymous"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0, pointerEvents: 'none' }}
        onLoadedMetadata={seekNext}
        onSeeked={() => {
          const v = vref.current
          if (!v) return
          const d = captureFrame(v, id)
          if (d) { setImg(d); return }
          tries.current += 1
          seekNext()
        }}
        onError={() => setGaveUp(true)} />
    </span>
  )
}

/** 회차 썸네일: 그 회차에서 처음 찍은(실패하지 않은) 영상 */
export function SessionThumb({ sessionId, w, h }: { sessionId: string | null | undefined; w: number; h: number }) {
  const sess = useSession(sessionId ?? undefined)
  const shots = [...(sess.data?.shots ?? [])].sort((a, b) => a.seq_no - b.seq_no)
  const first = shots.find((s) => s.status !== 'FAILED' && s.validity !== 'INVALID') ?? shots[0]
  return <ShotThumb shot={first} style={{ width: w, height: h, borderRadius: 10, flex: 'none' }} />
}
