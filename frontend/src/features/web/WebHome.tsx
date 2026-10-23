import { useDeferredValue, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { useDogSessions, useDogs, useUpdateDog } from '../../api/dogs'
import { LIMB_LABEL, PAIR_LABEL, SESSION_STATUS_LABEL, SESSION_STATUS_TONE, SEX_LABEL, SIZE_LABEL, dogDesc, fmtDate, fmtMetric, fmtMonthDay, metricLabel } from '../../api/labels'
import { useAllSessions, useSessionResult } from '../../api/results'
import type { DogOut, SessionHistoryItem } from '../../api/types'
import { useAuth } from '../../app/auth'
import { useToast } from '../../app/toast'
import { Icon } from '../../components/Icon'
import { Badge } from '../../components/ui'
import { DogStrip } from './DogStrip'

/** 웹 v2 홈: 기관·검색 → 반려견 띠 → 선택한 반려견 요약 · 최근 회차 · 측정 이력 표, 오른쪽에 최근 분석. */
export function WebHome() {
  const { staff } = useAuth()
  const nav = useNavigate()
  const toast = useToast()
  const [sp, setSp] = useSearchParams()
  const [q, setQ] = useState('')
  const dq = useDeferredValue(q.trim())
  const dogsQ = useDogs({ size: 100 })
  const all = useAllSessions(dogsQ.data?.items)

  const dogs = dogsQ.data?.items ?? []
  const shown = dq ? dogs.filter((d) => d.name.includes(dq)) : dogs
  const selId = sp.get('dog') ?? shown[0]?.id ?? dogs[0]?.id
  const dog = dogs.find((d) => d.id === selId) ?? shown[0]
  const recent = useMemo(() => [...all.items].sort((a, b) => b.measured_on.localeCompare(a.measured_on)).slice(0, 6), [all.items])

  return (
    <main className="web-main">
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--sub)' }}>{staff?.institution.name ?? '기관'}</span>
          <h1 className="web-h1">{staff ? `${staff.name} 담당자` : ''}</h1>
        </div>
        <label className="search" style={{ width: 320, maxWidth: '100%' }}>
          <Icon name="search" size={20} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="반려견 이름 검색" maxLength={50} aria-label="반려견 이름 검색" />
        </label>
      </div>

      <div style={{ display: 'flex', gap: 24, alignItems: 'stretch', flexWrap: 'wrap' }}>
        <aside className="web-card" style={{ order: 2, flex: 'none', width: 280, maxWidth: '100%', padding: '8px 18px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 0 8px' }}>
            <b style={{ fontSize: 16 }}>최근 분석</b>
            <button type="button" className="text-btn" style={{ color: 'var(--sub)', fontSize: 13.5, fontWeight: 500 }} onClick={() => nav('/results')}>
              전체 보기 ›
            </button>
          </div>
          {recent.map((r, i) => (
            <button
              type="button"
              key={r.id}
              className="row-item"
              style={{ borderTop: i ? '1px solid var(--line2)' : 'none', borderBottom: 0, padding: '13px 0' }}
              onClick={() => nav(r.status === 'DONE' ? `/sessions/${r.id}/result` : `/sessions/${r.id}`)}
            >
              <div className="avatar" style={{ width: 36, height: 36, fontSize: 14 }}>
                {r.dog.name.charAt(0)}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 15, fontWeight: 700 }}>{r.dog.name}</div>
                <div className="small muted tabular">{fmtMonthDay(r.measured_on)}</div>
              </div>
              <Badge tone={SESSION_STATUS_TONE[r.status]}>{SESSION_STATUS_LABEL[r.status]}</Badge>
            </button>
          ))}
          {!all.isPending && recent.length === 0 && <div style={{ fontSize: 14, color: 'var(--sub)', padding: '4px 0 14px' }}>아직 분석 기록이 없어요.</div>}
        </aside>

        <div style={{ flex: '1 1 560px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 24 }}>
          <DogStrip dogs={shown} selectedId={dog?.id ?? null} onPick={(id) => id && setSp({ dog: id })} onAdd={() => nav('/dogs/new')} showMeta />
          {dq && shown.length === 0 && <div style={{ fontSize: 15, color: 'var(--sub)', padding: '0 6px' }}>‘{dq}’ 이름의 반려견이 없어요.</div>}
          {dogsQ.isSuccess && dogs.length === 0 && (
            <div className="web-card" style={{ padding: '40px 32px', display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 12 }}>
              <b style={{ fontSize: 22, letterSpacing: -0.5 }}>첫 반려견을 등록해 주세요</b>
              <span style={{ fontSize: 15, color: 'var(--sub)' }}>이름·견종·체중만 있으면 바로 보행 측정을 시작할 수 있어요.</span>
              <button type="button" className="web-btn pri" style={{ marginTop: 6 }} onClick={() => nav('/dogs/new')}>
                반려견 등록하기
              </button>
            </div>
          )}
          {dog && <DogPanel dog={dog} onToast={toast} />}
        </div>
      </div>
    </main>
  )
}

function DogPanel({ dog, onToast }: { dog: DogOut; onToast: (m: string) => void }) {
  const nav = useNavigate()
  const histQ = useDogSessions(dog.id)
  const update = useUpdateDog(dog.id)
  const hist = histQ.data?.items ?? []
  const latestDone = hist.find((h) => h.status === 'DONE')
  const latest = hist[0]
  const resQ = useSessionResult(latestDone?.id)
  const res = resQ.data
  const G = res?.gaits.find((g) => g.gait_type === 'TROT') ?? res?.gaits[0]
  const top = G?.limb_compare.find((c) => c.comparable)
  const stifle = G?.limb_compare.find((c) => c.metric_code === 'rom_stifle')
  const stride = G?.limb_compare.find((c) => c.metric_code === 'stride_length' && c.pair === 'HIND')
  const baseline = hist.find((h) => h.is_baseline)
  const doneCount = hist.filter((h) => h.status === 'DONE').length
  const no = (h: SessionHistoryItem) => hist.length - hist.findIndex((x) => x.id === h.id)

  async function setBase(h: SessionHistoryItem) {
    try {
      await update.mutateAsync({ baseline_session_id: h.id })
      histQ.refetch()
      onToast(`${fmtMonthDay(h.measured_on)} 회차를 기준으로 정했어요`)
    } catch (e) {
      onToast(e instanceof Error ? e.message : '기준 회차를 바꾸지 못했어요')
    }
  }

  const cells: [string, string, string?][] = [
    ['체급', `${SIZE_LABEL[dog.size_class]} · ${dog.size_class_manual ? '직접 지정' : '자동 분류'}`],
    ['성별', dog.sex ? SEX_LABEL[dog.sex] : '미입력'],
    ['재활 시작일', dog.rehab_start_date ? fmtDate(dog.rehab_start_date) : '미입력'],
    ['관심 다리', dog.focus_limb ? LIMB_LABEL[dog.focus_limb] : '미선택'],
    ['기준 회차', baseline ? `${fmtMonthDay(baseline.measured_on)} · ${no(baseline)}회차` : '없음', dog.baseline_session_id ? undefined : baseline ? '가장 이른 회차로 자동 지정' : undefined],
  ]

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 280px', minWidth: 0 }}>
          <div style={{ fontSize: 30, lineHeight: 1.3, fontWeight: 800, letterSpacing: -0.7 }}>{dog.name}</div>
          <div style={{ fontSize: 14.5, color: 'var(--sub)', marginTop: 4 }}>{dogDesc(dog)}</div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button type="button" className="web-btn" style={{ height: 40 }} onClick={() => nav(`/dogs/${dog.id}/edit`)}>
            정보 수정
          </button>
          <button type="button" className="web-btn" style={{ height: 40 }} onClick={() => (doneCount < 2 ? onToast('완료된 회차가 2개 이상 있어야 비교할 수 있어요') : nav(`/dogs/${dog.id}/compare`))}>
            경과 비교
          </button>
          <button type="button" className="web-btn pri" style={{ height: 40 }} onClick={() => nav(dog.open_session_id ? `/sessions/${dog.open_session_id}` : `/capture?dog=${dog.id}`)}>
            <Icon name="cam" size={18} />
            {dog.open_session_id ? '이어서 측정' : '영상 올리기'}
          </button>
        </div>
      </div>

      <div className="web-card" style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px 20px' }}>
          {cells.map(([k, v, sub]) => (
            <div key={k} style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
              <span style={{ fontSize: 13, color: 'var(--sub)', fontWeight: 600 }}>{k}</span>
              <b className="tabular" style={{ fontSize: 16 }}>
                {v}
              </b>
              {sub && <span style={{ fontSize: 12, color: 'var(--dim)' }}>{sub}</span>}
            </div>
          ))}
        </div>
        <div style={{ borderTop: '1px solid var(--line2)', paddingTop: 14, display: 'flex', gap: 16, alignItems: 'baseline', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, color: 'var(--sub)', fontWeight: 600, flex: 'none' }}>내부 메모</span>
          <span style={{ flex: '1 1 240px', fontSize: 14.5, lineHeight: 1.55 }}>{dog.memo || '없음'}</span>
          <span style={{ fontSize: 12, color: 'var(--dim)' }}>보고서에는 넣지 않아요</span>
        </div>
      </div>

      {latest && latest.status === 'FAILED' && !latestDone && (
        <div className="web-card" style={{ padding: 28, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <b style={{ fontSize: 18 }}>최근 회차를 분석하지 못했어요</b>
            <Badge tone="bad">실패</Badge>
          </div>
          <span style={{ fontSize: 15, lineHeight: 1.6, color: 'var(--sub)' }}>쓸 수 있는 통과가 없었어요. 뛰지 않고, 멈추거나 앉지 않고, 일직선으로 걷도록 다시 찍어 올려 주세요.</span>
          <button type="button" className="web-btn pri" style={{ alignSelf: 'flex-start', marginTop: 4 }} onClick={() => nav(`/capture?dog=${dog.id}`)}>
            다시 올리기
          </button>
        </div>
      )}

      {latestDone && (
        <div className="web-card" style={{ padding: 26, display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <b style={{ fontSize: 16 }}>최근 회차</b>
              <span className="tabular" style={{ fontSize: 14, color: 'var(--sub)', marginLeft: 8 }}>
                {fmtMonthDay(latestDone.measured_on)} · {no(latestDone)}회차 · 체중 {latestDone.weight_kg ?? dog.weight_kg}kg
              </span>
            </div>
            <Badge tone="ok">완료</Badge>
          </div>
          {resQ.isPending && <div className="skeleton" style={{ height: 120 }} />}
          {resQ.isError && <span className="small muted">{resQ.error instanceof ApiError ? resQ.error.message : '회차 수치를 불러오지 못했어요'}</span>}
          {G && (
            <>
              <div className="web-kpis">
                <div className="web-kpi soft">
                  <div className="k">좌우 차이 지수</div>
                  <div className="v tabular">
                    {top?.symmetry_index != null ? top.symmetry_index.toFixed(1) : '—'}
                    <small>%</small>
                  </div>
                  <div className="d">{top ? `${PAIR_LABEL[top.pair]} ${metricLabel(top.metric_code)} · 낮을수록 대칭` : '비교 불가'}</div>
                </div>
                <div className="web-kpi soft">
                  <div className="k">뒷무릎 가동 범위 왼 / 오</div>
                  <div className="v tabular">
                    {stifle?.left != null ? stifle.left.toFixed(0) : '—'}
                    <span style={{ color: 'var(--dim)', fontWeight: 500 }}> / </span>
                    {stifle?.right != null ? stifle.right.toFixed(0) : '—'}
                    <small>°</small>
                  </div>
                  <div className="d">{stifle?.comparable ? `차이 ${fmtMetric(Math.abs(stifle.diff!), 'deg')}` : (stifle?.reason?.message ?? '측정 불가')}</div>
                </div>
                <div className="web-kpi soft">
                  <div className="k">걸음 길이 왼 / 오 (몸통 대비)</div>
                  <div className="v tabular">
                    {stride?.left != null ? stride.left.toFixed(0) : '—'}
                    <span style={{ color: 'var(--dim)', fontWeight: 500 }}> / </span>
                    {stride?.right != null ? stride.right.toFixed(0) : '—'}
                    <small>%</small>
                  </div>
                  <div className="d">{stride?.comparable ? `차이 ${fmtMetric(Math.abs(stride.diff!), 'pct_body')}p` : '비교 불가'}</div>
                </div>
              </div>
              <div style={{ background: 'var(--ink)', color: '#fff', borderRadius: 14, padding: '18px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
                  <span style={{ fontSize: 12.5, fontWeight: 700, color: '#F5B38A' }}>다리 비교 요약 · 속보</span>
                  <b style={{ fontSize: 18, letterSpacing: -0.4 }}>{top ? `${PAIR_LABEL[top.pair]} ${metricLabel(top.metric_code)}에서 좌우 차이가 가장 커요` : '양쪽을 모두 잰 수치가 없어요'}</b>
                  {top && (
                    <span className="tabular" style={{ fontSize: 13.5, color: 'rgba(255,255,255,.78)' }}>
                      왼 {fmtMetric(top.left, top.unit)} · 오 {fmtMetric(top.right, top.unit)} · 차이 {fmtMetric(Math.abs(top.diff!), top.unit)}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type="button" className="web-btn ghost" onClick={() => nav(`/sessions/${latestDone.id}/result`)}>
                    회차 결과 보기
                  </button>
                  <button type="button" className="web-btn pri" onClick={() => nav(`/sessions/${latestDone.id}/report`)}>
                    보고서
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      <div className="web-card web-table">
        <div className="tbl">
          <div className="ttitle">
            <b style={{ fontSize: 17 }}>
              측정 이력 <span style={{ color: 'var(--dim)', fontWeight: 600, fontSize: 15 }}>{hist.length}회차</span>
            </b>
          </div>
          <div className="thead" style={{ gridTemplateColumns: '1.1fr 1fr .9fr 1fr .8fr .8fr 1fr 1.2fr' }}>
            <span>회차</span>
            <span>측정일</span>
            <span>체중</span>
            <span>유효 통과</span>
            <span>모델</span>
            <span>보고서</span>
            <span>상태</span>
            <span />
          </div>
          {histQ.isError && <div style={{ padding: '28px 24px', fontSize: 15, color: 'var(--sub)' }}>{histQ.error instanceof ApiError ? histQ.error.message : '측정 이력을 불러오지 못했어요'}</div>}
          {hist.map((h) => (
            <button type="button" key={h.id} className="trow tabular" style={{ gridTemplateColumns: '1.1fr 1fr .9fr 1fr .8fr .8fr 1fr 1.2fr' }} onClick={() => nav(h.status === 'DONE' ? `/sessions/${h.id}/result` : `/sessions/${h.id}`)}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <b>{no(h)}회차</b>
                {h.is_baseline && <span className="mini-badge dark">기준</span>}
              </span>
              <span style={{ color: 'var(--sub)' }}>{fmtMonthDay(h.measured_on)}</span>
              <span>{h.weight_kg ?? '-'}kg</span>
              <span>
                왼 {h.valid_passes.LEFT} · 오 {h.valid_passes.RIGHT}
              </span>
              <span>{h.model_version ?? '-'}</span>
              <span>{h.reports ? (h.reports.OWNER === 'DONE' || h.reports.VET === 'DONE' ? '있음' : '만드는 중') : '-'}</span>
              <span>
                <Badge tone={SESSION_STATUS_TONE[h.status]}>{SESSION_STATUS_LABEL[h.status]}</Badge>
              </span>
              <span style={{ textAlign: 'right' }}>
                {h.status === 'DONE' && !h.is_baseline && (
                  <span
                    role="button"
                    tabIndex={0}
                    style={{ fontSize: 13, fontWeight: 700, color: 'var(--pri-d)', padding: '6px 0' }}
                    onClick={(e) => {
                      e.stopPropagation()
                      setBase(h)
                    }}
                    onKeyDown={(e) => e.key === 'Enter' && setBase(h)}
                  >
                    기준 회차로 지정
                  </span>
                )}
              </span>
            </button>
          ))}
          {histQ.isSuccess && hist.length === 0 && <div style={{ padding: '28px 24px', fontSize: 15, color: 'var(--sub)' }}>아직 측정 기록이 없어요.</div>}
        </div>
      </div>
    </section>
  )
}
