import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'

import { dogKeys, listDogSessions } from './dogs'
import { qs, request } from './client'
import type { AnglesOut, BaseKind, CompareOut, DogOut, GaitType, ReportOut, ReportsOut, SessionResultOut, ShotDetailOut, TrendsOut } from './types'

export const resultKeys = {
  result: (id: string) => ['sessions', 'result', id] as const,
  reports: (id: string) => ['sessions', 'reports', id] as const,
  shot: (id: string) => ['shots', 'detail', id] as const,
  angles: (id: string) => ['shots', 'angles', id] as const,
  compare: (dogId: string, p: CompareParams) => ['dogs', 'compare', dogId, p] as const,
  trends: (dogId: string, p: TrendsParams) => ['dogs', 'trends', dogId, p] as const,
}

export interface CompareParams {
  target?: string
  base?: BaseKind | string
  gait_type?: GaitType
}
export interface TrendsParams {
  metric_code: string
  gait_type: GaitType
  limb?: string
}

export const getSessionResult = (id: string) => request<SessionResultOut>(`/sessions/${id}/result`)
export const getReports = (id: string) => request<ReportsOut>(`/sessions/${id}/reports`)
export const regenerateReport = (reportId: string) => request<ReportOut>(`/reports/${reportId}/regenerate`, { method: 'POST' })
export const getShot = (id: string) => request<ShotDetailOut>(`/shots/${id}`)
export const getAngles = (id: string) => request<AnglesOut>(`/shots/${id}/angles`)
export const getCompare = (dogId: string, p: CompareParams) => request<CompareOut>(`/dogs/${dogId}/compare${qs({ target: p.target, base: p.base, gait_type: p.gait_type })}`)
export const getTrends = (dogId: string, p: TrendsParams) => request<TrendsOut>(`/dogs/${dogId}/trends${qs({ metric_code: p.metric_code, gait_type: p.gait_type, limb: p.limb })}`)

export function useSessionResult(id: string | undefined) {
  return useQuery({ queryKey: resultKeys.result(id ?? ''), queryFn: () => getSessionResult(id!), enabled: !!id })
}

/** 보고서 상태. DONE 이 되고 PENDING·GENERATING 판본이 없어질 때까지 3초마다(api-spec 1.7). */
export function useReports(id: string | undefined) {
  return useQuery({
    queryKey: resultKeys.reports(id ?? ''),
    queryFn: () => getReports(id!),
    enabled: !!id,
    refetchInterval: (q) => {
      const d = q.state.data
      if (!d) return false
      const busy = d.session_status !== 'DONE' || d.reports.length === 0 || d.reports.some((r) => r.status === 'PENDING' || r.status === 'GENERATING')
      return busy ? 3000 : false
    },
  })
}

export function useRegenerateReport(sessionId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (reportId: string) => regenerateReport(reportId),
    onSettled: () => qc.invalidateQueries({ queryKey: resultKeys.reports(sessionId) }),
  })
}

export function useShot(id: string | undefined) {
  return useQuery({
    queryKey: resultKeys.shot(id ?? ''),
    queryFn: () => getShot(id!),
    enabled: !!id,
    // 결과 영상이 아직이면 3초마다
    refetchInterval: (q) => (q.state.data && q.state.data.video_status === 'PENDING' ? 3000 : false),
  })
}

export function useAngles(id: string | undefined, enabled = true) {
  return useQuery({ queryKey: resultKeys.angles(id ?? ''), queryFn: () => getAngles(id!), enabled: !!id && enabled })
}

export function useCompare(dogId: string | undefined, p: CompareParams) {
  return useQuery({ queryKey: resultKeys.compare(dogId ?? '', p), queryFn: () => getCompare(dogId!, p), enabled: !!dogId, retry: false })
}

export function useTrends(dogId: string | undefined, p: TrendsParams) {
  return useQuery({ queryKey: resultKeys.trends(dogId ?? '', p), queryFn: () => getTrends(dogId!, p), enabled: !!dogId })
}

/** 분석 결과 목록(S5 목록): 기관 전체 회차 API 가 없어 반려견별 이력을 모아 만든다(screenPlan 6절 #5 2안). */
export function useAllSessions(dogs: DogOut[] | undefined) {
  const list = dogs ?? []
  return useQueries({
    queries: list.map((d) => ({
      queryKey: dogKeys.sessions(d.id),
      queryFn: () => listDogSessions(d.id),
      staleTime: 10_000,
    })),
    combine: (results) => ({
      isPending: results.some((r) => r.isPending),
      isError: results.some((r) => r.isError) && results.every((r) => !r.isSuccess),
      items: results.flatMap((r, i) => (r.data ? r.data.items.map((s) => ({ ...s, dog: list[i] })) : [])),
    }),
  })
}
