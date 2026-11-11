// 앱 보호자용 보고서의 '다음 방문까지 할 일'과 '이럴 때는 병원에 연락하세요'(QA 2절 3-4).
// 문장은 웹 보고서(web/src/views/views.ts owner_guide, web/src/views/ownerSummary.ts CONTACT)와 같다.
// 진단·통증·좋아짐/나빠짐 단정 없이 집에서 보이는 모습만 적는다(백엔드 terms.yaml forbidden).

export const CONTACT: string[] = [
  '평소와 다르게 한쪽 다리를 들고 걷거나, 디디지 않으려고 할 때',
  '산책이나 계단을 평소보다 피하거나, 금방 멈추려고 할 때',
  '다리를 만지면 싫어하거나, 붓거나 따뜻하게 느껴질 때',
  '며칠 사이에 걷는 모습이 눈에 띄게 달라졌을 때',
]

export interface PartLite { si: number; weak: 'l' | 'r' }

/** 덜 쓰는 쪽(좌우 차이 5% 이상인 다리 쌍 중 큰 쪽)에 맞춘 할 일·지켜볼 것. 웹 owner_guide 와 같은 문장 */
export function ownerTodo(front: PartLite, hind: PartLite): { todo: string[]; watch: string[] } {
  const part = hind.si >= front.si ? 'hind' : 'front'
  const p = part === 'hind' ? hind : front
  if (p.si < 5) return { todo: ['지금처럼 꾸준히 산책해 주세요', '미끄러운 바닥에는 매트를 깔아 주세요'], watch: [] }
  const side = p.weak === 'l' ? '왼쪽' : '오른쪽'
  const other = side === '왼쪽' ? '오른쪽' : '왼쪽'
  if (part === 'hind')
    return {
      todo: ['미끄러운 바닥에는 매트를 깔아 주세요', '계단·점프는 담당 수의사가 괜찮다고 할 때까지 줄여 주세요', '산책은 평지에서 짧게, 자주 하는 것이 좋아요',
        `양쪽 허벅지 굵기를 가끔 손으로 만져 비교해 보세요. ${side}이 가늘어지면 다음 진료 때 알려 주세요`],
      watch: [`${side} 뒷다리를 디딜 때 엉덩이가 들썩이거나, 몸이 ${other}으로 기울어 보일 수 있어요`, `앉을 때 ${side} 뒷다리를 옆으로 빼고 앉을 수 있어요`,
        '계단을 오르거나 소파·차에 뛰어오를 때 머뭇거릴 수 있어요'],
    }
  return {
    todo: ['미끄러운 바닥에는 매트를 깔아 주세요', '계단 내려가기·높은 곳에서 뛰어내리기는 담당 수의사가 괜찮다고 할 때까지 줄여 주세요', '산책은 평지에서 짧게, 자주 하는 것이 좋아요'],
    watch: [`${side} 앞다리를 디딜 때 고개가 위로 들리며 끄덕이듯 걸을 수 있어요`, `서 있을 때 ${side} 앞발을 살짝 들거나 짧게 디딜 수 있어요`,
      '계단을 내려가거나 높은 곳에서 뛰어내릴 때 머뭇거릴 수 있어요'],
  }
}

const BOX = { borderRadius: '12px', padding: '12px 14px', display: 'flex', flexDirection: 'column' as const, gap: '6px' }

export function AppOwnerSummary({ front, hind }: { front: PartLite; hind: PartLite }) {
  const { todo, watch } = ownerTodo(front, hind)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <b style={{ fontSize: '15px' }}>보호자가 알아 두면 좋은 점</b>
      <div style={{ ...BOX, border: '1px solid #ECE8E2' }}>
        <b style={{ fontSize: '13.5px', color: '#3A4250' }}>다음 방문까지 할 일</b>
        {todo.map((x) => <span key={x} style={{ fontSize: '13px', lineHeight: 1.5, paddingLeft: '10px', borderLeft: '3px solid #CFE3D6' }}>{x}</span>)}
        {watch.length ? <b style={{ fontSize: '12.5px', color: '#5B6472', marginTop: '4px' }}>집에서 지켜봐 주세요</b> : null}
        {watch.map((x) => <span key={x} style={{ fontSize: '13px', lineHeight: 1.5, paddingLeft: '10px', borderLeft: '3px solid #F2C9AE' }}>{x}</span>)}
      </div>
      <div style={{ ...BOX, background: '#FCEEE3', border: '1px solid #F0D2BC', color: '#8A3F12', fontSize: '13px', lineHeight: 1.55 }}>
        <b>이럴 때는 병원에 연락하세요</b>
        {CONTACT.map((u) => <span key={u}>· {u}</span>)}
      </div>
      <span style={{ fontSize: '11px', color: '#8E949C' }}>일반적인 안내예요. 우리 아이에게 맞는 관리는 담당 수의사와 상의해 주세요.</span>
    </div>
  )
}
