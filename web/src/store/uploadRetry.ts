// 업로드가 실패해 업로드 화면으로 돌아갈 때, 고른 영상을 잃지 않게 잠깐 들고 있는다(같은 탭 안에서만, 한 번 꺼내면 비운다)
let kept: { dog: string; files: File[] } | null = null

export function keepFiles(dog: string, files: File[]): void {
  kept = files.length ? { dog, files } : null
}

/** 그 반려견으로 돌아왔을 때 한 번만 꺼낸다 */
export function takeFiles(dog: string): File[] {
  if (!kept || kept.dog !== dog) return []
  const f = kept.files
  kept = null
  return f
}
