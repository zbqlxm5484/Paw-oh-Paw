import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { CAMERA_SIDE_LABEL, GAIT_LABEL, JOINT_LABEL, SHOT_STATUS_LABEL, SHOT_STATUS_TONE, VALIDITY_LABEL, VALIDITY_TONE, fileUrl, fmtMonthDay } from '../../api/labels'
import { useAngles, useShot } from '../../api/results'
import { useSession } from '../../api/sessions'
import type { JointCode, ShotDetailOut, ShotOut } from '../../api/types'
import { Badge, Card, Empty, TopBar } from '../../components/ui'
import './results.css'

/** 회차의 촬영 목록(S4 진입). 디자인에는 없는 화면이라 측정 화면의 촬영 목록 모양을 그대로 쓴다. */
export function SessionShotsPage() {
  const { sessionId } = useParams()
  const nav = useNavigate()
  const q = useSession(sessionId)
  const s = q.data
  return (
    <div className="screen">
      <TopBar title="촬영별 결과" onBack={() => nav(`/sessions/${sessionId}/result`)} />
      <div className="scroll screen-body" style={{ gap: 12, paddingTop: 4 }}>
        {s && (
          <div className="res-head">
            <div>
              <div className="res-name">{s.dog.name}</div>
              <div className="res-when tabular">
                {fmtMonthDay(s.measured_on)} · 촬영 {s.shots.length}건
              </div>
            </div>
          </div>
        )}
        {q.isError && <Empty>{q.error instanceof ApiError ? q.error.message : '회차를 불러오지 못했어요'}</Empty>}
        {s && s.shots.length === 0 && <Empty>촬영이 없어요</Empty>}
        {s && s.shots.length > 0 && (
          <Card style={{ padding: '0 16px' }}>
            {s.shots.map((sh) => (
              <ShotRow key={sh.id} sh={sh} onOpen={() => nav(`/shots/${sh.id}`)} />
            ))}
          </Card>
        )}
      </div>
    </div>
  )
}

function ShotRow({ sh, onOpen }: { sh: ShotOut; onOpen: () => void }) {
  const valid = sh.passes.filter((p) => p.is_valid).length
  return (
    <button type="button" className="res-item" onClick={onOpen}>
      <div className={`shot-no${sh.status === 'DONE' ? '' : ' pending'}`}>{sh.seq_no}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 15, fontWeight: 700 }}>{sh.seq_no}번째 영상</div>
        <div className="small muted tabular" style={{ marginTop: 2 }}>
          {sh.status === 'DONE' ? `통과 ${sh.passes.length}개 · 유효 ${valid}개` : (sh.fail_reason?.message ?? SHOT_STATUS_LABEL[sh.status])}
        </div>
      </div>
      {sh.status === 'DONE' && sh.validity ? <Badge tone={VALIDITY_TONE[sh.validity]}>{VALIDITY_LABEL[sh.validity]}</Badge> : <Badge tone={SHOT_STATUS_TONE[sh.status]}>{SHOT_STATUS_LABEL[sh.status]}</Badge>}
    </button>
  )
}

const JOINTS: JointCode[] = ['stifle', 'hip', 'tarsus', 'elbow', 'shoulder', 'carpus']

/** S4 촬영 상세: 결과 영상(서명 주소), 통과별 유효 구간, 입력 사양, 관절 각도 곡선. */
export function ShotDetailPage() {
  const { shotId } = useParams()
  const nav = useNavigate()
  const q = useShot(shotId)
  const sh = q.data
  const anglesQ = useAngles(shotId, sh?.status === 'DONE')
  const [joint, setJoint] = useState<JointCode>('stifle')
  const [passNo, setPassNo] = useState<number | null>(null)

  const src = fileUrl(sh?.video_url)
  const dur = sh?.duration_sec ?? null
  const fps = sh?.fps ?? null

  const curve = useMemo(() => {
    const passes = anglesQ.data?.passes ?? []
    const p = passes.find((x) => x.pass_no === passNo) ?? passes[0]
    if (!p) return null
    const arr = p.angles[joint]
    const vals = arr.filter((v): v is number => v != null)
    if (!vals.length) return { p, d: '', min: 0, max: 0 }
    const min = Math.floor(Math.min(...vals) / 10) * 10
    const max = Math.ceil(Math.max(...vals) / 10) * 10
    const W = 296
    const X = (i: number) => 24 + (i / Math.max(1, arr.length - 1)) * W
    const Y = (v: number) => 130 - ((v - min) / Math.max(1, max - min)) * 110
    // null 에서 선을 끊는다(api-spec 6절)
    let d = ''
    let pen = false
    arr.forEach((v, i) => {
      if (v == null) {
        pen = false
        return
      }
      d += `${pen ? 'L' : 'M'}${X(i).toFixed(1)},${Y(v).toFixed(1)} `
      pen = true
    })
    return { p, d, min, max }
  }, [anglesQ.data, joint, passNo])

  if (q.isError) {
    return (
      <div className="screen">
        <TopBar title="촬영 결과" />
        <div className="screen-body">
          <Empty>{q.error instanceof ApiError ? q.error.message : '촬영을 불러오지 못했어요'}</Empty>
        </div>
      </div>
    )
  }

  return (
    <div className="screen">
      <TopBar title={sh ? `${sh.seq_no}번째 영상` : '촬영 결과'} onBack={() => nav(-1)} />
      <div className="scroll screen-body" style={{ gap: 12, paddingTop: 4 }}>
        {!sh && <div className="skeleton" style={{ height: 200 }} />}
        {sh && (
          <>
            <div className="video-box">
              {src ? (
                <video key={src} src={src} controls playsInline preload="metadata" onError={() => q.refetch()} />
              ) : sh.video_status === 'FAILED' ? (
                <span>{sh.fail_reason?.message ?? '결과 영상을 만들지 못했습니다. 판정 결과는 그대로 볼 수 있습니다.'}</span>
              ) : (
                <span>{sh.status === 'DONE' ? '결과 영상을 만드는 중이에요' : '분석이 끝나면 골격을 그린 영상이 여기 보여요'}</span>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              {sh.status === 'DONE' && sh.validity ? <Badge tone={VALIDITY_TONE[sh.validity]}>{VALIDITY_LABEL[sh.validity]}</Badge> : <Badge tone={SHOT_STATUS_TONE[sh.status]}>{SHOT_STATUS_LABEL[sh.status]}</Badge>}
              {sh.below_min_spec && <Badge tone="warn">최저 사양 미만</Badge>}
              <span className="small muted">
                올린 시각 {new Date(sh.uploaded_at).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
            {sh.validity_reason && <div className={`shot-reason${sh.validity === 'INVALID' ? ' bad' : ''}`}>{sh.validity_reason.message}</div>}
            {sh.status === 'FAILED' && sh.fail_reason && <div className="shot-reason bad">{sh.fail_reason.message}</div>}

            {sh.status === 'DONE' && (
              <Card style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                <b style={{ fontSize: 15 }}>통과 {sh.passes.length}개</b>
                {dur && fps && (
                  <div className="timeline" aria-hidden="true">
                    {sh.passes.map((p) => {
                      const l = (p.start_frame / fps / dur) * 100
                      const w = ((p.end_frame - p.start_frame) / fps / dur) * 100
                      return <span key={p.pass_no} className={p.is_valid ? 'valid' : 'invalid'} style={{ left: `${l}%`, width: `${Math.max(1, w)}%` }} />
                    })}
                  </div>
                )}
                {sh.passes.map((p) => (
                  <div key={p.pass_no} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, fontSize: 13.5 }}>
                    <span className={`pass-chip ${p.is_valid ? 'valid' : 'invalid'}`} style={{ textDecoration: 'none' }}>
                      <span className={`side ${p.camera_side}`} />
                      {p.pass_no}회
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div>
                        {CAMERA_SIDE_LABEL[p.camera_side]} 다리 · {GAIT_LABEL[p.gait_type]}
                        {fps ? ` · ${(p.start_frame / fps).toFixed(1)}~${(p.end_frame / fps).toFixed(1)}초` : ''}
                      </div>
                      {!p.is_valid && p.exclude_reason && <div className="small muted">{p.exclude_reason.message}</div>}
                    </div>
                  </div>
                ))}
              </Card>
            )}

            {sh.status === 'DONE' && (
              <Card style={{ padding: '16px 18px 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <b style={{ fontSize: 15 }}>관절 각도 곡선</b>
                  {anglesQ.data && anglesQ.data.passes.length > 1 && (
                    <select className="input" style={{ height: 32, width: 'auto', fontSize: 13, padding: '0 8px' }} value={curve?.p.pass_no ?? ''} onChange={(e) => setPassNo(Number(e.target.value))}>
                      {anglesQ.data.passes.map((p) => (
                        <option key={p.pass_no} value={p.pass_no}>
                          {p.pass_no}회 통과
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                <div className="filters" style={{ padding: '10px 0 4px' }}>
                  {JOINTS.map((j) => (
                    <button key={j} type="button" className={`filter sm${joint === j ? ' on' : ''}`} onClick={() => setJoint(j)}>
                      {JOINT_LABEL[j]}
                    </button>
                  ))}
                </div>
                {anglesQ.isPending && <div className="skeleton" style={{ height: 120 }} />}
                {anglesQ.isError && <span className="small muted">{anglesQ.error instanceof ApiError ? anglesQ.error.message : '각도 자료가 아직 없어요'}</span>}
                {anglesQ.data && anglesQ.data.passes.length === 0 && <span className="small muted">유효 통과가 없어 각도 곡선이 없어요.</span>}
                {curve && (
                  <>
                    <svg viewBox="0 0 320 150" className="chart" aria-hidden="true">
                      <g stroke="#ECE8E2" strokeDasharray="3 4">
                        <line x1="24" y1="20" x2="320" y2="20" />
                        <line x1="24" y1="75" x2="320" y2="75" />
                        <line x1="24" y1="130" x2="320" y2="130" />
                      </g>
                      <g fontSize="10" fill="#A0A7B2">
                        <text x="0" y="24">{curve.max}°</text>
                        <text x="0" y="79">{Math.round((curve.max + curve.min) / 2)}°</text>
                        <text x="0" y="134">{curve.min}°</text>
                      </g>
                      <path d={curve.d} fill="none" stroke={curve.p.camera_side === 'LEFT' ? 'var(--left)' : 'var(--right)'} strokeWidth="2.2" strokeLinejoin="round" />
                    </svg>
                    <div className="small muted tabular">
                      {curve.p.pass_no}회 통과 · {CAMERA_SIDE_LABEL[curve.p.camera_side]} {JOINT_LABEL[joint]} · {curve.p.angles[joint].length}프레임. 관절점을 못 찾은 프레임은 선을 끊었어요.
                    </div>
                  </>
                )}
              </Card>
            )}

            <Spec sh={sh} />
          </>
        )}
      </div>
    </div>
  )
}

function Spec({ sh }: { sh: ShotDetailOut }) {
  const items: [string, string][] = [
    ['해상도', sh.width && sh.height ? `${sh.width}×${sh.height}` : '—'],
    ['프레임', sh.fps ? `${sh.fps.toFixed(2)} fps` : '—'],
    ['길이', sh.duration_sec ? `${sh.duration_sec.toFixed(1)}초` : '—'],
    ['비트레이트', sh.bitrate_kbps ? `${(sh.bitrate_kbps / 1000).toFixed(1)} Mbps` : '—'],
    ['코덱', sh.codec ?? '—'],
    ['모델', sh.model_name ? `${sh.model_name} ${sh.model_version ?? ''}` : '—'],
  ]
  return (
    <Card style={{ padding: '14px 18px' }}>
      <b style={{ fontSize: 14, display: 'block', marginBottom: 10 }}>입력 사양</b>
      <div className="spec-grid tabular">
        {items.map(([k, v]) => (
          <div key={k}>
            <div className="k">{k}</div>
            <div className="v">{v}</div>
          </div>
        ))}
      </div>
    </Card>
  )
}
