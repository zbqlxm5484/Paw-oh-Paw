// 설정값과 고정 목록. prototype/proto_app/config.py 를 그대로 옮겼다(값을 바꾸면 두 곳을 같이 바꾼다).

// 배포 경로 접두어(/web). 개발 서버에서는 ''. 라우터 basename·정적 파일 주소·현재 주소 계산에 쓴다
export const BASE = import.meta.env.BASE_URL.replace(/\/$/, '')
/** 접두어를 뺀 현재 화면 주소. window.location.pathname 을 navigate() 에 그대로 넘기면 접두어가 두 번 붙는다 */
export const herePath = (): string => {
  const p = window.location.pathname
  return (BASE && p.startsWith(BASE) ? p.slice(BASE.length) : p) || '/'
}

export const MAX_SHOTS = 16 // 한 회차 영상 수 (4초씩 16개)
export const ANALYSIS_SEC = 7.0 // 분석 시뮬레이션 시간(가짜 서버 모드)
export const MODEL = 'v1'

// 회차 상태: 라벨, 배경색, 글자색
export const ST: Record<string, [string, string, string]> = {
  ok: ['유효', '#E8F3EC', '#2E8B57'],
  part: ['일부 유효', '#FAF1DF', '#9A6A12'],
  fail: ['실패', '#F8E7E3', '#C2412D'],
}
export const STEPS = ['업로드 완료', '반려견 찾는 중', '관절점 찾는 중', '보행 수치 계산 중', '보고서 만드는 중']

export const SEX: Record<string, string> = { m: '수컷', f: '암컷', mn: '수컷(중성화)', fs: '암컷(중성화)' }
export const SIZE: Record<string, string> = { S: '소형', M: '중형', L: '대형' }
export const LIMB: Record<string, string> = { LF: '왼앞', RF: '오른앞', LH: '왼뒤', RH: '오른뒤' }
export const SITE: Record<string, string> = { ...LIMB, SP: '척추' } // 수술·진단 부위

export const STAGE: Record<string, [string, string, string]> = {
  pre: ['수술 전', '#EEF1F6', '#4A5A78'],
  rehab: ['재활 중', '#FCEEE3', '#A8481A'],
  done: ['종결', '#F0EEEA', '#7A808A'],
}
export const STAGE_NAMES: Record<string, string> = Object.fromEntries(Object.entries(STAGE).map(([k, v]) => [k, v[0]]))
// 메모 = 환자에 붙는 짧은 특이사항. 진료 기록 = 방문 하나의 S·O·A·P
export const MEMO_CAT: Record<string, [string, string]> = {
  주의: ['#FBE0D9', '#C2412D'],
  보호자: ['#E7EEFB', '#3B5BA9'],
  예약: ['#E3F1E7', '#2E7A4F'],
  기타: ['#F1ECE5', '#5B6472'],
}
export const NOTE_CAT = ['S', 'O', 'A', 'P', ...Object.keys(MEMO_CAT)]
export const SOAP: Record<string, [string, string]> = {
  S: ['주관', '보호자 말 · 증상'],
  O: ['객관', '검사 · 관찰'],
  A: ['평가', '판단 · 진단'],
  P: ['계획', '처치 · 다음 방문'],
}
// 바이탈 참고 범위(일반 성견). 혈압은 수축기 기준(ACVIM 2018: 140~159 경계, 160 이상 높음)
export const VITAL_REF = {
  temp: [37.8, 39.2] as [number, number],
  hr: { S: [80, 160], M: [70, 140], L: [60, 120] } as Record<string, [number, number]>,
  sbp: [90, 140, 160] as [number, number, number],
}
export const WEIGHT_CHANGE = 5
export const IMG_KIND: Record<string, string> = { pre: '수술 전 방사선', post: '수술 후 방사선', xray: '방사선', photo: '사진' }
export const CHANGE_DAYS = 7
export const SYM_CHANGE = 3
export const PAGE_SIZE = 30
export const SHOW_JUMPS = import.meta.env.VITE_JUMPS === '1'

export const BREEDS = ['말티즈', '푸들', '토이 푸들', '포메라니안', '시츄', '치와와', '비숑 프리제', '요크셔테리어', '닥스훈트',
  '미니어처 슈나우저', '웰시코기', '비글', '시바견', '진돗개', '풍산개', '골든 리트리버', '래브라도 리트리버',
  '보더콜리', '프렌치 불독', '퍼그', '사모예드', '시베리안 허스키', '저먼 셰퍼드', '스피츠',
  '이탈리안 그레이하운드', '잭 러셀 테리어', '말라뮤트', '믹스견']
export const SMALL_BREEDS = ['말티즈', '푸들', '토이 푸들', '포메라니안', '시츄', '치와와', '비숑 프리제', '요크셔테리어', '닥스훈트',
  '미니어처 슈나우저', '퍼그', '이탈리안 그레이하운드', '잭 러셀 테리어']
export const LARGE_BREEDS = ['골든 리트리버', '래브라도 리트리버', '사모예드', '시베리안 허스키', '저먼 셰퍼드', '말라뮤트', '풍산개']

/** 견종으로 먼저, 모르는 견종이면 체중(10 kg, 25 kg)으로 체급을 정한다. */
export function auto_size(breed: string, kg: unknown): string {
  if (SMALL_BREEDS.includes(breed)) return 'S'
  if (LARGE_BREEDS.includes(breed)) return 'L'
  if (BREEDS.includes(breed) && breed !== '믹스견') return 'M'
  const w = Number(kg)
  if (kg === '' || kg == null || Number.isNaN(w) || !w) return 'M'
  return w < 10 ? 'S' : w < 25 ? 'M' : 'L'
}
