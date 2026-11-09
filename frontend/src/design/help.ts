// 앱 도움말 화면 본문(촬영 가이드·자주 묻는 질문). 연락처·FAQ 는 legal/content.ts 와 같은 값을 쓴다
import { LEGAL, SUPPORT } from '../legal/content'

export interface HelpCard { h: string; items: string[] }

export const HELP_CARDS: HelpCard[] = [
  { h: '촬영 준비', items: [
    '반려견이 평소처럼 걷는 곳에서, 목줄을 느슨하게 잡고 보호자가 옆에서 같이 걷습니다.',
    '바닥이 미끄럽지 않고 밝은 곳이 좋습니다. 역광(창문·조명을 등진 방향)은 피해 주세요.',
    '옷·하네스는 벗기고, 다리가 다 보이게 해 주세요.',
  ] },
  { h: '촬영 방법', items: [
    '반려견의 옆모습이 보이도록 3~4m 떨어져 카메라를 가로로 들고 찍습니다.',
    '카메라는 움직이지 않고, 반려견이 화면을 가로질러 걷게 합니다. 한 번에 4초 정도면 충분합니다.',
    '왼쪽에서 오른쪽, 오른쪽에서 왼쪽으로 번갈아 찍으면 양쪽 다리가 고르게 잡힙니다.',
    '한 회차에 16개까지 올릴 수 있습니다. 8개 이상이면 결과가 안정됩니다.',
  ] },
  { h: '결과 보는 법', items: [
    '분석이 끝나면 홈과 알림에 표시됩니다. 회차를 열면 다리별 관절 가동 범위·입각기 비율·대칭 지수를 볼 수 있습니다.',
    '보고서는 보호자용과 수의사용 두 가지로 만들어지고 PDF 로 저장할 수 있습니다.',
    '같은 반려견을 여러 회차 찍으면 비교 화면에서 기준 회차 대비 변화를 봅니다.',
  ] },
  { h: '자주 묻는 질문', items: LEGAL.support.sections[1].p },
]

export const HELP_CONTACT = [
  { label: '이메일', value: SUPPORT.email, href: `mailto:${SUPPORT.email}` },
]
