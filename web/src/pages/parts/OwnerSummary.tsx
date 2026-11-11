// 보호자용 요약 정리(QA 2절 3-4). 보고서 종이(ReportPaper)의 보호자용에만 쓴다.
// - OwnerChangeStrip: 몸 그림 아래, 기준 회차와 견줘 오차 범위를 넘게 달라진 관절이 있는 다리만 주황으로 표시
// - OwnerAdvice: '보호자가 알아 두면 좋은 점'을 '다음 방문까지 할 일'과 '이럴 때는 병원에 연락하세요'로 나눔
import { css } from '../../app/css'
import type { Account, Result } from '../../store/types'
import { legNote, LEG_NAME, ownerAdvice, ownerChange, type LegCode } from '../../views/ownerSummary'
import type { OwnerGuide } from '../../views/views'

const ORDER: LegCode[] = ['LF', 'RF', 'LH', 'RH']

export function OwnerChangeStrip({ acct, r, gait }: { acct: Account; r: Result; gait: string }) {
  const ch = ownerChange(acct, r, gait)
  if (!ch) return null
  const any = ch.legs.some((x) => x.joints.length)
  const allShort = ch.legs.filter((x) => x.compared).every((x) => x.short)
  return (
    <div style={css('display:flex;flex-direction:column;gap:8px;padding:14px 18px;border-radius:12px;border:1px solid #ECE8E2')}>
      <span style={css('display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:13.5px;font-weight:700')}>
        <span>{ch.baseLabel}({ch.baseDate})와 비교</span>
        <span style={css('font-weight:600;color:#5B6472')}>{ch.modelChanged ? '분석 방식이 달라 값만 견줄 수 있어요' : allShort ? '쓴 걸음 수가 모자라 값만 견줄 수 있어요' : any ? '달라진 다리만 주황으로 표시했어요' : '네 다리 모두 오차 범위 안이에요'}</span>
      </span>
      <div style={css('display:grid;grid-template-columns:repeat(4,1fr);gap:8px')}>
        {ORDER.map((code) => {
          const x = ch.legs.find((l) => l.code === code)!
          const on = x.joints.length > 0
          return (
            <div key={code} style={css(`padding:8px 10px;border-radius:10px;display:flex;flex-direction:column;gap:2px;border:1px solid ${on ? '#E7A77A' : '#ECE8E2'};background:${on ? '#FCEEE3' : '#FAF7F2'}`)}>
              <b style={css(`font-size:13px;color:${on ? '#A8481A' : '#3A4250'}`)}>{LEG_NAME[code]}</b>
              <span style={css(`font-size:12.5px;line-height:1.45;color:${on ? '#A8481A' : '#8E949C'}`)}>{legNote(x)}</span>
            </div>
          )
        })}
      </div>
      <span style={css('font-size:12px;color:#8E949C')}>관절을 접었다 펴는 폭(가동 범위)이 같은 상태를 다시 재도 생길 수 있는 차이(오차 범위)보다 크게 달라진 다리만 표시해요. 위 몸 그림 색은 이번 회차의 왼쪽·오른쪽 차이예요.</span>
    </div>
  )
}

export function OwnerAdvice({ og }: { og: OwnerGuide }) {
  const a = ownerAdvice(og)
  return (
    <div className="rep-p2" style={css('display:flex;flex-direction:column;gap:14px')}>
      <b style={css('font-size:18px')}>보호자가 알아 두면 좋은 점</b>
      <div style={css('padding:14px 18px;border-radius:12px;background:#FFF9F4;border:1px solid #F0DCCB;font-size:15px;line-height:1.6;font-weight:600')}>{og.what}</div>
      <div style={css('padding:14px 18px;border-radius:12px;border:1px solid #ECE8E2;display:flex;flex-direction:column;gap:10px')}>
        <b style={css('font-size:15px;color:#3A4250')}>다음 방문까지 할 일</b>
        <div style={css('display:flex;flex-direction:column;gap:6px')}>
          {a.todo.map((x) => <span key={x} style={css('font-size:14px;line-height:1.55;padding-left:12px;border-left:3px solid #CFE3D6')}>{x}</span>)}
        </div>
        {a.watch.length ? (
          <>
            <b style={css('font-size:13.5px;color:#5B6472;margin-top:2px')}>집에서 지켜봐 주세요</b>
            <div style={css('display:flex;flex-direction:column;gap:6px')}>
              {a.watch.map((x) => <span key={x} style={css('font-size:14px;line-height:1.55;padding-left:12px;border-left:3px solid #F2C9AE')}>{x}</span>)}
            </div>
          </>
        ) : null}
      </div>
      <div style={css('padding:14px 18px;border-radius:12px;background:#FCEEE3;border:1px solid #F0D2BC;font-size:14px;line-height:1.6;color:#8A3F12')}>
        <b>이럴 때는 병원에 연락하세요</b>
        <div style={css('margin-top:6px;display:flex;flex-direction:column;gap:2px')}>{a.contact.map((u, i) => <span key={i}>· {u}</span>)}</div>
      </div>
      <span style={css('font-size:12px;color:#8E949C')}>일반적인 안내예요. 우리 아이에게 맞는 관리는 담당 수의사와 상의해 주세요.</span>
    </div>
  )
}
