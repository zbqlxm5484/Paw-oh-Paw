// 회차 썸네일: 그 회차에서 처음 찍은 영상의 첫 프레임. 기본 관절 그림은 쓰지 않는다.
// 이 기기에서 올린 영상이면 올릴 때 뽑아 둔 그림(camera.shotThumbs), 아니면 서버 영상(서명 주소)의 첫 프레임을 <video> 로 보인다.
// 영상이 아직 없으면 빈 어두운 칸이다.
import { useShot } from '../../api/results'
import { useSession } from '../../api/sessions'
import { shotThumbs } from '../../app/camera'

export function SessionThumb({ sessionId, w, h }: { sessionId: string | null | undefined; w: number; h: number }) {
  const sess = useSession(sessionId ?? undefined)
  const shots = [...(sess.data?.shots ?? [])].sort((a, b) => a.seq_no - b.seq_no)
  const first = shots.find((s) => s.status !== 'FAILED' && s.validity !== 'INVALID') ?? shots[0]
  const local = first ? shotThumbs[first.id] : undefined
  const shot = useShot(first && !local ? first.id : undefined)
  const url = shot.data?.video_url
  const box: React.CSSProperties = { width: w, height: h, borderRadius: 10, background: '#141B22', flex: 'none', overflow: 'hidden', display: 'block', objectFit: 'cover' }
  if (local) return <img src={local} alt="" style={box} />
  if (url) return <video src={`${url}${url.includes('#') ? '' : '#t=0.1'}`} muted playsInline preload="metadata" style={box} />
  return <div style={box} />
}
