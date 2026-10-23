import { useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { useDog, useDogSessions, useUpdateDog } from '../../api/dogs'
import { LIMB_LABEL, SESSION_STATUS_LABEL, SESSION_STATUS_TONE, SEX_LABEL, SIZE_LABEL, dogDesc, fmtDate, fmtMonthDay } from '../../api/labels'
import type { SessionHistoryItem } from '../../api/types'
import { useToast } from '../../app/toast'
import { Icon } from '../../components/Icon'
import { Avatar, Badge, Button, Card, Empty, Tag, TopBar } from '../../components/ui'
import './dogs.css'

/** S2·S7 반려견 상세·측정 이력. 디자인 v5 `dog`. */
export function DogDetailPage() {
  const { dogId } = useParams()
  const nav = useNavigate()
  const toast = useToast()
  const dogQ = useDog(dogId)
  const histQ = useDogSessions(dogId)
  const update = useUpdateDog(dogId ?? '')

  const dog = dogQ.data
  const hist = histQ.data?.items ?? []
  // 회차 번호는 서버에 없다. 오래된 것부터 1 (screenPlan 6절 #10)
  const total = hist.length
  const doneCount = hist.filter((h) => h.status === 'DONE').length

  if (dogQ.isError) {
    const msg = dogQ.error instanceof ApiError ? dogQ.error.message : '반려견 정보를 불러오지 못했어요'
    return (
      <div className="screen">
        <TopBar title="반려견 정보" />
        <div className="screen-body">
          <Empty>{msg}</Empty>
        </div>
      </div>
    )
  }

  async function setBaseline(s: SessionHistoryItem) {
    try {
      await update.mutateAsync({ baseline_session_id: s.id })
      histQ.refetch()
      toast(`${fmtMonthDay(s.measured_on)} 회차를 기준으로 정했어요`)
    } catch (err) {
      toast(err instanceof Error ? err.message : '기준 회차를 바꾸지 못했어요')
    }
  }

  function startMeasure() {
    if (!dog) return
    if (dog.open_session_id) {
      toast('진행 중인 회차로 이어서 측정해요')
    }
    nav('/capture', { state: { dogId: dog.id, sessionId: dog.open_session_id } })
  }

  function compare() {
    if (doneCount < 2) {
      toast('완료된 회차가 2개 이상 있어야 비교할 수 있어요')
      return
    }
    toast('경과 비교는 다음 단계에서 붙어요')
  }

  const baseline = hist.find((h) => h.is_baseline)

  return (
    <div className="screen">
      <TopBar
        title="반려견 정보"
        right={
          <button type="button" className="text-btn" onClick={() => nav(`/dogs/${dogId}/edit`)} disabled={!dog}>
            수정
          </button>
        }
      />
      <div className="scroll screen-body" style={{ gap: 14, paddingTop: 4 }}>
        {dog ? (
          <>
            <div className="dog-hero">
              <Avatar name={dog.name} size={64} />
              <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div className="dog-hero-name">{dog.name}</div>
                <div className="dog-hero-desc">{dogDesc(dog)}</div>
              </div>
            </div>
            <div className="tags">
              <Tag>
                {SIZE_LABEL[dog.size_class]} · {dog.size_class_manual ? '직접 지정' : '자동 분류'}
              </Tag>
              {dog.sex && <Tag>{SEX_LABEL[dog.sex]}</Tag>}
              {dog.open_session_id && <span className="live-chip" style={{ height: 28 }}>측정 중</span>}
            </div>

            <Card className="info-card">
              <b>재활 정보</b>
              <InfoRow k="재활 시작일" v={dog.rehab_start_date ? fmtDate(dog.rehab_start_date) : '미입력'} />
              <InfoRow k="관심 다리" v={dog.focus_limb ? LIMB_LABEL[dog.focus_limb] : '미선택'} />
              <InfoRow
                k="기준 회차"
                v={baseline ? `${fmtMonthDay(baseline.measured_on)} · ${sessionNo(hist, baseline)}회차` : '없음'}
                sub={dog.baseline_session_id ? '' : baseline ? '가장 이른 회차로 자동 지정' : ''}
              />
              <InfoRow k="내부 메모" v={dog.memo || '없음'} sub="보고서에는 넣지 않아요" />
            </Card>

            <div className="section-title">
              <b>
                측정 이력<span className="count">{total}회차</span>
              </b>
            </div>
            {histQ.isPending && <div className="skeleton" />}
            {histQ.isSuccess && total === 0 && <Empty>아직 측정 기록이 없어요</Empty>}
            {total > 0 && (
              <Card className="hist-card">
                {hist.map((h) => (
                  <HistItem key={h.id} h={h} no={sessionNo(hist, h)} onOpen={() => toast('회차 결과는 다음 단계에서 붙어요')} onSetBase={() => setBaseline(h)} busy={update.isPending} />
                ))}
              </Card>
            )}
          </>
        ) : (
          <>
            <div className="skeleton" style={{ height: 64 }} />
            <div className="skeleton" style={{ height: 200 }} />
          </>
        )}
      </div>
      <div className="sticky-footer footer-2">
        <Button variant="secondary" onClick={compare} dim={doneCount < 2}>
          경과 비교
        </Button>
        <Button onClick={startMeasure} disabled={!dog}>
          <Icon name="cam" size={20} />
          {dog?.open_session_id ? '이어서 측정' : '측정 시작'}
        </Button>
      </div>
    </div>
  )
}

function sessionNo(hist: SessionHistoryItem[], h: SessionHistoryItem): number {
  // hist 는 최신이 위. 오래된 것부터 1
  return hist.length - hist.findIndex((x) => x.id === h.id)
}

function InfoRow({ k, v, sub }: { k: string; v: string; sub?: string }) {
  return (
    <div className="info-row">
      <span className="k">{k}</span>
      <div className="v">
        <span>{v}</span>
        {sub && <span className="sub">{sub}</span>}
      </div>
    </div>
  )
}

function HistItem({ h, no, onOpen, onSetBase, busy }: { h: SessionHistoryItem; no: number; onOpen: () => void; onSetBase: () => void; busy: boolean }) {
  const hasReport = !!h.reports && (h.reports.OWNER === 'DONE' || h.reports.VET === 'DONE')
  const sub =
    h.status === 'FAILED'
      ? `체중 ${h.weight_kg ?? '-'}kg · 쓸 수 있는 통과 없음`
      : h.status === 'MEASURING'
        ? `체중 ${h.weight_kg ?? '-'}kg · 유효 통과 왼 ${h.valid_passes.LEFT} · 오 ${h.valid_passes.RIGHT}`
        : `체중 ${h.weight_kg ?? '-'}kg · 유효 통과 왼 ${h.valid_passes.LEFT} · 오 ${h.valid_passes.RIGHT} · 모델 ${h.model_version ?? '-'}`
  return (
    <div className="hist-item" role="button" tabIndex={0} onClick={onOpen} onKeyDown={(e) => e.key === 'Enter' && onOpen()}>
      <div className="hist-main">
        <div className="hist-title">
          <b>
            {no}회차 · {fmtMonthDay(h.measured_on)}
          </b>
          {h.is_baseline && <span className="mini-badge dark">기준</span>}
          {hasReport && <span className="mini-badge soft">보고서</span>}
        </div>
        <span className="hist-sub tabular">{sub}</span>
        {h.status === 'DONE' && !h.is_baseline && (
          <button
            type="button"
            className="hist-base-btn"
            disabled={busy}
            onClick={(e) => {
              e.stopPropagation()
              onSetBase()
            }}
          >
            기준 회차로 지정
          </button>
        )}
      </div>
      <Badge tone={SESSION_STATUS_TONE[h.status]}>{SESSION_STATUS_LABEL[h.status]}</Badge>
    </div>
  )
}
