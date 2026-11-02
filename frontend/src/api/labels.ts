/** API 값 → 화면 문구. api-spec 10절. 한 곳에서만 바꾼다. */
import type { CameraSide, Edition, GaitType, JointCode, Judgement, Limb, MetricLimb, Pair, ReportStatus, SessionStatus, Sex, ShotStatus, SizeClass, Unit, Validity } from './types'

export const SEX_LABEL: Record<Sex, string> = {
  MALE: '수컷',
  FEMALE: '암컷',
  MALE_NEUTERED: '수컷(중성화)',
  FEMALE_SPAYED: '암컷(중성화)',
}

export const SIZE_LABEL: Record<SizeClass, string> = {
  SMALL: '소형',
  MEDIUM: '중형',
  LARGE: '대형',
}

export const LIMB_LABEL: Record<Limb, string> = {
  LF: '왼앞',
  RF: '오른앞',
  LH: '왼뒤',
  RH: '오른뒤',
}

export const SESSION_STATUS_LABEL: Record<SessionStatus, string> = {
  MEASURING: '측정 중',
  AGGREGATING: '집계 중',
  DONE: '완료',
  FAILED: '실패',
}

export const REPORT_STATUS_LABEL: Record<ReportStatus, string> = {
  PENDING: '대기',
  GENERATING: '만드는 중',
  DONE: '완료',
  FAILED: '실패',
}

/** 상태 배지 색. tokens.css 의 ok/warn/bad 짝. */
export type Tone = 'ok' | 'warn' | 'bad' | 'neutral'
export const SESSION_STATUS_TONE: Record<SessionStatus, Tone> = {
  MEASURING: 'warn',
  AGGREGATING: 'warn',
  DONE: 'ok',
  FAILED: 'bad',
}

/** 체급 자동 분류 미리보기. 서버 규칙과 같다(등록 체중만, 10kg 미만 소형 · 25kg 미만 중형). 정본은 서버 응답의 size_class. */
export function previewSizeClass(weightKg: number | null | undefined): SizeClass | null {
  if (weightKg == null || !Number.isFinite(weightKg) || weightKg <= 0) return null
  if (weightKg < 10) return 'SMALL'
  if (weightKg < 25) return 'MEDIUM'
  return 'LARGE'
}

/** 견종 자동완성 목록. backend/config/breeds.yaml 과 같은 초안. 없는 견종은 입력한 이름으로 등록된다. */
export const BREEDS = [
  '말티즈', '푸들', '토이 푸들', '포메라니안', '치와와', '요크셔테리어', '시츄', '닥스훈트', '페키니즈', '파피용',
  '미니어처 핀셔', '비숑 프리제', '잭 러셀 테리어', '퍼그', '보스턴 테리어', '미니어처 슈나우저', '스피츠', '웰시코기',
  '비글', '시바견', '보더 콜리', '진돗개', '코커 스패니얼', '프렌치 불도그', '불도그', '삽살개', '골든 리트리버',
  '래브라도 리트리버', '저먼 셰퍼드', '사모예드', '시베리안 허스키', '알래스칸 말라뮤트', '도베르만', '로트와일러',
  '버니즈 마운틴 독', '그레이트 데인', '세인트 버나드', '달마시안', '아키타', '믹스견',
]

/** "2026-10-20" → "2026년 10월 20일" */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const [y, m, d] = iso.split('-')
  if (!y || !m || !d) return iso
  return `${y}년 ${Number(m)}월 ${Number(d)}일`
}

/** "2026-10-20" → "10월 20일" */
export function fmtMonthDay(iso: string | null | undefined): string {
  if (!iso) return ''
  const [, m, d] = iso.split('-')
  if (!m || !d) return iso
  return `${Number(m)}월 ${Number(d)}일`
}

/** 반려견 한 줄 설명: 견종 · N년생 · Nkg */
export function dogDesc(d: { breed: string; birth_year: number | null; weight_kg: number }): string {
  return [d.breed || '견종 미입력', d.birth_year ? `${d.birth_year}년생` : null, d.weight_kg ? `${d.weight_kg}kg` : null]
    .filter(Boolean)
    .join(' · ')
}

export const SHOT_STATUS_LABEL: Record<ShotStatus, string> = {
  UPLOADED: '분석 대기',
  SUBMITTED: '분석 요청',
  ANALYZING: '분석 중',
  DONE: '분석 완료',
  FAILED: '실패',
}
export const SHOT_STATUS_TONE: Record<ShotStatus, Tone> = {
  UPLOADED: 'neutral',
  SUBMITTED: 'warn',
  ANALYZING: 'warn',
  DONE: 'ok',
  FAILED: 'bad',
}

export const VALIDITY_LABEL: Record<Validity, string> = { VALID: '유효', PARTIAL: '일부 유효', INVALID: '무효' }
export const VALIDITY_TONE: Record<Validity, Tone> = { VALID: 'ok', PARTIAL: 'warn', INVALID: 'bad' }

export const CAMERA_SIDE_LABEL: Record<CameraSide, string> = { LEFT: '왼쪽', RIGHT: '오른쪽' }
export const GAIT_LABEL: Record<GaitType, string> = { WALK: '평보', TROT: '속보', PACE: '측대보', OTHER: '기타' }

/** 분석 중 촬영(SUBMITTED·ANALYZING)이 있으면 삭제·취소를 막는다(api-spec 10.2) */
export function isShotInProgress(status: ShotStatus): boolean {
  return status === 'SUBMITTED' || status === 'ANALYZING'
}

/* ---------- 회차 결과·비교 (api-spec 10.3, 10.4) ---------- */

export const METRIC_LABEL: Record<string, string> = {
  rom_shoulder: '어깨 가동 범위',
  rom_elbow: '팔꿈치 가동 범위',
  rom_carpus: '앞발목 가동 범위',
  rom_hip: '고관절 가동 범위',
  rom_stifle: '무릎 가동 범위',
  rom_tarsus: '뒷발목 가동 범위',
  stifle_cv: '무릎 움직임 일관성',
  paw_lift: '발 높이',
  paw_excursion: '발 움직임 범위',
  stride_length: '걸음 길이',
  stance_ratio: '입각기 비율',
  walk_speed: '보행 속도',
  gait_cycles: '보행 주기 수',
}
export function metricLabel(code: string): string {
  if (METRIC_LABEL[code]) return METRIC_LABEL[code]
  if (code.startsWith('angle_median_')) return `${JOINT_LABEL[code.slice(13) as JointCode] ?? code.slice(13)} 각도 중앙값`
  return code
}

export const JOINT_LABEL: Record<JointCode, string> = {
  shoulder: '어깨',
  elbow: '팔꿈치',
  carpus: '앞발목',
  hip: '고관절',
  stifle: '무릎',
  tarsus: '뒷발목',
}

export const UNIT_LABEL: Record<Unit, string> = { deg: '°', pct: '%', pct_body: '%', body_per_sec: '몸통/초', count: '회' }

export const PAIR_LABEL: Record<Pair, string> = { FORE: '앞다리', HIND: '뒷다리' }
export const EDITION_LABEL: Record<Edition, string> = { OWNER: '보호자용', VET: '수의사용' }

export const JUDGEMENT_LABEL: Record<Judgement, string> = {
  INCREASE: '증가',
  DECREASE: '감소',
  WITHIN_RANGE: '범위 안',
  UNKNOWN: '판단 보류',
  NOT_COMPARABLE: '비교 불가',
}

/** 수치 표시 자릿수(screenPlan 5절): 각도 1자리, 비율·횟수 정수, 그 밖 1자리. 측정 불가는 — */
export function fmtMetric(value: number | null | undefined, unit: Unit): string {
  if (value == null || !Number.isFinite(value)) return '—'
  const digits = unit === 'pct' || unit === 'pct_body' || unit === 'count' ? 0 : 1
  return `${value.toFixed(digits)}${UNIT_LABEL[unit]}`
}

/** 앞다리(LF·RF) / 뒷다리(LH·RH) 묶음 */
export function pairOf(limb: MetricLimb): Pair | null {
  if (limb === 'LF' || limb === 'RF') return 'FORE'
  if (limb === 'LH' || limb === 'RH') return 'HIND'
  return null
}

/** 서명 주소 처리(api-spec 1.6): /api/v1 로 시작하면 서버 주소를 붙이고, http 면 그대로 */
export function fileUrl(u: string | null | undefined): string | null {
  if (!u) return null
  if (u.startsWith('/api/v1')) return `${(import.meta.env.VITE_API_BASE as string | undefined) ?? ''}${u}`
  return u
}
