import { useNavigate, useParams } from 'react-router-dom'

import { fmtMonthDay } from '../../api/labels'
import { useSession } from '../../api/sessions'
import { Badge, Button, Card, Empty, TopBar } from '../../components/ui'

/** S5 회차 결과 자리. 7단계에서 GET /sessions/{id}/result 로 채운다. */
export function SessionResultPlaceholder() {
  const { sessionId } = useParams()
  const nav = useNavigate()
  const q = useSession(sessionId)
  const s = q.data
  return (
    <div className="screen">
      <TopBar title="회차 결과" onBack={() => nav(s ? `/dogs/${s.dog_id}` : '/')} />
      <div className="scroll screen-body" style={{ gap: 14 }}>
        {s && (
          <Card style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Badge tone="ok">완료</Badge>
            <b style={{ fontSize: 18 }}>{s.dog.name} 측정이 끝났어요</b>
            <span className="tabular" style={{ fontSize: 14, color: 'var(--sub)' }}>
              {fmtMonthDay(s.measured_on)} · 영상 {s.shots.length}건 · 유효 통과 왼 {s.progress.LEFT.valid_passes} · 오 {s.progress.RIGHT.valid_passes}
              {s.model_version ? ` · 모델 ${s.model_version}` : ''}
            </span>
          </Card>
        )}
        <Empty>
          회차 수치와 다리 비교는 다음 단계에서 붙어요.
          <br />
          <span className="small">docs/frontend/screenPlan.md 7단계</span>
        </Empty>
      </div>
      <div className="sticky-footer">
        <Button variant="secondary" onClick={() => nav(s ? `/dogs/${s.dog_id}` : '/')}>
          반려견 화면으로
        </Button>
      </div>
    </div>
  )
}
