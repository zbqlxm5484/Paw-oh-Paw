// 첨부한 영상의 첫 프레임 미리보기(앱 촬영 화면과 같은 방식). 업로드 칸에 디자인 그림 대신 쓴다
import { useEffect, useRef, useState } from 'react'
import { api, fileHref, type ShotOut } from '../api/client'

/** 영상 파일의 첫 프레임을 작은 jpeg data URL 로. 못 뽑으면 '' */
export async function firstFrame(file: File, width = 320): Promise<string> {
  const url = URL.createObjectURL(file)
  try {
    const v = document.createElement('video')
    v.muted = true
    v.playsInline = true
    v.preload = 'auto'
    v.src = url
    await new Promise<void>((ok, bad) => {
      v.onloadeddata = () => ok()
      v.onerror = () => bad(new Error('video'))
      setTimeout(() => bad(new Error('timeout')), 8000)
    })
    // 0초가 검은 프레임인 영상이 있어 조금 뒤로
    v.currentTime = Math.min(0.1, (v.duration || 1) / 2)
    await new Promise<void>((ok) => {
      v.onseeked = () => ok()
      setTimeout(ok, 1500)
    })
    const h = Math.round((width * (v.videoHeight || 9)) / (v.videoWidth || 16))
    const c = document.createElement('canvas')
    c.width = width
    c.height = h
    c.getContext('2d')!.drawImage(v, 0, 0, width, h)
    return c.toDataURL('image/jpeg', 0.7)
  } catch {
    return ''
  } finally {
    URL.revokeObjectURL(url)
  }
}

/** files 각각의 첫 프레임. 새 파일이 들어오면 그 파일만 뽑는다.
 * (전에는 썸네일 하나가 끝나 map 이 바뀔 때마다 효과를 정리하면서 아직 뽑던 다른 파일 결과를 버려, 여러 개 올리면 하나만 떴다) */
export function useFirstFrames(files: File[]): Map<File, string> {
  const [map, setMap] = useState(() => new Map<File, string>())
  const started = useRef(new WeakSet<File>())
  useEffect(() => {
    for (const f of files) {
      if (started.current.has(f)) continue
      started.current.add(f)
      void firstFrame(f).then((u) => {
        if (u) setMap((m) => new Map(m).set(f, u))
      })
    }
  }, [files])
  return map
}

/** 폰에서 올린 촬영의 서버 영상 주소(서명). 결과 영상이 준비된 촬영만 있다. <video> 의 첫 프레임을 썸네일로 쓴다 */
export function useShotVideos(shots: ShotOut[]): Record<string, string> {
  const [urls, setUrls] = useState<Record<string, string>>({})
  const busy = useRef(new Set<string>())
  useEffect(() => {
    for (const s of shots) {
      // 분석에 실패한 촬영은 결과 영상이 만들어지지 않으니 다시 묻지 않는다
      if (urls[s.id] || busy.current.has(s.id) || s.status === 'FAILED' || s.video_status === 'FAILED') continue
      busy.current.add(s.id)
      void api
        .shot(s.id)
        .then((d) => {
          if (d.video_url) setUrls((u) => ({ ...u, [s.id]: fileHref(d.video_url!) })) // VITE_API_BASE 를 따로 줄 때도 맞게
        })
        .catch(() => undefined)
        .finally(() => busy.current.delete(s.id)) // 아직 준비 전이면 다음 조회(3초) 때 다시
    }
  }, [shots, urls])
  return urls
}
