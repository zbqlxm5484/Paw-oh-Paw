import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { dogKeys } from './dogs'
import { request } from './client'
import type { SessionCreate, SessionDetailOut, SessionOut, ShotOut, ShotUploadOut } from './types'

export const sessionKeys = {
  detail: (id: string) => ['sessions', 'detail', id] as const,
}

export function startSession(dogId: string, body: SessionCreate): Promise<SessionOut> {
  return request(`/dogs/${dogId}/sessions`, { method: 'POST', body })
}
export function getSession(id: string): Promise<SessionDetailOut> {
  return request(`/sessions/${id}`)
}
export function cancelSession(id: string): Promise<void> {
  return request(`/sessions/${id}`, { method: 'DELETE' })
}
export function completeSession(id: string): Promise<SessionOut> {
  return request(`/sessions/${id}/complete`, { method: 'POST' })
}
export function uploadShot(sessionId: string, file: File): Promise<ShotUploadOut> {
  const fd = new FormData()
  fd.append('file', file, file.name)
  return request(`/sessions/${sessionId}/shots`, { method: 'POST', body: fd })
}
export function retryShot(shotId: string): Promise<ShotOut> {
  return request(`/shots/${shotId}/retry`, { method: 'POST' })
}
export function deleteShot(shotId: string): Promise<void> {
  return request(`/shots/${shotId}`, { method: 'DELETE' })
}

/** 측정 중·집계 중이면 2.5초마다 다시 부른다(api-spec 1.7). */
const POLL_MS = 2500
export function useSession(id: string | undefined) {
  return useQuery({
    queryKey: sessionKeys.detail(id ?? ''),
    queryFn: () => getSession(id!),
    enabled: !!id,
    refetchInterval: (q) => {
      const s = q.state.data?.status
      return s === 'MEASURING' || s === 'AGGREGATING' ? POLL_MS : false
    },
    refetchIntervalInBackground: true,
  })
}

function useInvalidateSession(sessionId: string) {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: sessionKeys.detail(sessionId) })
    qc.invalidateQueries({ queryKey: dogKeys.all })
  }
}

export function useStartSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ dogId, body }: { dogId: string; body: SessionCreate }) => startSession(dogId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: dogKeys.all }),
  })
}

export function useUploadShot(sessionId: string) {
  const inv = useInvalidateSession(sessionId)
  return useMutation({ mutationFn: (file: File) => uploadShot(sessionId, file), onSettled: inv })
}

export function useCompleteSession(sessionId: string) {
  const inv = useInvalidateSession(sessionId)
  return useMutation({ mutationFn: () => completeSession(sessionId), onSettled: inv })
}

export function useCancelSession(sessionId: string) {
  const inv = useInvalidateSession(sessionId)
  return useMutation({ mutationFn: () => cancelSession(sessionId), onSettled: inv })
}

export function useRetryShot(sessionId: string) {
  const inv = useInvalidateSession(sessionId)
  return useMutation({ mutationFn: (shotId: string) => retryShot(shotId), onSettled: inv })
}

export function useDeleteShot(sessionId: string) {
  const inv = useInvalidateSession(sessionId)
  return useMutation({ mutationFn: (shotId: string) => deleteShot(shotId), onSettled: inv })
}
