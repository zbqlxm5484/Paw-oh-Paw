/**
 * 보고서 PDF 저장. 앱(안드로이드 WebView)은 window.open 으로 내려받기가 안 되므로
 * 서명 주소를 fetch 해 캐시 폴더에 쓰고 공유 시트(파일에 저장·드라이브·메신저)로 넘긴다. 브라우저에서는 새 탭으로 연다.
 */
import { Capacitor } from '@capacitor/core'

export type SaveHow = 'shared' | 'opened'

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onerror = () => reject(r.error)
    r.onload = () => resolve(String(r.result).split(',')[1] ?? '')
    r.readAsDataURL(blob)
  })
}

/** 파일 이름에 못 쓰는 글자만 바꾼다(한글·공백·괄호는 그대로) */
const safeName = (s: string) => s.replace(/[\\/:*?"<>|]/g, '_').trim() || 'report'

export async function savePdf(url: string, fileName: string): Promise<SaveHow> {
  if (!Capacitor.isNativePlatform()) {
    window.open(url, '_blank', 'noopener')
    return 'opened'
  }
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await blobToBase64(await res.blob())
  const { Filesystem, Directory } = await import('@capacitor/filesystem')
  const { Share } = await import('@capacitor/share')
  const written = await Filesystem.writeFile({ path: `${safeName(fileName)}.pdf`, data, directory: Directory.Cache })
  await Share.share({ title: fileName, files: [written.uri] })
  return 'shared'
}
