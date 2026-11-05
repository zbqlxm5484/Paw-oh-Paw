// 회차·촬영 썸네일. 기본 관절 그림은 쓰지 않는다.
// 이 기기에서 올린 영상이면 올릴 때 뽑아 둔 그림(camera.shotThumbs), 아니면 서버 결과 영상(서명 주소, VITE_API_BASE 붙임)의 첫 프레임을 <video> 로 보인다.
// 결과 영상이 아직 없으면 빈 어두운 칸. 분석에 실패한 촬영은 결과 영상이 안 생기므로 묻지 않는다.
import { fileUrl } from '../../api/labels'
import { useShot } from '../../api/results'
import { useSession } from '../../api/sessions'
import type { ShotOut } from '../../api/types'
import { shotThumbs } from '../../app/camera'

const BOX: React.CSSProperties = { background: '#141B22', overflow: 'hidden', display: 'block', objectFit: 'cover' }

/** 촬영 하나의 썸네일 */
export function ShotThumb({ shot, style }: { shot: Pick<ShotOut, 'id' | 'status'> | undefined; style: React.CSSProperties }) {
  const local = shot ? shotThumbs[shot.id] : undefined
  const q = useShot(shot && !local && shot.status !== 'FAILED' ? shot.id : undefined)
  const url = fileUrl(q.data?.video_url)
  const box = { ...BOX, ...style }
  if (local) return <img src={local} alt="" style={box} />
  if (url) return <video src={`${url}#t=0.1`} muted playsInline preload="metadata" style={box} />
  return <div style={box} />
}

/** 회차 썸네일: 그 회차에서 처음 찍은(실패하지 않은) 영상 */
export function SessionThumb({ sessionId, w, h }: { sessionId: string | null | undefined; w: number; h: number }) {
  const sess = useSession(sessionId ?? undefined)
  const shots = [...(sess.data?.shots ?? [])].sort((a, b) => a.seq_no - b.seq_no)
  const first = shots.find((s) => s.status !== 'FAILED' && s.validity !== 'INVALID') ?? shots[0]
  return <ShotThumb shot={first} style={{ width: w, height: h, borderRadius: 10, flex: 'none' }} />
}
