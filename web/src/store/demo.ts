// 데모 기관(seed.py 의 DEMO_*). 둘러보기·화면 바로가기는 데모 기관을 처음 상태로 되돌리고 그 담당자로 들어간다.
import { db, freshAccount } from './db'

export const DEMO_ID = 'demo'
export const DEMO_STAFF = 's_demo' // 데모 기관 담당자
export const DEMO_CODE = 'HNB7KQW9PAX2M8NH4CDE'
export const FULL_CODE = 'FUZZ2QW9PAX2M8NH4CDE' // 계정 상한이 찬 코드
export const EXPIRED_CODE = 'EXPR3QW9PAX2M8NH4CDE' // 계약이 끝난 기관의 코드
export const STAFF = ['이서연 원장', '최지우 수의사', '한도윤 수의사', '박민준 테크니션', '정하늘 테크니션']

/** seed.demo_account(): 데모 기관을 시연 데이터 처음 상태로 */
export function resetDemo(): void {
  db.accounts[DEMO_ID] = freshAccount(DEMO_ID)
}
