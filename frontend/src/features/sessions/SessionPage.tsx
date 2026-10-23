import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { CAMERA_SIDE_LABEL, GAIT_LABEL, SHOT_STATUS_LABEL, SHOT_STATUS_TONE, SIZE_LABEL, VALIDITY_LABEL, VALIDITY_TONE, fmtMonthDay, isShotInProgress } from '../../api/labels'
import { useCancelSession, useCompleteSession, useDeleteShot, useRetryShot, useSession, useUploadShot } from '../../api/sessions'
import type { SessionDetailOut, ShotOut } from '../../api/types'
import { useToast } from '../../app/toast'
import { Icon } from '../../components/Icon'
import { Badge, Button, Card, Empty, Sheet, TopBar } from '../../components/ui'
import './sessions.css'

/**
 * S3 측정 화면. 디자인 v5 `capReview`·`analyzing` 를 명세 흐름으로 합쳤다.
 * 영상 1건마다 업로드 → 2.5초 폴링으로 촬영 상태·방향별 유효 통과를 갱신 → 측정 종료 → 집계 중 → 완료면 회차 결과로.
 */
export function SessionPage() {
  const { sessionId = '' } = useParams()
  const nav = useNavigate()
  const toast = useToast()
  const q = useSession(sessionId)
  const upload = useUploadShot(sessionId)
  const complete = useCompleteSession(sessionId)
  const cancel = useCancelSession(sessionId)
  const retry = useRetryShot(sessionId)
  const del = useDeleteShot(sessionId)

  const [sheet, setSheet] = useState<'cancel' | 'complete' | { del: ShotOut } | null>(null)
  const camRef = useRef<HTMLInputElement>(null)
  const galleryRef = useRef<HTMLInputElement>(null)

  const s = q.data

  // 집계가 끝나면 회차 결과로
  useEffect(() => {
    if (s?.status === 'DONE') nav(`/sessions/${s.id}/result`, { replace: true })
  }, [s?.status, s?.id, nav])

  if (q.isError) {
    return (
      <div className="screen">
        <TopBar title="측정" />
        <div className="screen-body">
          <Empty>{q.error instanceof ApiError ? q.error.message : '회차를 불러오지 못했어요'}</Empty>
        </div>
      </div>
    )
  }
  if (!s) {
    return (
      <div className="screen">
        <TopBar title="측정" />
        <div className="screen-body">
          <div className="skeleton" style={{ height: 140 }} />
          <div className="skeleton" />
        </div>
      </div>
    )
  }

  if (s.status === 'AGGREGATING') return <AggregatingView s={s} />
  if (s.status === 'FAILED') return <FailedView s={s} />

  const measuring = s.status === 'MEASURING'
  const anyInProgress = s.shots.some((sh) => isShotInProgress(sh.status))
  const shotCount = s.shots.length

  async function onFiles(files: FileList | null) {
    if (!files || !files.length) return
    for (const file of Array.from(files)) {
      try {
        const out = await upload.mutateAsync(file)
        if (out.warnings.length) toast(out.warnings[0].message)
        else toast(`${out.seq_no}번째 영상을 올렸어요. 분석을 시작해요`)
      } catch (err) {
        toast(err instanceof Error ? err.message : '영상을 올리지 못했어요')
      }
    }
    if (camRef.current) camRef.current.value = ''
    if (galleryRef.current) galleryRef.current.value = ''
  }

  async function doComplete() {
    setSheet(null)
    try {
      await complete.mutateAsync()
    } catch (err) {
      toast(err instanceof Error ? err.message : '측정을 끝내지 못했어요')
    }
  }

  async function doCancel() {
    setSheet(null)
    try {
      await cancel.mutateAsync()
      toast('측정을 취소했어요')
      nav(`/dogs/${s!.dog_id}`, { replace: true })
    } catch (err) {
      toast(err instanceof Error ? err.message : '측정을 취소하지 못했어요')
    }
  }

  async function doDelete(shot: ShotOut) {
    setSheet(null)
    try {
      await del.mutateAsync(shot.id)
      toast(`${shot.seq_no}번째 영상을 지웠어요`)
    } catch (err) {
      toast(err instanceof Error ? err.message : '영상을 지우지 못했어요')
    }
  }

  async function doRetry(shot: ShotOut) {
    try {
      await retry.mutateAsync(shot.id)
      toast('다시 분석을 시작했어요')
    } catch (err) {
      toast(err instanceof Error ? err.message : '다시 분석하지 못했어요')
    }
  }

  const met = (side: 'LEFT' | 'RIGHT') => s!.progress[side].valid_passes >= s!.progress[side].recommended

  return (
    <div className="screen">
      <TopBar
        title="측정"
        onBack={() => nav(`/dogs/${s.dog_id}`)}
        right={
          measuring && (
            <button type="button" className="text-btn" style={{ color: 'var(--sub)' }} onClick={() => setSheet('cancel')} disabled={anyInProgress}>
              측정 취소
            </button>
          )
        }
      />
      <div className="scroll screen-body" style={{ gap: 14, paddingTop: 4 }}>
        <div className="sess-head">
          <div className="sess-title">{s.dog.name}</div>
          <div className="sess-sub tabular">
            {fmtMonthDay(s.measured_on)} · 체중 {s.weight_kg ?? s.dog.weight_kg}kg · {SIZE_LABEL[s.size_class]} · {s.staff.name}
          </div>
        </div>

        <Card className="progress-card">
          <b style={{ fontSize: 15 }}>방향별 유효 통과</b>
          {(['LEFT', 'RIGHT'] as const).map((side) => {
            const p = s.progress[side]
            const pct = Math.min(100, Math.round((p.valid_passes / Math.max(1, p.recommended)) * 100))
            return (
              <div className="progress-row" key={side}>
                <div className="label">
                  <span>{CAMERA_SIDE_LABEL[side]} 다리 (카메라 쪽이 {CAMERA_SIDE_LABEL[side]})</span>
                  <span className={`num tabular${met(side) ? ' met' : ''}`}>
                    {p.valid_passes} / 권장 {p.recommended}
                  </span>
                </div>
                <div className={`bar ${side.toLowerCase()}`}>
                  <div style={{ width: `${pct}%` }} />
                </div>
              </div>
            )
          })}
          {s.notices.map((n) => (
            <div key={n.code} className={`notice${n.code === 'RECOMMENDED_MET' ? ' ok' : ''}`}>
              {n.message}
            </div>
          ))}
          {!s.notices.length && (
            <span className="small muted">매트를 왕복해 걷게 하고 영상을 하나씩 올려요. 양쪽 모두 권장 수를 채우면 측정을 끝낼 수 있어요.</span>
          )}
        </Card>

        {measuring && (
          <div className="upload-actions">
            <input ref={galleryRef} type="file" accept="video/mp4,video/quicktime,video/*" multiple hidden onChange={(e) => onFiles(e.target.files)} />
            <input ref={camRef} type="file" accept="video/*" capture="environment" hidden onChange={(e) => onFiles(e.target.files)} />
            <Button variant="secondary" onClick={() => galleryRef.current?.click()} disabled={upload.isPending}>
              <Icon name="img" size={20} />
              갤러리
            </Button>
            <Button onClick={() => camRef.current?.click()} disabled={upload.isPending}>
              <Icon name="cam" size={20} />
              {upload.isPending ? '올리는 중…' : '촬영하기'}
            </Button>
          </div>
        )}

        <div className="section-title">
          <b>
            올린 영상<span className="count">{shotCount}건</span>
          </b>
          {anyInProgress && <span className="small muted">분석 중…</span>}
        </div>
        {shotCount === 0 ? (
          <Empty>
            아직 올린 영상이 없어요.
            <br />
            <span className="small">휴대폰을 가로로 들고 반려견이 옆으로 걷는 모습을 찍어 올려 주세요.</span>
          </Empty>
        ) : (
          <Card style={{ padding: '0 16px' }}>
            {s.shots.map((sh) => (
              <ShotItem key={sh.id} shot={sh} measuring={measuring} busy={retry.isPending || del.isPending} onRetry={() => doRetry(sh)} onDelete={() => setSheet({ del: sh })} />
            ))}
          </Card>
        )}
        <p className="small muted" style={{ lineHeight: 1.5 }}>
          올린 영상은 서버가 바로 분석해요. 화면을 닫아도 분석은 계속되고, 홈의 ‘측정 중’에서 다시 들어올 수 있어요.
        </p>
      </div>

      {measuring && (
        <div className="sticky-footer">
          <Button onClick={() => setSheet('complete')} dim={shotCount === 0} disabled={complete.isPending}>
            {complete.isPending ? '끝내는 중…' : '측정 종료'}
          </Button>
        </div>
      )}

      <Sheet open={sheet === 'complete'} onClose={() => setSheet(null)}>
        <b className="sheet-title">측정을 끝낼까요?</b>
        <span className="sheet-text">
          {shotCount === 0
            ? '영상을 1건 이상 올려야 끝낼 수 있어요.'
            : anyInProgress
              ? '아직 분석 중인 영상이 있어요. 지금 끝내도 분석이 끝난 뒤 회차 수치를 계산해요.'
              : `올린 영상 ${shotCount}건의 유효 통과로 회차 수치를 계산하고 보고서를 만들어요.`}
        </span>
        <div className="sheet-actions">
          <Button variant="ghost" onClick={() => setSheet(null)}>
            취소
          </Button>
          <Button onClick={doComplete} disabled={shotCount === 0}>
            측정 종료
          </Button>
        </div>
      </Sheet>

      <Sheet open={sheet === 'cancel'} onClose={() => setSheet(null)}>
        <b className="sheet-title">측정을 취소할까요?</b>
        <span className="sheet-text">이 회차와 올린 영상 {shotCount}건이 모두 지워지고 되돌릴 수 없어요.</span>
        <div className="sheet-actions">
          <Button variant="ghost" onClick={() => setSheet(null)}>
            계속 측정
          </Button>
          <Button variant="danger" onClick={doCancel}>
            측정 취소
          </Button>
        </div>
      </Sheet>

      <Sheet open={typeof sheet === 'object' && sheet !== null} onClose={() => setSheet(null)}>
        {typeof sheet === 'object' && sheet !== null && (
          <>
            <b className="sheet-title">{sheet.del.seq_no}번째 영상을 지울까요?</b>
            <span className="sheet-text">파일과 분석 결과가 함께 지워져요. 남은 영상의 번호는 그대로예요.</span>
            <div className="sheet-actions">
              <Button variant="ghost" onClick={() => setSheet(null)}>
                취소
              </Button>
              <Button variant="danger" onClick={() => doDelete(sheet.del)}>
                삭제
              </Button>
            </div>
          </>
        )}
      </Sheet>
    </div>
  )
}

function ShotItem({ shot, measuring, busy, onRetry, onDelete }: { shot: ShotOut; measuring: boolean; busy: boolean; onRetry: () => void; onDelete: () => void }) {
  const done = shot.status === 'DONE'
  const valid = shot.passes.filter((p) => p.is_valid).length
  const sub = done
    ? `통과 ${shot.passes.length}개 · 유효 ${valid}개${shot.below_min_spec ? ' · 최저 사양 미만' : ''}`
    : shot.status === 'FAILED'
      ? (shot.fail_reason?.message ?? '분석에 실패했습니다.')
      : `올린 시각 ${new Date(shot.uploaded_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}${shot.below_min_spec ? ' · 최저 사양 미만' : ''}`
  return (
    <div className="shot-item">
      <div className="shot-head">
        <div className={`shot-no${done ? '' : ' pending'}`}>{shot.seq_no}</div>
        <div className="shot-meta">
          <div className="t">
            {shot.seq_no}번째 영상
            {done && shot.validity ? <Badge tone={VALIDITY_TONE[shot.validity]}>{VALIDITY_LABEL[shot.validity]}</Badge> : <Badge tone={SHOT_STATUS_TONE[shot.status]}>{SHOT_STATUS_LABEL[shot.status]}</Badge>}
          </div>
          <span className="s">{sub}</span>
        </div>
      </div>
      {done && shot.validity_reason && <div className={`shot-reason${shot.validity === 'INVALID' ? ' bad' : ''}`}>{shot.validity_reason.message}</div>}
      {done && shot.passes.length > 0 && (
        <div className="pass-chips">
          {shot.passes.map((p) => (
            <span key={p.pass_no} className={`pass-chip ${p.is_valid ? 'valid' : 'invalid'}`} title={p.exclude_reason?.message ?? ''}>
              <span className={`side ${p.camera_side}`} />
              {p.pass_no}회 {GAIT_LABEL[p.gait_type]}
              {!p.is_valid && p.exclude_reason ? ` · ${p.exclude_reason.message.replace(/\.$/, '')}` : ''}
            </span>
          ))}
        </div>
      )}
      {measuring && (shot.status === 'FAILED' || !isShotInProgress(shot.status)) && (
        <div className="shot-actions">
          {shot.status === 'FAILED' && (
            <Button size="sm" className="btn-soft" onClick={onRetry} disabled={busy}>
              다시 분석
            </Button>
          )}
          {!isShotInProgress(shot.status) && (
            <Button size="sm" variant="ghost" onClick={onDelete} disabled={busy}>
              삭제
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

/** 집계 중. 디자인 v5 `analyzing`. 단계는 API 에 없어 상태 하나로 보여 준다(screenPlan 6절 #4). */
function AggregatingView({ s }: { s: SessionDetailOut }) {
  const nav = useNavigate()
  const analyzingShots = s.shots.filter((sh) => isShotInProgress(sh.status) || sh.status === 'UPLOADED').length
  return (
    <div className="screen" style={{ background: '#fff' }}>
      <div className="topbar">
        <div className="topbar-left">
          <button type="button" className="icon-btn" onClick={() => nav('/')} aria-label="닫기">
            <Icon name="x" />
          </button>
        </div>
      </div>
      <div className="analyzing">
        <b>분석 중입니다</b>
        <span className="sub tabular">
          {s.dog.name} · {analyzingShots > 0 ? `영상 ${analyzingShots}건 분석 중` : '회차 수치 계산 중'}
        </span>
        <div className="paw-walk" aria-hidden="true">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <img key={i} src="/assets/paw-print.png" alt="" style={{ left: i % 2 ? 96 : 30, top: 110 - i * 22, transform: `rotate(${-23 + (i % 2 ? 10 : -6)}deg)`, animationDelay: `${i * 0.35}s` }} />
          ))}
        </div>
      </div>
      <div className="sticky-footer" style={{ borderTop: 0, display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center' }}>
        <span className="small" style={{ color: 'var(--dim)' }}>
          화면을 닫아도 분석은 계속돼요
        </span>
        <Button variant="ghost" onClick={() => nav('/')}>
          홈에서 기다리기
        </Button>
      </div>
    </div>
  )
}

function FailedView({ s }: { s: SessionDetailOut }) {
  const nav = useNavigate()
  return (
    <div className="screen">
      <TopBar title="측정" onBack={() => nav(`/dogs/${s.dog_id}`)} />
      <div className="scroll screen-body" style={{ gap: 14 }}>
        <div className="sess-head">
          <div className="sess-title">{s.dog.name}</div>
          <div className="sess-sub tabular">
            {fmtMonthDay(s.measured_on)} · 체중 {s.weight_kg ?? s.dog.weight_kg}kg
          </div>
        </div>
        <Card style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Badge tone="bad">실패</Badge>
          <b style={{ fontSize: 18 }}>분석하지 못했어요</b>
          <span style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--sub)' }}>
            {s.fail_reason?.message ?? '회차 수치를 계산하지 못했습니다.'} 반려견이 뛰지 않고, 멈추거나 앉지 않고, 일직선으로 걷도록 다시 찍어 주세요.
          </span>
        </Card>
      </div>
      <div className="sticky-footer">
        <Button onClick={() => nav(`/capture?dog=${s.dog_id}`)}>
          <Icon name="cam" size={20} />
          다시 촬영하기
        </Button>
      </div>
    </div>
  )
}
