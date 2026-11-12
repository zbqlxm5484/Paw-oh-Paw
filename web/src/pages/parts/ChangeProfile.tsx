// 기준 회차 대비 변화 프로필(QA 2절, S15P31A404-285). 수의사용 보고서·경과 비교 화면이 같이 쓴다.
// 관절·다리마다 '이번 − 기준' 가로 막대 + 오차 범위 회색 띠. 띠를 벗어난 관절만 색(증가 주황, 감소 남색), 범위 안은 회색,
// 판정할 수 없는 관절(통과 수 부족·범위 없음)은 흐린 막대 + '값만'. 관절별 작은 추이선은 GET /dogs/{id}/trends(로그인 화면에서만).
import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { css } from '../../app/css'
import type { Account, Result } from '../../store/types'
import { geom, gaitCode, JUDGE_LABEL, profileFromServer, profileLocal, type ProfileJudge, type ProfileView } from '../../views/changeProfile'

const COLOR: Record<ProfileJudge, string> = { INCREASE: '#D2601A', DECREASE: '#3A4250', WITHIN_RANGE: '#C9C3BA', VALUE_ONLY: '#C9C3BA' }
const CHIP: Record<ProfileJudge, [string, string]> = {
  INCREASE: ['#FCEEE3', '#A8481A'], DECREASE: ['#E9EBEE', '#3A4250'], WITHIN_RANGE: ['#F2EFEA', '#5B6472'], VALUE_ONLY: ['#fff', '#5B6472'],
}
const korDate = (iso: string) => {
  const [, m, d] = iso.split('-')
  return m && d ? `${Number(m)}월 ${Number(d)}일` : iso
}
const fmt = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(1)}°`

type Spark = Record<string, (number | null)[]> // `${code}|${limb}` → 오래된 회차부터 값

function Sparkline({ vals }: { vals: (number | null)[] }) {
  const pts = vals.map((v, i) => [i, v] as const).filter((p): p is readonly [number, number] => p[1] != null)
  if (pts.length < 2) return <span style={css('width:64px')}></span>
  const ys = pts.map((p) => p[1])
  const lo = Math.min(...ys), hi = Math.max(...ys), span = hi - lo || 1
  const X = (i: number) => 2 + (i * 60) / Math.max(1, vals.length - 1)
  const Y = (v: number) => 18 - ((v - lo) / span) * 14
  return (
    <svg viewBox="0 0 64 22" style={css('width:64px;height:22px;flex:none')} aria-hidden="true">
      <polyline points={pts.map(([i, v]) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ')} fill="none" stroke="#A0A7B2" strokeWidth="1.4" strokeLinejoin="round"></polyline>
      <circle cx={X(pts[pts.length - 1][0])} cy={Y(pts[pts.length - 1][1])} r="2.2" fill="#3A4250"></circle>
    </svg>
  )
}

/** 기준 회차 대비 변화 프로필. onSettled: 비교 값을 다 받았거나(또는 받을 수 없음이 정해졌을 때) 한 번 부른다(인쇄 준비 신호) */
export function ChangeProfile({ acct, r, gait, fromServer, onSettled, spark = true }: {
  acct: Account; r: Result; gait: string; fromServer: boolean; onSettled?: () => void; spark?: boolean
}) {
  const code = gaitCode(gait)
  const key = `${r.id}|${code}|${fromServer}`
  const [state, setState] = useState<{ key: string; v: ProfileView | null } | null>(() => (fromServer ? null : { key, v: profileLocal(acct, r, gait) }))
  const [sparks, setSparks] = useState<Spark>({})
  useEffect(() => {
    if (!fromServer) {
      setState({ key, v: profileLocal(acct, r, gait) })
      return
    }
    let alive = true
    api.compare(r.dog, 'BASELINE', r.id, code)
      .then((o) => alive && setState({ key, v: profileFromServer(o, code) }))
      .catch(() => alive && setState({ key, v: null })) // 기준 회차가 없거나 이번이 기준(400 COMPARE_INVALID)
    return () => {
      alive = false
    }
  }, [key, acct, r, gait, code, fromServer])
  const ready = state != null && state.key === key
  useEffect(() => {
    if (ready) onSettled?.()
  }, [ready, onSettled])

  // 관절별 작은 추이선(서버 회차, 로그인 화면에서만 — 인쇄 토큰으로는 trends 를 못 연다. 실패하면 선만 빠진다)
  const view = ready ? state!.v : null
  useEffect(() => {
    if (!spark || !fromServer || !view) return
    let alive = true
    const codes = [...new Set(view.rows.map((x) => x.code))]
    Promise.all(codes.map((c) => api.trends(r.dog, c, code).then((t) => [c, t] as const).catch(() => null))).then((res) => {
      if (!alive) return
      const out: Spark = {}
      for (const x of res) {
        if (!x) continue
        const [c, t] = x
        for (const s of t.series) {
          const pts = s.points.filter((p) => p.measured_on <= view.targetDate).slice(-8)
          out[`${c}|${s.limb}`] = pts.map((p) => (p.measurable ? p.value : null))
        }
      }
      setSparks(out)
    })
    return () => {
      alive = false
    }
  }, [spark, fromServer, view, r.dog, code])

  if (!ready) return null
  if (!view) {
    return (
      <section className="rep-sec" style={css('display:flex;flex-direction:column;gap:6px')}>
        <b style={css('font-size:18px;font-weight:800;letter-spacing:-0.3px')}>기준 회차 대비 변화</b>
        <span style={css('font-size:14px;color:#5B6472')}>기준 회차와 비교할 수 있게 되면 보여 드립니다.</span>
      </section>
    )
  }
  const showSpark = spark && fromServer && Object.keys(sparks).length > 0
  return (
    <section className="rep-sec" data-section="change-profile" style={css('display:flex;flex-direction:column;gap:10px')}>
      <div style={css('display:flex;align-items:baseline;gap:10px;flex-wrap:wrap')}>
        <b style={css('font-size:18px;font-weight:800;letter-spacing:-0.3px')}>기준 회차 대비 변화</b>
        <span style={css('font-size:13px;color:#5B6472')}>기준 {korDate(view.baseDate)} → 이번 {korDate(view.targetDate)} · {gait} · 관절 가동 범위</span>
      </div>
      <span style={css('font-size:13px;color:#5B6472;line-height:1.5')}>
        막대는 이번 값에서 기준 값을 뺀 크기예요. 회색 띠는 오차 범위(같은 상태를 다시 재도 생길 수 있는 차이)이고, 띠를 벗어난 관절만 색으로 표시했어요.
        {view.modelChanged ? ' 두 회차의 분석 방식이 달라 값만 적었어요.' : ''}
      </span>
      <div style={css('display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:#5B6472')}>
        <span><span style={css(`display:inline-block;width:12px;height:8px;border-radius:2px;background:${COLOR.INCREASE};margin-right:5px`)}></span>증가</span>
        <span><span style={css(`display:inline-block;width:12px;height:8px;border-radius:2px;background:${COLOR.DECREASE};margin-right:5px`)}></span>감소</span>
        <span><span style={css(`display:inline-block;width:12px;height:8px;border-radius:2px;background:${COLOR.WITHIN_RANGE};margin-right:5px`)}></span>범위 안</span>
        <span><span style={css('display:inline-block;width:12px;height:8px;border-radius:2px;background:#ECE8E2;margin-right:5px')}></span>오차 범위</span>
      </div>
      <div style={css('display:flex;flex-direction:column')}>
        {view.rows.map((x, i) => {
          const bar = geom(x.diff, view.scale)
          const band = x.tol != null ? geom(x.tol, view.scale) : null
          const faded = x.j === 'VALUE_ONLY'
          return (
            <div key={i} style={css(`display:grid;grid-template-columns:118px 1fr 92px 64px ${showSpark ? '64px' : '0px'};gap:10px;align-items:center;padding:7px 0;border-top:${i ? '1px solid #F2EFEA' : 'none'}`)}>
              <span style={css('font-size:14px;font-weight:600;white-space:nowrap')}>{x.joint} <span style={css('font-weight:500;color:#5B6472')}>{x.side}</span></span>
              <div style={css('position:relative;height:14px')} title={`기준 ${x.base}° → 이번 ${x.target}°`}>
                {band ? <span style={css(`position:absolute;top:0;bottom:0;left:${50 - band.width}%;width:${band.width * 2}%;background:#ECE8E2;border-radius:3px`)}></span> : null}
                <span style={css('position:absolute;top:-2px;bottom:-2px;left:50%;width:1px;background:#A0A7B2')}></span>
                <span style={css(`position:absolute;top:3px;height:8px;left:${bar.left}%;width:${Math.max(bar.width, 0.6)}%;background:${COLOR[x.j]};opacity:${faded ? 0.45 : 1};border-radius:2px`)}></span>
              </div>
              <span style={css('font-size:13px;font-weight:700;text-align:right;font-variant-numeric:tabular-nums')}>{fmt(x.diff)}</span>
              <span style={css(`justify-self:start;padding:2px 8px;border-radius:6px;font-size:12px;font-weight:700;background:${CHIP[x.j][0]};color:${CHIP[x.j][1]};border:${x.j === 'VALUE_ONLY' ? '1px solid #E2DCD3' : 'none'}`)}>{JUDGE_LABEL[x.j]}</span>
              {showSpark ? <Sparkline vals={sparks[`${x.code}|${x.limb}`] ?? []} /> : <span></span>}
            </div>
          )
        })}
      </div>
      {view.rows.some((x) => x.j === 'VALUE_ONLY') ? (
        <span style={css('font-size:12px;color:#5B6472')}>'값만'은 걸은 횟수가 모자라거나(다리마다 8번 미만) 오차 범위가 정해지지 않아 증가·감소를 가르지 않은 관절이에요.</span>
      ) : null}
    </section>
  )
}
