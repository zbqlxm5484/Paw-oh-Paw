// 수의사용 보고서 '무릎을 가장 굽힌 순간·가장 편 순간'(285): 각도 API(GET /shots/{id}/angles)의 프레임별 각도에서
// 가장 작은 각도(가장 굽힘)와 가장 큰 각도(가장 폄)의 프레임을 찾고, 그 촬영의 결과 영상 주소와 함께 돌려준다.
// 그림은 화면(AppAngleFrames.tsx)이 결과 영상을 그 시각으로 옮겨 잘라 만든다. 측정한 프레임만 쓰고 값을 메우거나 다듬지 않는다.
// 웹(web/src/views/angleFrames.ts)에 같은 코드가 있다(두 프로젝트는 코드를 공유하지 않는다). 고치면 둘 다.
import type { AnglesOut, JointCode } from '../../api/types'
import { pickShots, type ShotLite } from './gaitClip'

/** 고른 프레임 하나: frame 은 영상 프레임 번호, sec 는 그 프레임의 시각(초) */
export interface FramePick { pass_no: number; frame: number; sec: number; deg: number }
/** flex = 각도가 가장 작은 프레임(가장 굽힘), ext = 가장 큰 프레임(가장 폄) */
export interface Extremes { flex: FramePick; ext: FramePick }

const num = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

/** 계열에서 가장 작은 값·가장 큰 값의 위치. 값이 같으면 앞의 것. 값 있는 프레임이 2개 미만이거나 최소와 최대가 같으면 null */
export function minMaxIndex(s: readonly (number | null)[]): { min: number; max: number } | null {
  let min = -1, max = -1, n = 0
  for (let i = 0; i < s.length; i++) {
    const v = s[i]
    if (!num(v)) continue
    n++
    if (min < 0 || v < (s[min] as number)) min = i
    if (max < 0 || v > (s[max] as number)) max = i
  }
  if (n < 2 || (s[min] as number) === (s[max] as number)) return null
  return { min, max }
}

/** 한 촬영의 각도 응답에서, 고른 보행 유형의 통과들 전체에 걸쳐 joint 가 가장 굽힌·가장 편 프레임. 못 찾으면 null */
export function extremeFrames(resp: AnglesOut, gait: string, joint: JointCode): Extremes | null {
  const fps = resp.fps
  if (!num(fps) || fps <= 0) return null
  let flex: FramePick | null = null, ext: FramePick | null = null
  for (const p of resp.passes ?? []) {
    if (p.gait_type !== gait) continue
    const s = p.angles?.[joint] ?? []
    const at = (i: number): FramePick => {
      const frame = p.start_frame + i
      return { pass_no: p.pass_no, frame, sec: frame / fps, deg: s[i] as number }
    }
    const mm = minMaxIndex(s)
    if (!mm) continue
    const lo = at(mm.min), hi = at(mm.max)
    if (!flex || lo.deg < flex.deg) flex = lo
    if (!ext || hi.deg > ext.deg) ext = hi
  }
  return flex && ext && flex.deg < ext.deg ? { flex, ext } : null
}

/** 영상에서 그 프레임으로 옮길 시각(초): 프레임 한가운데. 영상 길이를 알면 끝을 넘지 않게 */
export function seekSec(frame: number, fps: number, duration?: number): number {
  const t = (frame + 0.5) / fps
  return duration && Number.isFinite(duration) && duration > 0 ? Math.min(t, Math.max(0, duration - 0.5 / fps)) : t
}

/** 한 쪽(카메라 쪽 다리) 한 촬영의 결과 */
export interface FrameShot { side: 'LEFT' | 'RIGHT'; shotId: string; seqNo: number | null; gait: string; fps: number; videoUrl: string; ex: Extremes }

type ShotRow = ShotLite & { seq_no?: number }

/** 회차 id → 쪽마다 한 촬영의 가장 굽힌·편 프레임과 결과 영상 주소. 결과 영상이 준비되지 않았거나 각도가 없는 촬영은 건너뛴다.
 *  보행 유형·촬영 고르기는 3D·무릎 곡선과 같은 pickShots. 아무것도 못 찾거나 오류면 빈 배열 */
export async function loadAngleFrames(
  deps: {
    session: (id: string) => Promise<{ shots: ShotRow[] }>
    angles: (shotId: string) => Promise<AnglesOut>
    shot: (shotId: string) => Promise<{ video_status?: string; video_url: string | null }>
  },
  sessionId: string,
  prefer: string | null,
  joint: JointCode = 'stifle',
): Promise<FrameShot[]> {
  try {
    const s = await deps.session(sessionId)
    const shots = s.shots ?? []
    const pick = pickShots(shots, prefer)
    if (!pick) return []
    const out: FrameShot[] = []
    for (const [side, ids] of [['LEFT', pick.L], ['RIGHT', pick.R]] as const) {
      for (const id of ids) {
        const [a, d] = await Promise.all([deps.angles(id).catch(() => null), deps.shot(id).catch(() => null)])
        if (!a || !d || d.video_status !== 'READY' || !d.video_url) continue
        // 각도 응답의 통과 중 이 쪽(camera_side)만
        const ex = extremeFrames({ ...a, passes: (a.passes ?? []).filter((p) => p.camera_side === side) }, pick.gait, joint)
        if (!ex) continue
        out.push({ side, shotId: id, seqNo: shots.find((x) => x.id === id)?.seq_no ?? null, gait: pick.gait, fps: a.fps, videoUrl: d.video_url, ex })
        break
      }
    }
    return out
  } catch {
    return []
  }
}
