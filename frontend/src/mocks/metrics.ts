/**
 * 가짜 서버의 회차 수치·비교·추이·촬영 상세. 수치·관절각은 시연 회차(demoSessions.json + companySample.json)에서 가져온다.
 * 수치 코드와 단위는 api-spec 10.4, 응답 모양은 7·8절.
 */
import type { AnglesOut, CompareItem, CompareOut, GaitType, Judgement, LimbCompareOut, MetricLimb, MetricOut, Pair, Reason, SessionResultOut, ShotDetailOut, TrendsOut, Unit } from '../api/types'
import { dogs, findDog, reason, sessions, toSessionOut, validPasses, type MockSession, type MockShot } from './db'
import demo from './demoSessions.json'

/**
 * 시연 회차: AI-Hub 71878 라벨 관절점으로 잰 관절각·가동 범위 + 합성 값(demoSessions.json, prototype/tools/build_demo_sessions.py).
 * 회사 데이터(제니) 1회차는 companySample.json 에 따로 둔다. 시연에 써도 되는지 멘토링에서 확인하기 전까지만 두고,
 * 그 파일을 지우면 아래 glob 이 빈 결과라 자동으로 빠진다(코드 수정 필요 없음).
 * 가짜 회차마다 시연 회차 하나를 차례로 붙여 수치·관절각을 그대로 쓴다(반려견·날짜는 가짜 DB 값).
 */
type RealSession = { id: string; source: string; cycles: number; walk_speed: number | null; fps: number
  metrics: Record<string, Record<string, number>>; angle_series: Record<string, Record<string, (number | null)[] | string>> }
const company = Object.values(import.meta.glob('./companySample.json', { eager: true, import: 'default' })) as { sessions: RealSession[] }[]
const REAL: RealSession[] = [...(demo as { sessions: RealSession[] }).sessions, ...company.flatMap((c) => c.sessions)]

/** 완료 회차 전체를 날짜순으로 세워 실측 회차를 돌려 가며 붙인다 */
function realOf(s: MockSession): RealSession {
  const all = sessions.filter((x) => x.status === 'DONE').sort((a, b) => a.measured_on.localeCompare(b.measured_on) || a.id.localeCompare(b.id))
  const i = Math.max(0, all.findIndex((x) => x.id === s.id))
  return REAL[i % REAL.length]
}

/** 수치 정의: 코드, 단위, 다리 (값은 실측 회차에서) */
const DEFS: { code: string; unit: Unit; limbs: MetricLimb[] }[] = [
  { code: 'rom_stifle', unit: 'deg', limbs: ['LH', 'RH'] },
  { code: 'rom_hip', unit: 'deg', limbs: ['LH', 'RH'] },
  { code: 'rom_tarsus', unit: 'deg', limbs: ['LH', 'RH'] },
  { code: 'rom_shoulder', unit: 'deg', limbs: ['LF', 'RF'] },
  { code: 'rom_elbow', unit: 'deg', limbs: ['LF', 'RF'] },
  { code: 'rom_carpus', unit: 'deg', limbs: ['LF', 'RF'] },
  { code: 'stride_length', unit: 'pct_body', limbs: ['LF', 'RF', 'LH', 'RH'] },
  { code: 'stance_ratio', unit: 'pct', limbs: ['LF', 'RF', 'LH', 'RH'] },
  { code: 'paw_lift', unit: 'pct_body', limbs: ['LF', 'RF', 'LH', 'RH'] },
  { code: 'walk_speed', unit: 'body_per_sec', limbs: ['NONE'] },
  { code: 'gait_cycles', unit: 'count', limbs: ['NONE'] },
]


/** 반려견의 완료 회차를 오래된 순으로 */
function doneAsc(dogId: string): MockSession[] {
  return sessions.filter((s) => s.dog_id === dogId && s.status === 'DONE').sort((a, b) => a.measured_on.localeCompare(b.measured_on))
}

/** 한 회차·수치·다리의 실측값. 그 다리를 잴 수 없었으면 null. 평보·속보 구분은 실측에 없어 같은 값 */
function metricValue(s: MockSession, code: string, limb: MetricLimb, _gait: GaitType): number | null {
  const r = realOf(s)
  if (code === 'walk_speed') return r.walk_speed
  if (code === 'gait_cycles') return r.cycles
  const v = r.metrics[limb]?.[code]
  return v == null ? null : Math.round(v * 10) / 10
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
  const gaits: GaitType[] = ['TROT']   // 실측 영상에 보행 종류 판별이 아직 없다
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

/** 촬영 상세의 프레임별 관절각: 같은 방향 실측 통과의 관절각을 그대로 (프레임 수는 실측 통과 길이) */
export function anglesFor(shot: MockShot): AnglesOut {
  const owner = sessions.find((x) => x.shots.some((y) => y.id === shot.id))
  const r = owner ? realOf(owner) : REAL[0]
  const passes = shot.passes
    .filter((p) => p.is_valid)
    .map((p) => {
      const a = r.angle_series[p.camera_side === 'LEFT' ? 'L' : 'R'] ?? Object.values(r.angle_series)[0]
      const pick = (k: string) => (Array.isArray(a?.[k]) ? (a[k] as (number | null)[]) : [])
      return {
        pass_no: p.pass_no,
        camera_side: p.camera_side,
        gait_type: p.gait_type,
        start_frame: p.start_frame,
        angles: { shoulder: pick('shoulder'), elbow: pick('elbow'), carpus: pick('carpus'), hip: pick('hip'), stifle: pick('stifle'), tarsus: pick('tarsus') },
      }
    })
  return { shot_id: shot.id, fps: r.fps, passes }
}

export { dogs as _dogs }
