// 화면 바로가기 (디자인 검토용, VITE_JUMPS=1 일 때만): 이름, 주소, 로그인 필요 여부. main.py 의 JUMPS 와 같다
export const JUMPS: [string, string, boolean][] = [
  ['랜딩', '/', false], ['서비스 소개 (로그인 전)', '/about', false], ['로그인', '/login', false],
  ['회원가입 (디바이스 코드)', '/signup', false], ['비밀번호 찾기', '/forgot', false], ['계약 만료 안내', '/expired?demo=1', false],
  ['크림오프 관리', '/admin?demo=1', false], ['홈, 반려견, 측정 이력', '/home', true], ['반려견 등록', '/home?modal=pet', true],
  ['영상 업로드', '/upload', true], ['업로드, 영상 첨부 중', '/upload?demo=7', true], ['분석 중', '/analyzing/demo', true],
  ['분석 결과', '/results', true], ['회차 결과', '/results/r1', true], ['회차 결과, 일부 유효', '/results/r2', true],
  ['회차 결과, 실패', '/results/r3', true], ['보고서', '/results/r1/report', true], ['경과 비교', '/compare/d1', true],
  ['서비스 소개', '/about', true], ['마이페이지', '/my', true], ['기본 정보', '/account', true],
]
