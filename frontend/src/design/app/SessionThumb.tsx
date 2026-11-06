// 회차·촬영 썸네일. 기본 관절 그림은 쓰지 않는다.
// 이 기기에서 올린 영상이면 올릴 때 뽑아 둔 그림(camera.shotThumbs), 아니면 서버 결과 영상(서명 주소, VITE_API_BASE 붙임)에서
// 첫 프레임을 한 번만 뽑아 그림으로 기억해 둔다(camera.serverThumbs). 그 뒤로는 영상을 다시 안 불러온다.
// 그림이 준비되기 전에는 검은 칸 대신 옅게 반짝이는 자리표시(pp-skel)를 보인다.
// 결과 영상이 아직 없으면 자리표시 그대로. 분석에 실패한 촬영은 결과 영상이 안 생기므로 묻지 않는다.
import { useEffect, useRef, useState } from 'react'
import { fileUrl } from '../../api/labels'
import { useShot } from '../../api/results'
import { useSession } from '../../api/sessions'
import type { ShotOut } from '../../api/types'
import { captureFrame, serverThumbs, shotThumbs } from '../../app/camera'

const BOX: React.CSSProperties = { background: '#E9E4DC', overflow: 'hidden', display: 'block', objectFit: 'cover' }

/** 촬영 하나의 썸네일 */
export function ShotThumb({ shot, style }: { shot: Pick<ShotOut, 'id' | 'status'> | undefined; style: React.CSSProperties }) {
  const id = shot?.id
  const cached = id ? shotThumbs[id] || serverThumbs[id] : undefined
  const q = useShot(id && !cached && shot?.status !== 'FAILED' ? id : undefined)
  const url = fileUrl(q.data?.video_url)
  const [img, setImg] = useState<string | undefined>(cached)
  const [plain, setPlain] = useState(false) // CORS 로 못 받으면 이전처럼 영상을 그대로 보인다
  const vref = useRef<HTMLVideoElement>(null)
  useEffect(() => { setImg(cached) }, [cached, id])
  const box = { ...BOX, ...style }
  if (img) return <img src={img} alt="" style={box} />
  if (url && id && plain) return <video src={`${url}#t=0.1`} muted playsInline preload="metadata" style={box} />
  if (url && id) {
    // 보이지 않는 <video>(CORS) 로 첫 프레임을 받아 그림으로 바꾼다. 못 뽑으면 영상 자체를 보인다(이전 방식)
    return (
      <span className="pp-skel" style={{ ...box, position: 'relative' }}>
        <video ref={vref} src={`${url}#t=0.1`} muted playsInline preload="auto" crossOrigin="anonymous"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', opacity: 0 }}
          onLoadedData={() => { const v = vref.current; if (!v) return; const d = captureFrame(v, id); if (d) setImg(d); else setPlain(true) }}
          onError={() => setPlain(true)} />
      </span>
    )
  }
  return <span className="pp-skel" style={box} />
}

/** 회차 썸네일: 그 회차에서 처음 찍은(실패하지 않은) 영상 */
export function SessionThumb({ sessionId, w, h }: { sessionId: string | null | undefined; w: number; h: number }) {
  const sess = useSession(sessionId ?? undefined)
  const shots = [...(sess.data?.shots ?? [])].sort((a, b) => a.seq_no - b.seq_no)
  const first = shots.find((s) => s.status !== 'FAILED' && s.validity !== 'INVALID') ?? shots[0]
  return <ShotThumb shot={first} style={{ width: w, height: h, borderRadius: 10, flex: 'none' }} />
}
