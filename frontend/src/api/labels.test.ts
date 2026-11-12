import { describe, expect, it } from 'vitest'

import {
  CAMERA_SIDE_LABEL, GAIT_LABEL, JOINT_LABEL, JUDGEMENT_LABEL, LIMB_LABEL, METRIC_LABEL, REPORT_STATUS_LABEL, SESSION_STATUS_LABEL,
  SEX_LABEL, SHOT_STATUS_LABEL, SIZE_LABEL, VALIDITY_LABEL, dogDesc, fmtDate, fmtMetric, fmtMonthDay, metricLabel, pairOf,
  previewSizeClass,
} from './labels'

// api-spec 10절 값 목록. 서버 값이 늘면 여기와 labels.ts 를 같이 고친다
const ENUMS: [string, Record<string, string>, string[]][] = [
  ['sex', SEX_LABEL, ['MALE', 'FEMALE', 'MALE_NEUTERED', 'FEMALE_SPAYED']],
  ['size_class', SIZE_LABEL, ['SMALL', 'MEDIUM', 'LARGE']],
  ['limb', LIMB_LABEL, ['LF', 'RF', 'LH', 'RH']],
  ['gait_type', GAIT_LABEL, ['WALK', 'TROT', 'PACE', 'OTHER']],
  ['validity', VALIDITY_LABEL, ['VALID', 'PARTIAL', 'INVALID']],
  ['session status', SESSION_STATUS_LABEL, ['MEASURING', 'AGGREGATING', 'DONE', 'FAILED']],
  ['shot status', SHOT_STATUS_LABEL, ['UPLOADED', 'SUBMITTED', 'ANALYZING', 'DONE', 'FAILED']],
  ['report status', REPORT_STATUS_LABEL, ['PENDING', 'GENERATING', 'DONE', 'FAILED']],
  ['camera_side', CAMERA_SIDE_LABEL, ['LEFT', 'RIGHT']],
  ['judgement', JUDGEMENT_LABEL, ['INCREASE', 'DECREASE', 'WITHIN_RANGE', 'UNKNOWN', 'NOT_COMPARABLE']],
  ['joint', JOINT_LABEL, ['shoulder', 'elbow', 'carpus', 'hip', 'stifle', 'tarsus']],
]
// api-spec 10.4 수치 코드
const METRIC_CODES = ['rom_shoulder', 'rom_elbow', 'rom_carpus', 'rom_hip', 'rom_stifle', 'rom_tarsus', 'stifle_cv', 'paw_lift',
  'paw_excursion', 'stride_length', 'stance_ratio', 'walk_speed', 'gait_cycles']

describe('값 한글화', () => {
  it.each(ENUMS)('%s 의 모든 값에 한글 문구가 있다', (_, dict, values) => {
    expect(Object.keys(dict).sort()).toEqual([...values].sort())
    for (const v of values) expect(dict[v]).toMatch(/[가-힣]/)
  })

  it('수치 코드(10.4)를 모두 한글로 보여 준다', () => {
    for (const c of METRIC_CODES) {
      expect(METRIC_LABEL[c]).toBeTruthy()
      expect(metricLabel(c)).toMatch(/[가-힣]/)
    }
  })

  it('관절 각도 중앙값 코드는 관절 이름을 붙이고, 모르는 코드는 그대로 둔다', () => {
    expect(metricLabel('angle_median_stifle')).toBe('무릎 각도 중앙값')
    expect(metricLabel('new_metric')).toBe('new_metric')
  })

  it('진단성 표현을 쓰지 않는다(screenPlan 5절 금지 표현)', () => {
    const all = [...ENUMS.flatMap(([, d]) => Object.values(d)), ...Object.values(METRIC_LABEL)].join(' ')
    for (const w of ['아프', '좋아졌', '나빠졌', '진단', '질환', '통증']) expect(all).not.toContain(w)
  })
})

describe('숫자 자릿수 (screenPlan 5절)', () => {
  it('각도는 소수 1자리', () => {
    expect(fmtMetric(42.26, 'deg')).toBe('42.3°')
    expect(fmtMetric(40, 'deg')).toBe('40.0°')
  })

  it('비율은 정수', () => {
    expect(fmtMetric(61.6, 'pct')).toBe('62%')
    expect(fmtMetric(38.2, 'pct_body')).toBe('38%')
  })

  it('횟수는 정수, 그 밖은 소수 1자리', () => {
    expect(fmtMetric(12, 'count')).toBe('12회')
    expect(fmtMetric(1.437, 'body_per_sec')).toBe('1.4등 길이/초')
  })

  it('측정 불가(null·NaN)는 0 이 아니라 — 로 보여 준다', () => {
    for (const v of [null, undefined, Number.NaN]) {
      expect(fmtMetric(v, 'deg')).toBe('—')
      expect(fmtMetric(v, 'pct')).toBe('—')
    }
    expect(fmtMetric(0, 'deg')).toBe('0.0°')   // 실제로 잰 0 은 그대로
  })
})

describe('날짜·설명·체급', () => {
  it('날짜는 한국어로', () => {
    expect(fmtDate('2026-10-20')).toBe('2026년 10월 20일')
    expect(fmtMonthDay('2026-10-05')).toBe('10월 5일')
    expect(fmtDate(null)).toBe('')
  })

  it('반려견 한 줄 설명은 빈 값을 빼고 잇는다', () => {
    expect(dogDesc({ breed: '말티즈', birth_year: 2020, weight_kg: 3.2 })).toBe('말티즈 · 2020년생 · 3.2kg')
    expect(dogDesc({ breed: '', birth_year: null, weight_kg: 0 })).toBe('견종 미입력')
  })

  it('체급 미리보기 경계는 서버와 같다(10kg 미만 소형, 25kg 미만 중형)', () => {
    expect(previewSizeClass(9.9)).toBe('SMALL')
    expect(previewSizeClass(10)).toBe('MEDIUM')
    expect(previewSizeClass(24.9)).toBe('MEDIUM')
    expect(previewSizeClass(25)).toBe('LARGE')
    expect(previewSizeClass(0)).toBeNull()
    expect(previewSizeClass(null)).toBeNull()
  })

  it('다리 묶음', () => {
    expect(pairOf('LF')).toBe('FORE')
    expect(pairOf('RH')).toBe('HIND')
    expect(pairOf('NONE')).toBeNull()
  })
})
