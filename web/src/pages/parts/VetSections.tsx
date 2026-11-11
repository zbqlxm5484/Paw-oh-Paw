// 수의사용 보고서의 추가 섹션(백엔드 보고서 시안 반영, S15P31A404-103, 보고서 그래프는 S15P31A404-208 연관)
import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { api, ApiError } from '../../api/client'
import { css } from '../../app/css'
import type { Account, Result } from '../../store/types'
import { sess_label } from '../../views/views'
import { ChangeProfile } from './ChangeProfile'
import { cmpFromServer, cmpLocal, GAIT_CODE, gaitsOf, kneeTrend, LIMBS, lrCompare, otherRows, type CmpRow, type CmpView } from '../../views/vet'

const BLUE = '#3B6FE0'
const ORANGE = '#D2601A'
const H2 = 'margin:0;font-size:18px;font-weight:800;letter-spacing:-0.3px'
const SUB = 'font-size:13px;color:#5B6472;line-height:1.5'

function Legend() {
  return (
    <div style={css('display:flex;gap:14px;font-size:12.5px;color:#5B6472')}>
      <span><span style={css(`display:inline-block;width:10px;height:10px;border-radius:3px;background:${BLUE};margin-right:5px`)}></span>왼쪽</span>
      <span><span style={css(`display:inline-block;width:10px;height:10px;border-radius:3px;background:${ORANGE};margin-right:5px`)}></span>오른쪽</span>
    </div>
  )
}

/** 1. 왼쪽과 오른쪽 비교: 관절마다 왼쪽·오른쪽 막대를 위아래로 */
function LrSection({ r }: { r: Result }) {
  const gaits = lrCompare(r)
  if (!gaits.length) return null
  return (
    <section className="rep-sec rep-pb" style={css('display:flex;flex-direction:column;gap:10px')}>
      <h2 style={css(H2)}>왼쪽과 오른쪽 비교</h2>
      <Legend />
      {gaits.map((g) => (
        <div key={g.gait} style={css('display:flex;flex-direction:column')}>
          <b style={css('font-size:13.5px;color:#5B6472;padding:8px 6px 6px;border-bottom:1px solid #ECE8E2;display:flex;justify-content:space-between')}><span>{g.gait}</span><span>좌우 차이</span></b>
          {g.rows.map((x) => (
            <div key={x.code} style={css(`display:grid;grid-template-columns:170px 1fr 64px;gap:14px;align-items:center;padding:10px 6px;border-bottom:1px solid #F2EFEA;background:${x.top ? '#FAF8F5' : 'transparent'}`)}>
              <div style={css('display:flex;flex-direction:column;gap:2px')}>
                <b style={css('font-size:15px')}>{x.n}</b>
                {x.top ? <span style={css('font-size:11.5px;font-weight:700;color:#1B2433')}>좌우 차이 가장 큼</span> : null}
              </div>
              <div style={css('display:flex;flex-direction:column;gap:6px')}>
                {([[x.wl, x.l, BLUE], [x.wr, x.r, ORANGE]] as const).map(([w, v, c], i) => (
                  <div key={i} style={css('display:flex;align-items:center;gap:8px')}>
                    <span style={css(`height:9px;border-radius:5px;background:${c};width:calc(${w}% - 50px);min-width:4px`)}></span>
                    <span style={css('font-size:12.5px;font-variant-numeric:tabular-nums;color:#3A4250')}>{v.toFixed(1)}°</span>
                  </div>
                ))}
              </div>
              <div style={css('text-align:right')}><b style={css('font-size:16px;font-variant-numeric:tabular-nums')}>{x.diff}</b></div>
            </div>
          ))}
        </div>
      ))}
    </section>
  )
}

const BADGE: Record<string, [string, string]> = {
  INCREASE: ['#1B2433', '#fff'], DECREASE: ['#1B2433', '#fff'], WITHIN_RANGE: ['#EEE8DF', '#3A4250'], RANGE_NOT_SET: ['#fff', '#5B6472'], UNKNOWN: ['#fff', '#5B6472'],
}

function badge(x: CmpRow): string {
  if (x.j === 'INCREASE') return `▲ ${x.diff.replace('-', '')}${x.u} 증가`
  if (x.j === 'DECREASE') return `▼ ${x.diff.replace('-', '')}${x.u} 감소`
  if (x.j === 'WITHIN_RANGE') return '범위 안'
  return '값만'
}

/** 한 줄: 지난 값 ○ → 이번 값 ●, 회색 띠 = 지난 값 ± 오차 범위 */
function CmpLine({ x, lo, hi }: { x: CmpRow; lo: number; hi: number }) {
  const p = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`
  const c = x.side === '왼쪽' ? BLUE : ORANGE
  const [bg, fg] = BADGE[x.j] ?? BADGE.UNKNOWN
  const a = Math.min(x.b, x.t)
  const b = Math.max(x.b, x.t)
  return (
    <div className="rep-cmp-row" style={css('display:grid;grid-template-columns:120px 1fr 150px 92px;gap:12px;align-items:center;padding:9px 6px;border-bottom:1px solid #F2EFEA')}>
      <span style={css('font-size:14.5px')}><b>{x.n}</b> <span style={css(`color:${c};font-size:13px;font-weight:600`)}>{x.side}</span></span>
      <div style={css('position:relative;height:18px')}>
        <span style={css('position:absolute;top:8px;left:0;right:0;height:2px;background:#F2EFEA')}></span>
        {x.tol != null ? <span style={css(`position:absolute;top:3px;height:12px;border-radius:6px;background:#ECE7DE;left:${p(x.b - x.tol)};width:calc(${p(x.b + x.tol)} - ${p(x.b - x.tol)})`)}></span> : null}
        <span style={css(`position:absolute;top:8px;height:2px;background:${c};left:${p(a)};width:calc(${p(b)} - ${p(a)})`)}></span>
        <span style={css(`position:absolute;top:3px;width:12px;height:12px;margin-left:-6px;border-radius:6px;background:#fff;border:2px solid #5B6472;left:${p(x.b)}`)}></span>
        <span style={css(`position:absolute;top:3px;width:12px;height:12px;margin-left:-6px;border-radius:6px;background:${c};left:${p(x.t)}`)}></span>
      </div>
      <span style={css('text-align:right;font-size:13.5px;font-variant-numeric:tabular-nums;color:#5B6472')}>{x.b.toFixed(1)}{x.u} → <b style={css('color:#1B2433')}>{x.t.toFixed(1)}{x.u}</b></span>
      <span style={css(`justify-self:end;height:24px;padding:0 9px;border-radius:12px;background:${bg};color:${fg};border:1px solid ${x.j === 'RANGE_NOT_SET' || x.j === 'UNKNOWN' ? '#D8D2C8' : bg};font-size:12px;font-weight:700;display:flex;align-items:center;white-space:nowrap`)}>{badge(x)}</span>
    </div>
  )
}

function CmpGroup({ title, note, rows, v }: { title: string; note?: string; rows: CmpRow[]; v: CmpView }) {
  if (!rows.length) return null
  return (
    <div style={css('display:flex;flex-direction:column')}>
      <b style={css('font-size:13.5px;color:#3A4250;padding:10px 0 6px;border-bottom:1px solid #ECE8E2')}>{title} <span style={css('color:#8E949C;font-weight:600')}>{rows.length}</span>{note ? <span style={css('font-weight:500;color:#8E949C;margin-left:8px;font-size:12px')}>{note}</span> : null}</b>
      {rows.map((x, i) => <CmpLine key={i} x={x} lo={v.lo} hi={v.hi} />)}
    </div>
  )
}

/** 2. 지난 측정과 비교 */
function CmpSection({ v, gait, base }: { v: CmpView | null | undefined; gait: string; base?: string }) {
  return (
    <section className="rep-sec rep-pb" style={css('display:flex;flex-direction:column;gap:8px')}>
      <h2 style={css(H2)}>지난 측정과 비교{v ? <span style={css('font-size:14px;font-weight:600;color:#5B6472;margin-left:8px')}>직전 회차({base || v.baseDate}) 대비 · {gait}</span> : null}</h2>
      {v === undefined ? <span style={css(SUB)}>불러오는 중…</span> : v === null ? <span style={css(SUB)}>비교할 직전 회차가 없습니다.</span> : (
        <>
          {v.modelChanged ? <span style={css(SUB)}>두 회차의 분석 모델이 달라 변화는 판단하지 않고 값만 적었습니다.</span> : null}
          <span style={css('font-size:12px;color:#8E949C')}>○ 지난 · ● 이번 · 회색 띠 = 오차 범위</span>
          <CmpGroup title="크게 달라진 값" rows={v.changed} v={v} />
          <CmpGroup title="범위 안" rows={v.within} v={v} />
          <CmpGroup title="값만(판정 기준 없음)" rows={v.valueOnly} v={v} />
        </>
      )}
    </section>
  )
}

/** 3. 무릎 가동 범위 변화 */
export function KneeTrend({ acct, r, gait }: { acct: Account; r: Result; gait: string }) {
  const t = kneeTrend(acct, r, gait)
  const W = 360, Hh = 150, x0 = 34, x1 = 306, y0 = 14, y1 = 120
  return (
    <section className="rep-sec" style={css('display:flex;flex-direction:column;gap:8px;min-width:0')}>
      <h2 style={css(H2)}>무릎 가동 범위 변화 <span style={css('font-size:13px;font-weight:600;color:#5B6472')}>{gait}</span></h2>
      {!t ? <span style={css(SUB)}>회차가 2개 이상이면 보여 드립니다.</span> : (() => {
        const X = (i: number) => x0 + (t.x.length === 1 ? 0 : (i * (x1 - x0)) / (t.x.length - 1))
        const Y = (v: number) => y1 - ((v - t.lo) / (t.hi - t.lo)) * (y1 - y0)
        const line = (vs: (number | null)[]) => vs.map((v, i) => (v == null ? null : `${X(i)},${Y(v)}`)).filter(Boolean).join(' ')
        const ticks = [t.lo, (t.lo + t.hi) / 2, t.hi]
        return (
          <>
            <Legend />
            <svg className="rep-trend2" viewBox={`0 0 ${W} ${Hh}`} style={css('width:100%;max-width:520px;display:block;font-family:inherit')}>
              {ticks.map((v, i) => <g key={i}><line x1={x0} x2={x1} y1={Y(v)} y2={Y(v)} stroke="#ECE8E2" strokeDasharray="3 4" /><text x={x0 - 6} y={Y(v) + 3} fontSize="9.5" fill="#8E949C" textAnchor="end">{Math.round(v)}</text></g>)}
              {t.x.map((d, i) => <text key={i} x={X(i)} y={Hh - 12} fontSize="9.5" fill="#8E949C" textAnchor="middle">{d}</text>)}
              {([[t.l, BLUE], [t.r, ORANGE]] as const).map(([vs, c], k) => (
                <g key={k}>
                  <polyline points={line(vs)} fill="none" stroke={c} strokeWidth="2.2" strokeLinejoin="round" />
                  {vs.map((v, i) => (v == null ? null : <circle key={i} cx={X(i)} cy={Y(v)} r={i === vs.length - 1 ? 4.5 : 3.2} fill={i === vs.length - 1 ? c : '#fff'} stroke={c} strokeWidth="2" />))}
                  {vs[vs.length - 1] != null ? <text x={X(vs.length - 1) + 7} y={Y(vs[vs.length - 1]!) + 4} fontSize="10" fontWeight="700" fill="#1B2433">{vs[vs.length - 1]!.toFixed(1)}°</text> : null}
                </g>
              ))}
            </svg>
          </>
        )
      })()}
    </section>
  )
}

/** 4. 그 밖의 수치 */
export function OtherTable({ r, gait }: { r: Result; gait: string }) {
  const rows = otherRows(r, gait)
  if (!rows.length) return null
  return (
    <section className="rep-sec" style={css('display:flex;flex-direction:column;gap:8px;min-width:0')}>
      <h2 style={css(H2)}>그 밖의 수치 <span style={css('font-size:13px;font-weight:600;color:#5B6472')}>{gait}</span></h2>
      <div style={css('font-size:13.5px;font-variant-numeric:tabular-nums')}>
        <div style={css('display:grid;grid-template-columns:1.8fr repeat(4,1fr);color:#5B6472;font-size:12.5px;padding:6px 0;border-bottom:1px solid #ECE8E2')}><span></span>{LIMBS.map(([, n]) => <span key={n} style={css('text-align:right')}>{n}</span>)}</div>
        {rows.map((row) => (
          <div key={row.n} style={css('display:grid;grid-template-columns:1.8fr repeat(4,1fr);padding:9px 0;border-bottom:1px solid #F2EFEA')}><span>{row.n}</span>{row.v.map((x, i) => <span key={i} style={css('text-align:right')}>{x}</span>)}</div>
        ))}
      </div>
    </section>
  )
}

/** 수의사용 추가 섹션 전체. fromServer 면 지난 측정 비교를 백엔드 비교 API(15.8)로 받는다 */
/** 대표 보행: 결과가 고른 보행, 없으면 마지막(속보 쪽) */
export function mainGait(r: Result): string {
  const gaits = gaitsOf(r).map(([g]) => g)
  return r.gait && gaits.includes(r.gait) ? r.gait : gaits[gaits.length - 1] ?? '속보'
}

export function VetSections({ acct, r, fromServer, knee, onReady }: { acct: Account; r: Result; fromServer: boolean; knee?: ReactNode; onReady?: () => void }) {
  const gait = mainGait(r)
  const [cmp, setCmp] = useState<CmpView | null | undefined>(() => (fromServer ? undefined : cmpLocal(acct, r, gait)))
  useEffect(() => {
    if (!fromServer) return
    let alive = true
    api.compare(r.dog, 'PREVIOUS', r.id, GAIT_CODE[gait])
      .then((o) => alive && setCmp(cmpFromServer(o, GAIT_CODE[gait] ?? 'TROT')))
      .catch((e) => {
        if (!alive) return
        // 비교 API 가 없는 서버(404 NOT_FOUND)면 이 브라우저에서 계산, 직전 회차가 없으면(400 COMPARE_INVALID) 비교 없음
        setCmp(e instanceof ApiError && e.code === 'NOT_FOUND' ? cmpLocal(acct, r, gait) : null)
      })
    return () => {
      alive = false
    }
  }, [acct, r, gait, fromServer])
  // 인쇄 전용 화면: 비교 값을 다 받은 뒤(서버 회차) 또는 바로(브라우저 계산) 다 그렸다고 알린다
  // (서버 회차는 비교 API 응답이 오기 전까지 cmp 가 undefined. 브라우저 계산은 직전 회차가 없으면 undefined 여도 다 그린 것)
  // 기준 회차 대비 변화 프로필(ChangeProfile)도 값을 받은 뒤에 준비 완료
  const [profDone, setProfDone] = useState(false)
  const profSettled = useCallback(() => setProfDone(true), [])
  const loading = (fromServer && cmp === undefined) || !profDone
  useEffect(() => {
    if (!loading) onReady?.()
  }, [loading, onReady])
  return (
    <div style={css('display:flex;flex-direction:column;gap:28px')}>
      {/* 인쇄(A4): 1쪽 끝 = 측정 품질(Report.tsx), 2쪽 = 좌우 비교·뒷무릎 각도(이번 회차), 3쪽 = 지난 측정과 비교·무릎 가동 범위 변화(시간에 따른 변화).
          그 밖의 수치(걸음 길이·입각기·발 들림)는 첫 쪽 다리별 수치와 겹치고 검증이 덜 돼 수의사용 화면에서 뺐다(OtherTable 은 남겨 둔다) */}
      <LrSection r={r} />
      {knee}
      <CmpSection v={cmp} gait={gait} base={(() => { const b = cmp && cmp.baseId ? acct.results.find((x) => x.id === cmp.baseId) : undefined; return b ? sess_label(acct, b, r) : undefined })()} />
      <ChangeProfile acct={acct} r={r} gait={gait} fromServer={fromServer} onSettled={profSettled} />
      <KneeTrend acct={acct} r={r} gait={gait} />
    </div>
  )
}
