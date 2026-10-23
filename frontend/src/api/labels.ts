/** API 값 → 화면 문구. api-spec 10절. 한 곳에서만 바꾼다. */
import type { Limb, ReportStatus, SessionStatus, Sex, SizeClass } from './types'

export const SEX_LABEL: Record<Sex, string> = {
  MALE: '수컷',
  FEMALE: '암컷',
  MALE_NEUTERED: '중성화 수컷',
  FEMALE_SPAYED: '중성화 암컷',
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
