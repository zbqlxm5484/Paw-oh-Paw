import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { qs, request } from './client'
import type { DogCreate, DogOut, DogUpdate, Paged, SessionHistoryItem } from './types'

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

export function useDogs(p: DogListParams) {
  return useQuery({ queryKey: dogKeys.list(p), queryFn: () => listDogs(p), placeholderData: (prev) => prev })
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
