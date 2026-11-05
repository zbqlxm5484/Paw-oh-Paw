// 첨부한 영상의 첫 프레임 미리보기(앱 촬영 화면과 같은 방식). 업로드 칸에 디자인 그림 대신 쓴다
import { useEffect, useState } from 'react'

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

/** files 각각의 첫 프레임. 새 파일이 들어오면 그 파일만 뽑는다 */
export function useFirstFrames(files: File[]): Map<File, string> {
  const [map, setMap] = useState(() => new Map<File, string>())
  useEffect(() => {
    let alive = true
    for (const f of files) {
      if (map.has(f)) continue
      map.set(f, '')
      void firstFrame(f).then((u) => {
        if (!alive || !u) return
        setMap((m) => new Map(m).set(f, u))
      })
    }
    return () => {
      alive = false
    }
  }, [files, map])
  return map
}
