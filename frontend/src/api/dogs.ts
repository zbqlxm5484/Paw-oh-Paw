import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { qs, request } from './client'
import type { DogCreate, DogHistoryOut, DogOut, DogUpdate, Paged, SessionHistoryItem, VitalOut } from './types'

export interface DogListParams {
  q?: string
  page?: number
  size?: number
}

export const dogKeys = {
  all: ['dogs'] as const,
  list: (p: DogListParams) => ['dogs', 'list', p] as const,
  detail: (id: string) => ['dogs', 'detail', id] as const,
  sessions: (id: string) => ['dogs', 'sessions', id] as const,
  vitals: (id: string) => ['dogs', 'vitals', id] as const,
  history: (id: string) => ['dogs', 'history', id] as const,
}

export function listDogs(p: DogListParams): Promise<Paged<DogOut>> {
  return request(`/dogs${qs({ q: p.q, page: p.page, size: p.size })}`)
}
export function getDog(id: string): Promise<DogOut> {
  return request(`/dogs/${id}`)
}
export function createDog(body: DogCreate): Promise<DogOut> {
  return request('/dogs', { method: 'POST', body })
}
export function updateDog(id: string, body: DogUpdate): Promise<DogOut> {
  return request(`/dogs/${id}`, { method: 'PATCH', body })
}
export function listDogSessions(id: string, p: { page?: number; size?: number } = {}): Promise<Paged<SessionHistoryItem>> {
  return request(`/dogs/${id}/sessions${qs({ page: p.page, size: p.size ?? 100 })}`)
}

/** 바이탈 목록(최신 날짜가 앞) */
export function listVitals(id: string): Promise<{ items: VitalOut[] }> {
  return request(`/dogs/${id}/vitals`)
}
/** 진단·수술·재활 이력(오래된 것부터) */
export function listHistory(id: string): Promise<{ items: DogHistoryOut[] }> {
  return request(`/dogs/${id}/history`)
}
/** 서버에 아직 이 API 가 없으면(404 등) 빈 목록으로 본다 */
const orEmpty = <T,>(p: Promise<{ items: T[] }>): Promise<T[]> => p.then((r) => r.items).catch(() => [])

export function useDogVitals(id: string | undefined) {
  return useQuery({ queryKey: dogKeys.vitals(id ?? ''), queryFn: () => orEmpty(listVitals(id!)), enabled: !!id })
}
export function useDogHistory(id: string | undefined) {
  return useQuery({ queryKey: dogKeys.history(id ?? ''), queryFn: () => orEmpty(listHistory(id!)), enabled: !!id })
}

export function useDogs(p: DogListParams, enabled = true) {
  return useQuery({ queryKey: dogKeys.list(p), queryFn: () => listDogs(p), placeholderData: (prev) => prev, enabled })
}

export function useDog(id: string | undefined) {
  return useQuery({ queryKey: dogKeys.detail(id ?? ''), queryFn: () => getDog(id!), enabled: !!id })
}

export function useDogSessions(id: string | undefined) {
  return useQuery({ queryKey: dogKeys.sessions(id ?? ''), queryFn: () => listDogSessions(id!), enabled: !!id })
}

export function useCreateDog() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createDog,
    onSuccess: () => qc.invalidateQueries({ queryKey: dogKeys.all }),
  })
}

export function useUpdateDog(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: DogUpdate) => updateDog(id, body),
    onSuccess: (dog) => {
      qc.setQueryData(dogKeys.detail(id), dog)
      qc.invalidateQueries({ queryKey: dogKeys.all })
    },
  })
}
