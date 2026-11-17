// '분석 시작'을 누른 뒤 영상을 서버로 올리는 동안의 진행(몇 개 중 몇 개). 업로드 화면이 덮개로 보여 준다.
// 영상을 다 올려야 분석 중 화면으로 넘어가므로, 그 사이 화면이 멈춘 것처럼 보이지 않게 한다
import { useSyncExternalStore } from 'react'

export interface UploadProgress {
  /** 다 올린 영상 수 */
  done: number
  /** 이번에 올릴 영상 수(폰에서 이미 올린 영상만 있으면 0) */
  total: number
}

let cur: UploadProgress | null = null
const subs = new Set<() => void>()

/** null 이면 올리는 중이 아니다 */
export function setUploadProgress(p: UploadProgress | null): void {
  cur = p
  subs.forEach((fn) => fn())
}

const subscribe = (fn: () => void) => {
  subs.add(fn)
  return () => {
    subs.delete(fn)
  }
}

export function useUploadProgress(): UploadProgress | null {
  return useSyncExternalStore(subscribe, () => cur)
}
