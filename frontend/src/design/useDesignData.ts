/**
 * 디자인 화면이 쓰는 데이터를 API 에서 모아 디자인 모양(adapter)으로 넘긴다.
 * 반려견 목록 → 반려견별 측정 이력 → 끝난 회차의 결과(수치) 순으로 가져오고,
 * 측정 중인 회차는 2.5초마다 다시 읽어 "분석 중" 진행도를 만든다.
 */
import { useEffect, useMemo, useRef } from 'react'
import { useQueries, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '../app/auth'
import * as dogsApi from '../api/dogs'
import { getSessionResult, resultKeys, useAllSessions, useCompare, useReports, useSessionResult, useTrends } from '../api/results'
import * as sessApi from '../api/sessions'
import type { DogCreate, DogUpdate, SessionHistoryItem, SessionResultOut } from '../api/types'
import { TREND_CODE, compareRows, toAcct, toAna, toDog, toResult, trendLines, type DAna, type DDog, type DRes } from './adapter'

/** 결과(수치)를 미리 읽어 두는 회차 수. 목록·홈 요약에 쓴다 */
const RESULT_PREFETCH = 40

export interface DesignData {
  dogs: DDog[]
  results: DRes[]
  ana: DAna | null
  acct: ReturnType<typeof toAcct>
  loading: boolean
  loggedIn: boolean
  resultById: (id: string) => DRes | undefined
}

/** @param focusSessionId 지금 보고 있는 회차. 목록에 아직 없으면(방금 끝난 회차) 결과만 따로 읽어 끼워 넣는다 */
export function useDesignData(focusSessionId?: string): DesignData {
  const { loggedIn, staff } = useAuth()
  const qc = useQueryClient()
  const dogsQ = dogsApi.useDogs({ size: 100 }, loggedIn)
  const rawDogs = loggedIn ? dogsQ.data?.items : undefined
  const hist = useAllSessions(rawDogs)
  const doneIds = useMemo(
    () => hist.items.filter((s) => s.status === 'DONE').sort((a, b) => b.measured_on.localeCompare(a.measured_on)).slice(0, RESULT_PREFETCH).map((s) => s.id),
    [hist.items],
  )
  const resultsQ = useQueries({
    queries: doneIds.map((id) => ({ queryKey: resultKeys.result(id), queryFn: () => getSessionResult(id), staleTime: 60_000 })),
    combine: (rs) => {
      const m = new Map<string, SessionResultOut>()
      rs.forEach((r, i) => {
        if (r.data) m.set(doneIds[i], r.data)
      })
      return m
    },
  })

  const dogs = useMemo(() => (rawDogs ?? []).map(toDog), [rawDogs])
  // 목록에 없는 회차(방금 끝난 회차)는 결과를 따로 읽는다
  const missing = !!focusSessionId && !hist.isPending && !hist.items.some((s) => s.id === focusSessionId)
  const focusQ = useSessionResult(missing ? focusSessionId : undefined)
  const results = useMemo(() => {
    const list = hist.items
      .filter((s) => s.status === 'DONE' || s.status === 'FAILED')
      .map((s) => toResult(s, s.dog.id, resultsQ.get(s.id)))
    const f = focusQ.data
    if (missing && f && !list.some((r) => r.id === f.id)) {
      const h: SessionHistoryItem = { id: f.id, measured_on: f.measured_on, weight_kg: f.weight_kg, status: f.status, is_baseline: false, valid_passes: { LEFT: 0, RIGHT: 0 }, model_version: f.model_version, reports: null }
      list.push(toResult(h, f.dog_id, f))
    }
    return list.sort((a, b) => b.measured_on.localeCompare(a.measured_on) || b.id.localeCompare(a.id))
  }, [hist.items, resultsQ, focusQ.data, missing])

  // 측정 중인 회차(반려견의 open_session_id). 하나만 "분석 중" 으로 보여 준다
  const openDog = dogs.find((d) => d.open)
  const sessQ = sessApi.useSession(openDog?.open ?? undefined)
  const ana = useMemo(() => (openDog && openDog.open ? toAna(sessQ.data, openDog.id, openDog.open) : null), [openDog, sessQ.data])
  // 측정 중이던 회차가 끝나면 반려견·이력 목록을 다시 읽는다
  const lastStatus = useRef<string | undefined>(undefined)
  useEffect(() => {
    const st = sessQ.data?.status
    if (lastStatus.current && lastStatus.current !== st && (st === 'DONE' || st === 'FAILED')) qc.invalidateQueries({ queryKey: dogsApi.dogKeys.all })
    lastStatus.current = st
  }, [sessQ.data?.status, qc])

  const acct = useMemo(() => toAcct(staff), [staff])
  return {
    dogs, results, ana, acct, loggedIn,
    loading: loggedIn && (dogsQ.isPending || hist.isPending),
    resultById: (id) => results.find((r) => r.id === id),
  }
}

/** 경과 비교 화면 값. 비교 대상 반려견·기준·추이 지표가 바뀌면 다시 읽는다 */
export function useCompareData(dogId: string | undefined, mode: 'base' | 'prev', tk: string, focus: import('../api/types').Limb | null) {
  const cmpQ = useCompare(dogId, { base: mode === 'base' ? 'BASELINE' : 'PREVIOUS', gait_type: 'TROT' })
  const trQ = useTrends(dogId, { metric_code: TREND_CODE[tk] ?? 'rom_stifle', gait_type: 'TROT' })
  return useMemo(
    () => ({
      cmp: cmpQ.data, rows: compareRows(cmpQ.data, focus), trend: trendLines(trQ.data, tk),
      error: cmpQ.error as Error | null, pending: cmpQ.isPending,
    }),
    [cmpQ.data, cmpQ.error, cmpQ.isPending, trQ.data, tk, focus],
  )
}

export function useReportData(sessionId: string | undefined) {
  return useReports(sessionId)
}

/** 화면 동작(등록·수정·기준 회차·회차 시작·업로드·종료). 끝나면 관련 조회를 다시 읽는다 */
export function useDesignActions() {
  const qc = useQueryClient()
  const invDogs = () => qc.invalidateQueries({ queryKey: dogsApi.dogKeys.all })
  const invSession = (id: string) => {
    qc.invalidateQueries({ queryKey: sessApi.sessionKeys.detail(id) })
    return invDogs()
  }
  return {
    createDog: async (b: DogCreate) => {
      const d = await dogsApi.createDog(b)
      await invDogs()
      return d
    },
    updateDog: async (id: string, b: DogUpdate) => {
      const d = await dogsApi.updateDog(id, b)
      await invDogs()
      return d
    },
    startSession: async (dogId: string, weight: number | null) => {
      const s = await sessApi.startSession(dogId, { weight_kg: weight })
      await invDogs()
      return s
    },
    uploadShot: async (sessionId: string, file: File) => {
      const out = await sessApi.uploadShot(sessionId, file)
      await invSession(sessionId)
      return out
    },
    completeSession: async (sessionId: string) => {
      const s = await sessApi.completeSession(sessionId)
      await invSession(sessionId)
      return s
    },
    cancelSession: async (sessionId: string) => {
      await sessApi.cancelSession(sessionId)
      await invSession(sessionId)
    },
    regenerateReport: async (sessionId: string, reportId: string) => {
      const r = await import('../api/results').then((m) => m.regenerateReport(reportId))
      await qc.invalidateQueries({ queryKey: resultKeys.reports(sessionId) })
      return r
    },
    invalidateSession: invSession,
  }
}
