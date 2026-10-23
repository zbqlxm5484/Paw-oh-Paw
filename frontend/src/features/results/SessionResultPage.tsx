import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { GAIT_LABEL, PAIR_LABEL, SESSION_STATUS_LABEL, SESSION_STATUS_TONE, fmtMetric, fmtMonthDay, metricLabel, pairOf } from '../../api/labels'
import { useSession } from '../../api/sessions'
import { useSessionResult } from '../../api/results'
import type { GaitResultOut, GaitType, LimbCompareOut, MetricOut, SessionResultOut } from '../../api/types'
import { Icon } from '../../components/Icon'
import { Badge, Button, Card, Empty, TopBar } from '../../components/ui'
import './results.css'

/** 지표 표에 올릴 수치와 순서(api-spec 10.4 표 순서 중 다리가 있는 것). 뒷다리 → 앞다리 묶음. */
const HIND_CODES = ['rom_stifle', 'rom_hip', 'rom_tarsus', 'stride_length', 'stance_ratio', 'paw_lift', 'paw_excursion', 'stifle_cv']
const FORE_CODES = ['rom_elbow', 'rom_shoulder', 'rom_carpus', 'stride_length', 'stance_ratio', 'paw_lift', 'paw_excursion']

interface Row {
  code: string
  pair: 'FORE' | 'HIND'
  left: MetricOut | undefined
  right: MetricOut | undefined
}

function rowsOf(g: GaitResultOut): Row[] {
  const find = (code: string, limb: string) => g.metrics.find((m) => m.metric_code === code && m.limb === limb)
  const out: Row[] = []
  for (const code of HIND_CODES) {
    const l = find(code, 'LH')
    const r = find(code, 'RH')
    if (l || r) out.push({ code, pair: 'HIND', left: l, right: r })
  }
  for (const code of FORE_CODES) {
    const l = find(code, 'LF')
    const r = find(code, 'RF')
    if (l || r) out.push({ code, pair: 'FORE', left: l, right: r })
  }
  return out
}

/**
 * S5 회차 결과. 디자인 v5 `detail`. 수치는 GET /sessions/{id}/result 그대로, 0 으로 그리지 않고 "측정 불가 + 사유".
 * 디자인의 "대칭 지수"(높을수록 좋음)는 API 의 symmetry_index(좌우 차이 비율, 낮을수록 대칭)와 뜻이 반대라 "좌우 차이 지수"로 쓴다(screenPlan 6절 #3).
 */
export function SessionResultPage() {
  const { sessionId } = useParams()
  const nav = useNavigate()
  const sessQ = useSession(sessionId)
  const resQ = useSessionResult(sessQ.data?.status === 'DONE' ? sessionId : undefined)
  const [gait, setGait] = useState<GaitType | null>(null)

  const s = sessQ.data
  const res = resQ.data
  const gaits = res?.gaits ?? []
  const curGait = gait && gaits.some((g) => g.gait_type === gait) ? gait : (gaits.find((g) => g.gait_type === 'TROT') ?? gaits[0])?.gait_type ?? null
  const G = gaits.find((g) => g.gait_type === curGait)
  const rows = useMemo(() => (G ? rowsOf(G) : []), [G])

  if (sessQ.isError) {
    return (
      <div className="screen">
        <TopBar title="회차 결과" />
        <div className="screen-body">
          <Empty>{sessQ.error instanceof ApiError ? sessQ.error.message : '회차를 불러오지 못했어요'}</Empty>
        </div>
      </div>
    )
  }
  if (!s) {
    return (
      <div className="screen">
        <TopBar title="회차 결과" />
        <div className="screen-body">
          <div className="skeleton" style={{ height: 80 }} />
          <div className="skeleton" style={{ height: 220 }} />
        </div>
      </div>
    )
  }

  // 집계 전·실패는 측정 화면이 보여 준다
  if (s.status !== 'DONE') {
    nav(`/sessions/${s.id}`, { replace: true })
    return null
  }

  const when = `${fmtMonthDay(s.measured_on)} · 체중 ${s.weight_kg ?? s.dog.weight_kg}kg`
  const top = G?.limb_compare.find((c) => c.comparable)
  const invalidShots = res ? res.shot_counts.invalid + res.shot_counts.failed : 0

  return (
    <div className="screen">
      <TopBar title="회차 결과" onBack={() => nav(`/dogs/${s.dog_id}`)} />
      <div className="scroll screen-body" style={{ gap: 12, paddingTop: 4 }}>
        <div className="res-head">
          <div style={{ minWidth: 0 }}>
            <div className="res-name">{s.dog.name}</div>
            <div className="res-when tabular">{when}</div>
          </div>
          <Badge tone={SESSION_STATUS_TONE[s.status]}>{SESSION_STATUS_LABEL[s.status]}</Badge>
        </div>

        {resQ.isPending && <div className="skeleton" style={{ height: 220 }} />}
        {resQ.isError && <Empty>{resQ.error instanceof ApiError ? resQ.error.message : '회차 수치를 불러오지 못했어요'}</Empty>}

        {res && G && (
          <>
            {res.notices.map((n) => (
              <div key={n.code} className="note-warn">
                {n.message}
              </div>
            ))}
            {invalidShots > 0 && !res.notices.length && (
              <div className="note-warn">촬영 {res.shot_counts.total}건 중 {invalidShots}건은 쓰지 못했어요. 유효 통과만으로 수치를 냈어요.</div>
            )}

            <Kpis res={res} G={G} />

            <div className="dark-card">
              <span className="eyebrow">다리 비교 요약 · {GAIT_LABEL[G.gait_type]}</span>
              {top ? (
                <>
                  <b className="title">
                    {PAIR_LABEL[top.pair]} {metricLabel(top.metric_code)}에서 좌우 차이가 가장 커요
                  </b>
                  <span className="sub tabular">
                    왼 {fmtMetric(top.left, top.unit)} · 오 {fmtMetric(top.right, top.unit)} · 차이 {fmtMetric(top.diff == null ? null : Math.abs(top.diff), top.unit)}
                    {top.symmetry_index != null ? ` · 좌우 차이 지수 ${top.symmetry_index.toFixed(1)}%` : ''}
                  </span>
                </>
              ) : (
                <b className="title">양쪽을 모두 잰 수치가 없어 좌우를 비교하지 못했어요</b>
              )}
              <hr />
              {G.limb_compare.slice(top ? 1 : 0, top ? 4 : 3).map((c) => (
                <RankRow key={`${c.pair}:${c.metric_code}`} c={c} />
              ))}
              {G.limb_compare
                .filter((c) => !c.comparable)
                .slice(0, 2)
                .map((c) => (
                  <RankRow key={`na:${c.pair}:${c.metric_code}`} c={c} />
                ))}
              <span className="foot">진단이 아닌 좌우 차이 비교예요.</span>
            </div>

            {gaits.length > 1 && (
              <div className="seg" style={{ gridTemplateColumns: `repeat(${gaits.length}, 1fr)` }}>
                {gaits.map((g) => (
                  <button key={g.gait_type} type="button" className={g.gait_type === G.gait_type ? 'on' : ''} onClick={() => setGait(g.gait_type)}>
                    {GAIT_LABEL[g.gait_type]}
                  </button>
                ))}
              </div>
            )}

            <div className="table">
              <div className="thead">
                <span>지표</span>
                <span>왼쪽</span>
                <span>오른쪽</span>
                <span>차이</span>
              </div>
              {(['HIND', 'FORE'] as const).map((pair) => {
                const list = rows.filter((r) => r.pair === pair)
                if (!list.length) return null
                return (
                  <div key={pair}>
                    <div className="sec">{PAIR_LABEL[pair]}</div>
                    {list.map((r) => {
                      const l = r.left
                      const rr = r.right
                      const ok = l?.measurable && rr?.measurable
                      if (ok)
                        return (
                          <div className="tr tabular" key={r.code}>
                            <span>{metricLabel(r.code)}</span>
                            <span>{fmtMetric(l!.value, l!.unit)}</span>
                            <span>{fmtMetric(rr!.value, rr!.unit)}</span>
                            <span>{fmtMetric(Math.abs(l!.value! - rr!.value!), l!.unit)}</span>
                          </div>
                        )
                      const reason = (!l?.measurable ? l?.unmeasurable_reason : rr?.unmeasurable_reason)?.message ?? '한쪽 다리를 재지 못했어요'
                      const side = !l?.measurable && !rr?.measurable ? '' : !l?.measurable ? '왼쪽 ' : '오른쪽 '
                      return (
                        <div className="tr na" key={r.code}>
                          <span>{metricLabel(r.code)}</span>
                          <span>
                            {side}측정 불가 · {reason}
                            {side && (l?.measurable || rr?.measurable) ? ` (${l?.measurable ? '왼' : '오'} ${fmtMetric((l?.measurable ? l : rr)!.value, (l ?? rr)!.unit)})` : ''}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                )
              })}
              <div className="tfoot">거리 수치는 cm 가 아니라 몸통 길이 대비 %예요.</div>
            </div>

            <WholeBody G={G} />

            <Card style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 12 }}>
              <b style={{ fontSize: 15 }}>통과 집계</b>
              <div className="counts tabular">
                <div>
                  <div className="k">측정</div>
                  <div className="v">{res.pass_counts.measured}</div>
                </div>
                <div>
                  <div className="k">사용</div>
                  <div className="v">{res.pass_counts.used}</div>
                </div>
                <div>
                  <div className="k">제외</div>
                  <div className="v">{res.pass_counts.excluded}</div>
                </div>
              </div>
              {res.exclude_summary.length > 0 && (
                <div className="chips">
                  {res.exclude_summary.map((e) => (
                    <span key={e.code} className="chip tabular">
                      {e.message.replace(/\..*$/, '')} {e.count}회
                    </span>
                  ))}
                </div>
              )}
              <span className="small muted">
                촬영 {res.shot_counts.total}건 · 실패 {res.shot_counts.failed} · 무효 {res.shot_counts.invalid}.{' '}
                <button type="button" className="text-btn" style={{ padding: 0, fontSize: 13 }} onClick={() => nav(`/sessions/${s.id}/shots`)}>
                  촬영별 결과 보기
                </button>
              </span>
            </Card>

            <span className="small muted" style={{ lineHeight: 1.5, padding: '2px 2px 0' }}>
              분석 모델 {res.model_name ?? '-'} {res.model_version ?? ''} · 보행 평가 보조 자료이며 진단을 대신하지 않습니다.
            </span>
          </>
        )}
      </div>
      {res && (
        <div className="sticky-footer footer-2">
          <Button variant="secondary" onClick={() => nav(`/dogs/${s.dog_id}/compare?target=${s.id}`)}>
            경과 비교
          </Button>
          <Button onClick={() => nav(`/sessions/${s.id}/report`)}>
            <Icon name="doc" size={20} />
            보고서 보기
          </Button>
        </div>
      )}
    </div>
  )
}

function Kpis({ res, G }: { res: SessionResultOut; G: GaitResultOut }) {
  const top = G.limb_compare.find((c) => c.comparable)
  const stifle = G.limb_compare.find((c) => c.metric_code === 'rom_stifle')
  const stride = G.limb_compare.find((c) => c.metric_code === 'stride_length' && c.pair === 'HIND') ?? G.limb_compare.find((c) => c.metric_code === 'stride_length')
  const strideDiff = stride?.comparable ? `${stride.left! > stride.right! ? '오른쪽' : stride.left! < stride.right! ? '왼쪽' : ''}${stride.left === stride.right ? '좌우 같음' : `이 ${fmtMetric(Math.abs(stride.diff!), stride.unit)}p 짧음`}` : '비교 불가'
  void res
  return (
    <div className="kpi-grid tabular">
      <div className="kpi">
        <div className="k">좌우 차이 지수</div>
        <div className="v">
          {top?.symmetry_index != null ? top.symmetry_index.toFixed(1) : '—'}
          <small>%</small>
        </div>
        <div className="d">{top ? `${PAIR_LABEL[top.pair]} ${metricLabel(top.metric_code)} · 낮을수록 대칭` : '비교 불가'}</div>
      </div>
      <div className="kpi">
        <div className="k">뒷무릎 가동 왼/오</div>
        <div className="v" style={{ fontSize: 19, marginTop: 6 }}>
          {stifle?.left != null ? stifle.left.toFixed(0) : '—'}
          <span style={{ color: 'var(--dim)', fontWeight: 500 }}> / </span>
          {stifle?.right != null ? stifle.right.toFixed(0) : '—'}
          <small>°</small>
        </div>
        <div className="d">{stifle?.comparable ? `차이 ${fmtMetric(Math.abs(stifle.diff!), 'deg')}` : (stifle?.reason?.message ?? '측정 불가')}</div>
      </div>
      <div className="kpi">
        <div className="k">걸음 길이 왼/오</div>
        <div className="v" style={{ fontSize: 19, marginTop: 6 }}>
          {stride?.left != null ? stride.left.toFixed(0) : '—'}
          <span style={{ color: 'var(--dim)', fontWeight: 500 }}> / </span>
          {stride?.right != null ? stride.right.toFixed(0) : '—'}
          <small>%</small>
        </div>
        <div className="d">{strideDiff}</div>
      </div>
    </div>
  )
}

function RankRow({ c }: { c: LimbCompareOut }) {
  return (
    <div className="rank tabular">
      <span className="n">
        {PAIR_LABEL[c.pair]} · {metricLabel(c.metric_code)}
      </span>
      {c.comparable ? <span className="v">차이 {fmtMetric(Math.abs(c.diff!), c.unit)}</span> : <span className="v na">비교 불가{c.reason ? ` · ${c.reason.message.replace(/\.$/, '')}` : ''}</span>}
    </div>
  )
}

/** 다리 구분이 없는 수치(보행 속도, 보행 주기 수) */
function WholeBody({ G }: { G: GaitResultOut }) {
  const whole = G.metrics.filter((m) => m.limb === 'NONE')
  if (!whole.length) return null
  return (
    <Card style={{ padding: '14px 18px', display: 'flex', gap: 16 }}>
      {whole.map((m) => (
        <div key={m.metric_code} style={{ flex: 1 }}>
          <div className="small muted" style={{ fontWeight: 600 }}>
            {metricLabel(m.metric_code)}
          </div>
          <div className="tabular" style={{ fontSize: 18, fontWeight: 700, marginTop: 2 }}>
            {m.measurable ? fmtMetric(m.value, m.unit) : '측정 불가'}
          </div>
          {!m.measurable && m.unmeasurable_reason && <div className="small muted">{m.unmeasurable_reason.message}</div>}
        </div>
      ))}
    </Card>
  )
}

export { pairOf }
