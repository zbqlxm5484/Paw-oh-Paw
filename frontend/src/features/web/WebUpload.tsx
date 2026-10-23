import { useEffect, useRef, useState, type DragEvent } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { useDogs } from '../../api/dogs'
import { CAMERA_SIDE_LABEL, GAIT_LABEL, SHOT_STATUS_LABEL, SHOT_STATUS_TONE, SIZE_LABEL, VALIDITY_LABEL, VALIDITY_TONE, fmtMonthDay, isShotInProgress } from '../../api/labels'
import { useCancelSession, useCompleteSession, useDeleteShot, useRetryShot, useSession, useStartSession, useUploadShot } from '../../api/sessions'
import type { ShotOut } from '../../api/types'
import { useToast } from '../../app/toast'
import { Icon } from '../../components/Icon'
import { Badge, Button, Sheet } from '../../components/ui'
import { DogStrip } from './DogStrip'
import '../sessions/sessions.css'

/** 웹 v2 "보행 영상 분석" 1·2단계: 반려견 고르고 오늘 체중 → 회차 시작(POST /dogs/{id}/sessions) → 영상 올리기 화면으로. */
export function WebUpload() {
  const nav = useNavigate()
  const toast = useToast()
  const [sp] = useSearchParams()
  const dogsQ = useDogs({ size: 100 })
  const start = useStartSession()
  const dogs = dogsQ.data?.items ?? []
  const [picked, setPicked] = useState<string | null>(sp.get('dog'))
  const [weight, setWeight] = useState('')
  const [guide, setGuide] = useState(false)
  const sel = dogs.find((d) => d.id === picked) ?? (picked ? undefined : dogs[0])

  async function go() {
    if (!sel) return toast('촬영할 반려견을 골라 주세요')
    if (sel.open_session_id) return nav(`/sessions/${sel.open_session_id}`)
    const w = weight.trim()
    const num = w ? Number(w) : null
    if (w && (!Number.isFinite(num) || num! < 0.5 || num! > 100)) return toast('체중은 0.5~100kg 사이로 입력해 주세요')
    try {
      const s = await start.mutateAsync({ dogId: sel.id, body: { weight_kg: num } })
      nav(`/sessions/${s.id}`, { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.code === 'SESSION_ALREADY_OPEN' && typeof err.detail?.session_id === 'string') return nav(`/sessions/${err.detail.session_id}`, { replace: true })
      toast(err instanceof Error ? err.message : '회차를 시작하지 못했어요')
    }
  }

  return (
    <main className="web-main" style={{ paddingTop: 32 }}>
      <h1 className="web-h1" style={{ fontSize: 34 }}>
        보행 영상 분석
      </h1>
      <div style={{ maxWidth: 1100, display: 'flex', flexDirection: 'column', gap: 22 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <b style={{ fontSize: 16 }}>1. 반려견 선택</b>
          {dogsQ.isSuccess && dogs.length === 0 && (
            <div className="web-card" style={{ padding: 24, display: 'flex', alignItems: 'center', gap: 16 }}>
              <span style={{ flex: 1, color: 'var(--sub)' }}>등록된 반려견이 없어요.</span>
              <button type="button" className="web-btn pri" onClick={() => nav('/dogs/new')}>
                반려견 등록하기
              </button>
            </div>
          )}
          <DogStrip dogs={dogs} selectedId={sel?.id ?? null} onPick={(id) => setPicked(id)} onAdd={() => nav('/dogs/new')} />
        </div>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 320 }}>
          <span style={{ fontSize: 16, fontWeight: 700 }}>
            2. 오늘 체중 <span style={{ color: 'var(--dim)', fontWeight: 500, fontSize: 14 }}>선택</span>
          </span>
          <div style={{ position: 'relative', display: 'flex' }}>
            <input className="input" value={weight} onChange={(e) => setWeight(e.target.value)} placeholder={sel ? `등록 체중 ${sel.weight_kg}` : '예) 28.1'} inputMode="decimal" style={{ paddingRight: 44 }} disabled={!!sel?.open_session_id} />
            <span className="input-unit">kg</span>
          </div>
          <span style={{ fontSize: 13, color: 'var(--sub)' }}>재활 중 체중이 바뀌면 그날 기준으로 비교해요. 비우면 등록 체중을 써요.</span>
        </label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <b style={{ fontSize: 16 }}>3. 영상 올리기</b>
          <span style={{ fontSize: 14.5, color: 'var(--sub)' }}>회차를 시작하면 영상을 하나씩 끌어다 놓을 수 있어요. 올린 영상은 서버가 바로 분석하고, 방향별 유효 통과가 권장 수(8)에 닿으면 측정을 끝낼 수 있어요.</span>
        </div>
        <button type="button" className="web-back" onClick={() => setGuide(true)} style={{ marginTop: -6 }}>
          <span style={{ width: 20, height: 20, borderRadius: '50%', border: '1.6px solid currentColor', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 800 }}>?</span>
          영상 촬영 방법
        </button>
        <button type="button" className={`web-btn pri lg${!sel ? ' dim' : ''}`} style={{ alignSelf: 'flex-end', width: 240 }} onClick={go} disabled={start.isPending}>
          {sel?.open_session_id ? '이어서 측정' : start.isPending ? '회차 만드는 중…' : '측정 시작'}
        </button>
      </div>
      <GuideSheet open={guide} onClose={() => setGuide(false)} />
    </main>
  )
}

function GuideSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const steps: [string, string][] = [
    ['매트와 직각, 옆에서', '반려견이 걷는 방향과 직각 위치에서 옆모습이 보이게 찍어요.'],
    ['휴대폰은 가로로', '몸 전체가 화면 안에 들어오게, 흔들리지 않게 잡아요.'],
    ['평소처럼 걷게', '뛰거나 멈추거나 앉지 않고 매트를 일직선으로 지나가게 해요.'],
    ['양쪽 방향 모두', '왼쪽 다리와 오른쪽 다리는 각각 카메라 쪽에 있을 때 재요. 왕복해서 걷게 해 주세요.'],
  ]
  return (
    <Sheet open={open} onClose={onClose}>
      <b className="sheet-title">영상 촬영 방법</b>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {steps.map(([t, b], i) => (
          <div key={t} style={{ display: 'flex', gap: 14 }}>
            <span style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--pri-l)', color: 'var(--pri-ink)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 800, flex: 'none' }}>{i + 1}</span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3, paddingTop: 3 }}>
              <b style={{ fontSize: 15 }}>{t}</b>
              <span style={{ fontSize: 14, color: 'var(--sub)', lineHeight: 1.5 }}>{b}</span>
            </div>
          </div>
        ))}
      </div>
      <Button onClick={onClose}>확인</Button>
    </Sheet>
  )
}

/** 웹 v2 영상 올리기 3단계 + 측정 진행: 드래그앤드롭 업로드, 방향별 진행, 촬영 목록, 측정 종료·취소. 집계 중이면 분석 중 화면. */
export function WebSession() {
  const { sessionId = '' } = useParams()
  const nav = useNavigate()
  const toast = useToast()
  const q = useSession(sessionId)
  const upload = useUploadShot(sessionId)
  const complete = useCompleteSession(sessionId)
  const cancel = useCancelSession(sessionId)
  const retry = useRetryShot(sessionId)
  const del = useDeleteShot(sessionId)
  const fileRef = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const [sheet, setSheet] = useState<'complete' | 'cancel' | null>(null)
  const [guide, setGuide] = useState(false)
  const s = q.data

  useEffect(() => {
    if (s?.status === 'DONE') nav(`/sessions/${s.id}/result`, { replace: true })
  }, [s?.status, s?.id, nav])

  async function onFiles(files: FileList | File[] | null) {
    if (!files) return
    for (const file of Array.from(files)) {
      try {
        const out = await upload.mutateAsync(file)
        toast(out.warnings.length ? out.warnings[0].message : `${out.seq_no}번째 영상을 올렸어요. 분석을 시작해요`)
      } catch (err) {
        toast(err instanceof Error ? err.message : '영상을 올리지 못했어요')
      }
    }
    if (fileRef.current) fileRef.current.value = ''
  }
  function onDrop(e: DragEvent) {
    e.preventDefault()
    setOver(false)
    const files = Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith('video/') || /\.(mp4|mov)$/i.test(f.name))
    if (!files.length) return toast('MP4 또는 MOV 영상만 올릴 수 있어요')
    onFiles(files)
  }

  if (q.isError)
    return (
      <main className="web-main">
        <div className="web-card" style={{ padding: 24 }}>{q.error instanceof ApiError ? q.error.message : '회차를 불러오지 못했어요'}</div>
      </main>
    )
  if (!s)
    return (
      <main className="web-main">
        <div className="skeleton" style={{ height: 200 }} />
      </main>
    )

  if (s.status === 'AGGREGATING') {
    const n = s.shots.filter((sh) => isShotInProgress(sh.status) || sh.status === 'UPLOADED').length
    return (
      <main className="web-main" style={{ padding: '80px 80px 96px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, textAlign: 'center' }}>
          <b style={{ fontSize: 38, letterSpacing: -1 }}>분석 중입니다</b>
          <span className="tabular" style={{ fontSize: 17, color: 'var(--sub)' }}>
            {s.dog.name} · {n > 0 ? `영상 ${n}건 분석 중` : '회차 수치 계산 중'}
          </span>
          <div className="paw-walk" style={{ width: 'min(100%, 1400px)', height: 340, margin: '64px 0 24px' }} aria-hidden="true">
            {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
              <img key={i} src="/assets/paw-print.png" alt="" style={{ width: 96, height: 96, left: `${8 + i * 12}%`, top: i % 2 ? 60 : 180, transform: `rotate(${-23 + (i % 2 ? 10 : -6)}deg)`, animationDelay: `${i * 0.3}s` }} />
            ))}
          </div>
          <span style={{ fontSize: 14, color: 'var(--dim)' }}>화면을 닫아도 분석은 계속돼요.</span>
          <button type="button" className="web-btn" onClick={() => nav('/')}>
            홈에서 기다리기
          </button>
        </div>
      </main>
    )
  }

  if (s.status === 'FAILED')
    return (
      <main className="web-main">
        <div className="web-card" style={{ padding: 32, display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 640 }}>
          <Badge tone="bad">실패</Badge>
          <b style={{ fontSize: 20 }}>분석하지 못했어요</b>
          <span style={{ fontSize: 15, lineHeight: 1.65, color: 'var(--sub)' }}>{s.fail_reason?.message ?? '회차 수치를 계산하지 못했습니다.'} 반려견이 뛰지 않고, 멈추거나 앉지 않고, 일직선으로 걷도록 다시 찍어 올려 주세요.</span>
          <button type="button" className="web-btn pri" style={{ alignSelf: 'flex-start' }} onClick={() => nav(`/capture?dog=${s.dog_id}`)}>
            다시 올리기
          </button>
        </div>
      </main>
    )

  const measuring = s.status === 'MEASURING'
  const anyInProgress = s.shots.some((sh) => isShotInProgress(sh.status))
  const met = (side: 'LEFT' | 'RIGHT') => s.progress[side].valid_passes >= s.progress[side].recommended

  return (
    <main className="web-main" style={{ paddingTop: 32 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <h1 className="web-h1" style={{ fontSize: 34 }}>
            {s.dog.name} · 보행 영상 분석
          </h1>
          <div className="tabular" style={{ fontSize: 15, color: 'var(--sub)', marginTop: 4 }}>
            {fmtMonthDay(s.measured_on)} · 체중 {s.weight_kg ?? s.dog.weight_kg}kg · {SIZE_LABEL[s.size_class]} · {s.staff.name}
          </div>
        </div>
        {measuring && (
          <button type="button" className="web-btn" onClick={() => setSheet('cancel')} disabled={anyInProgress}>
            측정 취소
          </button>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 16, alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <input ref={fileRef} type="file" accept="video/mp4,video/quicktime,video/*" multiple hidden onChange={(e) => onFiles(e.target.files)} />
          {measuring && (
            <button
              type="button"
              className={`dropzone${over ? ' over' : ''}`}
              onClick={() => fileRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault()
                setOver(true)
              }}
              onDragLeave={() => setOver(false)}
              onDrop={onDrop}
              disabled={upload.isPending}
            >
              <div className="ico">
                <Icon name="img" size={28} />
              </div>
              <b>{upload.isPending ? '올리는 중…' : '영상을 끌어다 놓거나 눌러서 선택하세요'}</b>
              <span>MP4 · MOV · 가로 영상 · 1건씩 올리면 바로 분석해요</span>
            </button>
          )}
          <div className="web-card progress-card" style={{ borderRadius: 18 }}>
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
          </div>
          <button type="button" className="web-back" onClick={() => setGuide(true)}>
            <span style={{ width: 20, height: 20, borderRadius: '50%', border: '1.6px solid currentColor', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 800 }}>?</span>
            영상 촬영 방법
          </button>
          {measuring && (
            <button type="button" className={`web-btn pri lg${s.shots.length === 0 ? ' dim' : ''}`} style={{ alignSelf: 'flex-end', width: 240 }} onClick={() => setSheet('complete')} disabled={complete.isPending}>
              측정 종료
            </button>
          )}
        </div>

        <div className="web-card" style={{ padding: '4px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', padding: '14px 0 6px' }}>
            <b style={{ fontSize: 16 }}>
              올린 영상 <span style={{ color: 'var(--dim)', fontWeight: 600, fontSize: 14 }}>{s.shots.length}건</span>
            </b>
            {anyInProgress && <span className="small muted">분석 중… 2.5초마다 갱신</span>}
          </div>
          {s.shots.length === 0 && <div style={{ padding: '24px 0 28px', color: 'var(--sub)', fontSize: 14.5 }}>아직 올린 영상이 없어요. 왼쪽에 영상을 끌어다 놓아 주세요.</div>}
          {s.shots.map((sh) => (
            <WebShotRow
              key={sh.id}
              shot={sh}
              measuring={measuring}
              busy={retry.isPending || del.isPending}
              onRetry={() => retry.mutateAsync(sh.id).then(() => toast('다시 분석을 시작했어요')).catch((e: unknown) => toast(e instanceof Error ? e.message : '다시 분석하지 못했어요'))}
              onDelete={() => del.mutateAsync(sh.id).then(() => toast(`${sh.seq_no}번째 영상을 지웠어요`)).catch((e: unknown) => toast(e instanceof Error ? e.message : '영상을 지우지 못했어요'))}
              onOpen={() => nav(`/shots/${sh.id}`)}
            />
          ))}
        </div>
      </div>

      <Sheet open={sheet === 'complete'} onClose={() => setSheet(null)}>
        <b className="sheet-title">측정을 끝낼까요?</b>
        <span className="sheet-text">{anyInProgress ? '아직 분석 중인 영상이 있어요. 지금 끝내도 분석이 끝난 뒤 회차 수치를 계산해요.' : `올린 영상 ${s.shots.length}건의 유효 통과로 회차 수치를 계산하고 보고서를 만들어요.`}</span>
        <div className="sheet-actions">
          <Button variant="ghost" onClick={() => setSheet(null)}>
            취소
          </Button>
          <Button
            onClick={() => {
              setSheet(null)
              complete.mutateAsync().catch((e: unknown) => toast(e instanceof Error ? e.message : '측정을 끝내지 못했어요'))
            }}
            disabled={s.shots.length === 0}
          >
            측정 종료
          </Button>
        </div>
      </Sheet>
      <Sheet open={sheet === 'cancel'} onClose={() => setSheet(null)}>
        <b className="sheet-title">측정을 취소할까요?</b>
        <span className="sheet-text">이 회차와 올린 영상 {s.shots.length}건이 모두 지워지고 되돌릴 수 없어요.</span>
        <div className="sheet-actions">
          <Button variant="ghost" onClick={() => setSheet(null)}>
            계속 측정
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              setSheet(null)
              cancel
                .mutateAsync()
                .then(() => {
                  toast('측정을 취소했어요')
                  nav(`/?dog=${s.dog_id}`, { replace: true })
                })
                .catch((e: unknown) => toast(e instanceof Error ? e.message : '측정을 취소하지 못했어요'))
            }}
          >
            측정 취소
          </Button>
        </div>
      </Sheet>
      <GuideSheet open={guide} onClose={() => setGuide(false)} />
    </main>
  )
}

function WebShotRow({ shot, measuring, busy, onRetry, onDelete, onOpen }: { shot: ShotOut; measuring: boolean; busy: boolean; onRetry: () => void; onDelete: () => void; onOpen: () => void }) {
  const done = shot.status === 'DONE'
  const valid = shot.passes.filter((p) => p.is_valid).length
  return (
    <div className="shot-item">
      <div className="shot-head">
        <div className={`shot-no${done ? '' : ' pending'}`}>{shot.seq_no}</div>
        <div className="shot-meta">
          <div className="t">
            {shot.seq_no}번째 영상
            {done && shot.validity ? <Badge tone={VALIDITY_TONE[shot.validity]}>{VALIDITY_LABEL[shot.validity]}</Badge> : <Badge tone={SHOT_STATUS_TONE[shot.status]}>{SHOT_STATUS_LABEL[shot.status]}</Badge>}
          </div>
          <span className="s">{done ? `통과 ${shot.passes.length}개 · 유효 ${valid}개${shot.below_min_spec ? ' · 최저 사양 미만' : ''}` : shot.status === 'FAILED' ? (shot.fail_reason?.message ?? '분석에 실패했습니다.') : `올린 시각 ${new Date(shot.uploaded_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}`}</span>
        </div>
        <div className="shot-actions">
          {done && (
            <Button size="sm" variant="secondary" onClick={onOpen}>
              상세
            </Button>
          )}
          {measuring && shot.status === 'FAILED' && (
            <Button size="sm" className="btn-soft" onClick={onRetry} disabled={busy}>
              다시 분석
            </Button>
          )}
          {measuring && !isShotInProgress(shot.status) && (
            <Button size="sm" variant="ghost" onClick={onDelete} disabled={busy}>
              삭제
            </Button>
          )}
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
    </div>
  )
}
