/**
 * 가짜 서버의 회차 수치·비교·추이·촬영 상세. 회차 ID 와 수치 코드로 정해지는 값이라 새로고침해도 같다.
 * 수치 코드와 단위는 api-spec 10.4, 응답 모양은 7·8절.
 */
import type { AnglesOut, CompareItem, CompareOut, GaitType, Judgement, LimbCompareOut, MetricLimb, MetricOut, Pair, Reason, SessionResultOut, ShotDetailOut, TrendsOut, Unit } from '../api/types'
import { dogs, findDog, reason, sessions, toSessionOut, validPasses, type MockSession, type MockShot } from './db'

/** 수치 정의: 코드, 단위, 다리, 기준값, 흔들림 폭 */
const DEFS: { code: string; unit: Unit; limbs: MetricLimb[]; base: number; spread: number }[] = [
  { code: 'rom_stifle', unit: 'deg', limbs: ['LH', 'RH'], base: 38, spread: 6 },
  { code: 'rom_hip', unit: 'deg', limbs: ['LH', 'RH'], base: 30, spread: 4 },
  { code: 'rom_tarsus', unit: 'deg', limbs: ['LH', 'RH'], base: 42, spread: 5 },
  { code: 'rom_shoulder', unit: 'deg', limbs: ['LF', 'RF'], base: 34, spread: 4 },
  { code: 'rom_elbow', unit: 'deg', limbs: ['LF', 'RF'], base: 52, spread: 5 },
  { code: 'rom_carpus', unit: 'deg', limbs: ['LF', 'RF'], base: 60, spread: 6 },
  { code: 'stride_length', unit: 'pct_body', limbs: ['LF', 'RF', 'LH', 'RH'], base: 58, spread: 8 },
  { code: 'stance_ratio', unit: 'pct', limbs: ['LF', 'RF', 'LH', 'RH'], base: 61, spread: 4 },
  { code: 'paw_lift', unit: 'pct_body', limbs: ['LF', 'RF', 'LH', 'RH'], base: 12, spread: 3 },
  { code: 'walk_speed', unit: 'body_per_sec', limbs: ['NONE'], base: 1.4, spread: 0.3 },
  { code: 'gait_cycles', unit: 'count', limbs: ['NONE'], base: 10, spread: 3 },
]

function hash(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619)
  return (h >>> 0) / 4294967295
}

/** 반려견의 완료 회차를 오래된 순으로 */
function doneAsc(dogId: string): MockSession[] {
  return sessions.filter((s) => s.dog_id === dogId && s.status === 'DONE').sort((a, b) => a.measured_on.localeCompare(b.measured_on))
}

/** 한 회차·수치·다리의 값. 관심 다리는 조금 낮고, 회차가 쌓일수록 좌우 차이가 줄어든다. */
function metricValue(s: MockSession, code: string, limb: MetricLimb, gait: GaitType): number | null {
  const def = DEFS.find((d) => d.code === code)!
  const dog = findDog(s.dog_id)
  // 발 높이 LF 는 신뢰도 낮음으로 측정 불가 (측정 불가 표시 확인용)
  if (code === 'paw_lift' && limb === 'LF') return null
  const idx = doneAsc(s.dog_id).findIndex((x) => x.id === s.id)
  const n = Math.max(1, doneAsc(s.dog_id).length)
  const noise = (hash(`${s.id}:${code}:${limb}`) - 0.5) * def.spread
  const gaitF = gait === 'WALK' ? 0.86 : 1
  let v = def.base * gaitF + noise
  if (def.unit === 'pct_body' && dog) v *= dog.size_class === 'SMALL' ? 1.12 : dog.size_class === 'LARGE' ? 0.95 : 1
  // 관심 다리는 기준 회차에서 가장 낮고 최근 회차로 갈수록 회복
  if (dog?.focus_limb && limb === dog.focus_limb && def.unit !== 'pct') {
    const gap = def.spread * 1.2 * (1 - idx / n)
    v -= gap
  }
  if (code === 'gait_cycles') return Math.round(v)
  return Math.round(v * 10) / 10
}

function pairOf(limb: MetricLimb): Pair | null {
  if (limb === 'LF' || limb === 'RF') return 'FORE'
  if (limb === 'LH' || limb === 'RH') return 'HIND'
  return null
}

const LOW_CONF: Reason = reason('LOW_CONFIDENCE')
const ONE_SIDE: Reason = reason('ONE_SIDE_ONLY')

export function resultFor(s: MockSession): SessionResultOut {
  const vp = validPasses(s)
  const used = vp.LEFT + vp.RIGHT
  const measured = used + Math.max(2, Math.round(used * 0.4))
  const gaits: GaitType[] = s.id.endsWith('5') || s.id.endsWith('2') ? ['WALK', 'TROT'] : ['TROT']
  const nPass = (limb: MetricLimb) => (limb === 'LF' || limb === 'LH' ? vp.LEFT : limb === 'RF' || limb === 'RH' ? vp.RIGHT : used)
  return {
    ...toSessionOut(s),
    pass_counts: { measured, used, excluded: measured - used },
    shot_counts: { total: Math.max(s.shots.length, Math.round(measured / 1.3)), failed: s.id.endsWith('7') ? 1 : 0, invalid: Math.round((measured - used) / 3) },
    exclude_summary: [
      { ...reason('RUNNING'), count: Math.ceil((measured - used) / 2) },
      { ...reason('STOPPED'), count: Math.floor((measured - used) / 2) },
    ].filter((x) => x.count > 0),
    notices: vp.LEFT === 0 || vp.RIGHT === 0 ? [ONE_SIDE] : [],
    gaits: gaits.map((gait) => {
      const metrics: MetricOut[] = []
      for (const def of DEFS)
        for (const limb of def.limbs) {
          const n = nPass(limb)
          const v = n === 0 ? null : metricValue(s, def.code, limb, gait)
          metrics.push({
            metric_code: def.code,
            limb,
            value: v,
            unit: def.unit,
            measurable: v != null,
            unmeasurable_reason: v == null ? (n === 0 ? reason('NO_PASS_FOR_LIMB') : LOW_CONF) : null,
            n_passes: n,
          })
        }
      const limb_compare: LimbCompareOut[] = []
      for (const def of DEFS) {
        for (const pair of ['FORE', 'HIND'] as Pair[]) {
          const [L, R] = pair === 'FORE' ? (['LF', 'RF'] as const) : (['LH', 'RH'] as const)
          if (!def.limbs.includes(L)) continue
          const l = metrics.find((m) => m.metric_code === def.code && m.limb === L)!
          const r = metrics.find((m) => m.metric_code === def.code && m.limb === R)!
          const comparable = l.value != null && r.value != null
          const diff = comparable ? Math.round((l.value! - r.value!) * 10) / 10 : null
          const mean = comparable ? (l.value! + r.value!) / 2 : 0
          limb_compare.push({
            pair,
            metric_code: def.code,
            unit: def.unit,
            left: l.value,
            right: r.value,
            diff,
            symmetry_index: comparable && mean !== 0 ? Math.round((Math.abs(diff!) / mean) * 10000) / 100 : null,
            comparable,
            reason: comparable ? null : (l.unmeasurable_reason ?? r.unmeasurable_reason),
          })
        }
      }
      limb_compare.sort((a, b) => {
        if (a.comparable !== b.comparable) return a.comparable ? -1 : 1
        if (a.symmetry_index == null && b.symmetry_index == null) return 0
        if (a.symmetry_index == null) return 1
        if (b.symmetry_index == null) return -1
        return b.symmetry_index - a.symmetry_index
      })
      return { gait_type: gait, metrics, limb_compare }
    }),
  }
}

/* ---------- 비교 ---------- */

export function compareFor(dogId: string, p: { target?: string; base?: string; gait_type?: GaitType }): CompareOut | { error: string; reason: string } {
  const dog = findDog(dogId)!
  const done = doneAsc(dogId)
  if (!done.length) return { error: 'COMPARE_INVALID', reason: 'NO_DONE_SESSION' }
  const target = p.target ? done.find((s) => s.id === p.target) : done[done.length - 1]
  if (!target) {
    const any = sessions.find((s) => s.id === p.target)
    return { error: any ? 'COMPARE_INVALID' : 'NOT_FOUND', reason: any ? 'NOT_DONE' : '' }
  }
  const baselineId = dog.baseline_session_id ?? done[0].id
  let base: MockSession | undefined
  let kind: CompareOut['base']['kind'] = 'BASELINE'
  const mode = p.base ?? 'BASELINE'
  if (mode === 'BASELINE') base = done.find((s) => s.id === baselineId)
  else if (mode === 'PREVIOUS') {
    const i = done.findIndex((s) => s.id === target.id)
    if (i <= 0) return { error: 'COMPARE_INVALID', reason: 'NO_PREVIOUS' }
    base = done[i - 1]
    kind = 'PREVIOUS'
  } else {
    base = done.find((s) => s.id === mode)
    kind = 'SESSION'
    if (!base) return { error: 'COMPARE_INVALID', reason: 'NOT_DONE' }
  }
  if (!base || base.id === target.id) return { error: 'COMPARE_INVALID', reason: 'SAME_SESSION' }

  const gaits: GaitType[] = p.gait_type ? [p.gait_type] : ['TROT']
  const modelChanged = base.model_version !== target.model_version
  const items: CompareItem[] = []
  for (const gait of gaits)
    for (const def of DEFS)
      for (const limb of def.limbs) {
        const b = metricValue(base, def.code, limb, gait)
        const t = metricValue(target, def.code, limb, gait)
        const comparable = b != null && t != null
        let judgement: Judgement = 'UNKNOWN'
        let note: Reason | null = { code: 'RANGE_NOT_SET', message: '변화 판단 기준이 아직 정해지지 않았습니다.' }
        if (!comparable) {
          judgement = 'NOT_COMPARABLE'
          note = b == null && t == null ? { code: 'NO_DATA', message: '이 회차에는 이 수치가 없습니다.' } : LOW_CONF
        } else if (modelChanged) {
          note = { code: 'MODEL_CHANGED', message: '두 회차의 분석 방식이 달라 변화를 판단하지 않았습니다.' }
        }
        items.push({ metric_code: def.code, limb, gait_type: gait, unit: def.unit, base_value: b, target_value: t, diff: comparable ? Math.round((t! - b!) * 10) / 10 : null, judgement, note })
      }
  // 정렬: 보행 유형, 관심 다리 먼저, LF·RF·LH·RH·NONE, 수치 순서
  const order: MetricLimb[] = ['LF', 'RF', 'LH', 'RH', 'NONE']
  const rank = (l: MetricLimb) => (dog.focus_limb && l === dog.focus_limb ? -1 : order.indexOf(l))
  items.sort((a, b) => a.gait_type.localeCompare(b.gait_type) || rank(a.limb) - rank(b.limb) || DEFS.findIndex((d) => d.code === a.metric_code) - DEFS.findIndex((d) => d.code === b.metric_code))
  return {
    dog_id: dogId,
    base: { session_id: base.id, measured_on: base.measured_on, model_version: base.model_version, kind },
    target: { session_id: target.id, measured_on: target.measured_on, model_version: target.model_version },
    model_changed: modelChanged,
    items,
  }
}

/* ---------- 추이 ---------- */

export function trendsFor(dogId: string, code: string, gait: GaitType, limb?: string): TrendsOut {
  const dog = findDog(dogId)!
  const def = DEFS.find((d) => d.code === code) ?? DEFS[0]
  const done = doneAsc(dogId)
  const limbs = def.limbs.filter((l) => !limb || l === limb)
  const order: MetricLimb[] = ['LF', 'RF', 'LH', 'RH', 'NONE']
  limbs.sort((a, b) => (dog.focus_limb && a === dog.focus_limb ? -1 : order.indexOf(a)) - (dog.focus_limb && b === dog.focus_limb ? -1 : order.indexOf(b)))
  const series = limbs.map((l) => ({
    limb: l,
    points: done.map((s) => {
      const v = metricValue(s, def.code, l, gait)
      return { session_id: s.id, measured_on: s.measured_on, value: v, measurable: v != null, unmeasurable_reason: v == null ? LOW_CONF : null, model_version: s.model_version }
    }),
  }))
  const lr_diff = (['FORE', 'HIND'] as Pair[])
    .filter((pair) => def.limbs.some((l) => pairOf(l) === pair))
    .map((pair) => {
      const [L, R] = pair === 'FORE' ? (['LF', 'RF'] as const) : (['LH', 'RH'] as const)
      return {
        pair,
        points: done
          .map((s) => {
            const l = metricValue(s, def.code, L, gait)
            const r = metricValue(s, def.code, R, gait)
            if (l == null || r == null) return null
            const diff = Math.round((l - r) * 10) / 10
            const mean = (l + r) / 2
            return { session_id: s.id, measured_on: s.measured_on, diff, symmetry_index: mean ? Math.round((Math.abs(diff) / mean) * 10000) / 100 : null }
          })
          .filter((x): x is NonNullable<typeof x> => x != null),
      }
    })
  return { dog_id: dogId, metric_code: def.code, unit: def.unit, gait_type: gait, series, lr_diff }
}

/* ---------- 촬영 상세·각도 ---------- */

export function shotDetailFor(shot: MockShot, s: MockSession, origin: string): ShotDetailOut {
  const { session_id: _sid, ...base } = shot
  const ready = shot.video_status === 'READY'
  const exp = new Date(Date.now() + 5 * 60_000).toISOString()
  return {
    ...base,
    width: 1920,
    height: 1080,
    fps: 59.94,
    duration_sec: 4.2,
    bitrate_kbps: shot.below_min_spec ? 2800 : 15800,
    codec: 'h264',
    model_name: shot.status === 'DONE' ? 'pga-pose' : null,
    model_version: shot.status === 'DONE' ? (s.model_version ?? 'v1') : null,
    submitted_at: shot.status === 'UPLOADED' ? null : shot.uploaded_at,
    video_ready_at: ready ? (shot.analyzed_at ?? shot.uploaded_at) : null,
    // 가짜 서버는 PDF·영상 파일을 못 만든다. 공개 폴더의 견본 영상 주소(절대 주소, api-spec 1.6 "http 로 시작하면 그대로")를 준다
    video_url: ready ? `${origin}/test_walk.mp4` : null,
    url_expires_at: ready ? exp : null,
  }
}

export function anglesFor(shot: MockShot): AnglesOut {
  const fps = 59.94
  const passes = shot.passes
    .filter((p) => p.is_valid)
    .map((p) => {
      const n = p.end_frame - p.start_frame
      const curve = (base: number, amp: number, phase: number) =>
        Array.from({ length: n }, (_, i) => {
          if (i % 37 === 19) return null // 관절점을 못 찾은 프레임
          const t = (i / n) * Math.PI * 2 * 3 + phase + hash(`${shot.id}:${p.pass_no}`) * 2
          return Math.round((base + amp * Math.sin(t) + amp * 0.3 * Math.sin(t * 2.1)) * 10) / 10
        })
      return {
        pass_no: p.pass_no,
        camera_side: p.camera_side,
        gait_type: p.gait_type,
        start_frame: p.start_frame,
        angles: {
          shoulder: curve(112, 14, 0),
          elbow: curve(120, 22, 0.6),
          carpus: curve(150, 26, 1.1),
          hip: curve(108, 12, 0.3),
          stifle: curve(122, 18, 0.9),
          tarsus: curve(135, 20, 1.4),
        },
      }
    })
  return { shot_id: shot.id, fps, passes }
}

export { dogs as _dogs }
