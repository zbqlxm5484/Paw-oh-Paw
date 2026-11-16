// 반려견 휴지통(15.5): 마이페이지 '반려견 복구' 팝업이 쓴다.
// 서버 기관은 GET /dogs?trash=true · POST /dogs/{id}/restore, 시연 기관은 acct.trash(브라우저 안)
import { api } from '../api/client'
import { isRemote, syncFromBackend } from './backend'
import { changed } from './db'
import type { Account } from './types'

export interface TrashItem { id: string; name: string; breed: string; deletedAt: string; purgeAt: string }

const KEEP_DAYS = 30
const plusDays = (iso: string, n: number) => new Date(new Date(iso).getTime() + n * 86400000).toISOString()

export async function listTrash(acct: Account): Promise<TrashItem[]> {
  if (!isRemote(acct.id)) {
    const now = Date.now()
    return (acct.trash ?? [])
      .filter((t) => new Date(plusDays(t.at, KEEP_DAYS)).getTime() > now)
      .map((t) => ({ id: t.dog.id, name: t.dog.name, breed: t.dog.breed, deletedAt: t.at, purgeAt: plusDays(t.at, KEEP_DAYS) }))
  }
  const out: TrashItem[] = []
  for (let page = 1; page < 20; page++) {
    const r = await api.trashDogs(page, 100)
    for (const o of r.items) {
      const at = o.deleted_at ?? o.updated_at
      out.push({ id: o.id, name: o.name, breed: o.breed, deletedAt: at, purgeAt: o.purge_at ?? plusDays(at, KEEP_DAYS) })
    }
    if (out.length >= r.total || !r.items.length) break
  }
  return out
}

/** 복구. 서버 기관은 복구 뒤 반려견·회차를 다시 읽는다. 실패하면 서버 메시지로 throw */
export async function restoreTrash(acct: Account, id: string): Promise<void> {
  if (isRemote(acct.id)) {
    await api.restoreDog(id)
    await syncFromBackend()
    return
  }
  const t = (acct.trash ?? []).find((x) => x.dog.id === id)
  if (!t) throw new Error('휴지통에 없는 반려견입니다')
  acct.trash = (acct.trash ?? []).filter((x) => x !== t)
  acct.dogs = [...acct.dogs, t.dog]
  acct.results = [...acct.results, ...t.results].sort((a, b) => (a.day === b.day ? (a.time < b.time ? 1 : -1) : a.day < b.day ? 1 : -1)) // 최신 회차가 앞
  acct.jobs = [...acct.jobs, ...t.jobs]
  changed()
}

/** "11월 10일" / 남은 날(올림, 0 이상) */
export const dayLabel = (iso: string): string => { const d = new Date(iso); return `${d.getMonth() + 1}월 ${d.getDate()}일` }
export const daysLeft = (iso: string, now = Date.now()): number => Math.max(0, Math.ceil((new Date(iso).getTime() - now) / 86400000))
