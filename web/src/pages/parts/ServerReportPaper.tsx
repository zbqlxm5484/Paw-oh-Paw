// 서버 보고서 내용(GET /sessions/{id}/report-content, 285)으로 그리는 보고서 종이. 인쇄 전용 화면(/print/reports/:rid)이 쓴다.
// 모양(레이아웃·색·몸 그림·다리 카드·대칭 막대·추세 그래프·수의사용 절)은 회차 결과 화면의 ReportPaper 와 같고,
// 글·표·숫자는 전부 서버 값이다(KPI-30 숫자 대조·KPI-31 금지 표현 검사를 통과한 것). 화면은 새 숫자나 문장을 만들지 않는다.
// 확정 전 칸(legs·baseline.diff·symmetry_level)이 없을 때만 views/reportContent.ts 가 서버의 다른 값으로 대신 정한다.
import { Fragment } from 'react'
import type { ReportContentChangeCell, ReportContentGait, ReportContentOut } from '../../api/client'
import { css } from '../../app/css'
import { staticUrl } from '../../app/page'
import { LIMB } from '../../config'
import { _svg } from '../../views/views'
import { KneeChart } from '../Report'
import {
  baselineDiff, isWeak, LEVEL_STYLE, legCard, legFills, paintBody, cardGait, pairViews, sizeCode, symLevel, trendPoints, type KneeChartView, type PairView,
} from '../../views/reportContent'

const H2 = 'margin:0;font-size:18px;font-weight:800;letter-spacing:-0.3px'
const SUB = 'font-size:13px;color:#5B6472;line-height:1.5'
const GAIT_ORDER = ['TROT', 'WALK', 'OTHER']
const LIMB_ORDER = ['LF', 'RF', 'LH', 'RH', 'NONE']
const LIMB_NAME: Record<string, string> = { ...LIMB, NONE: '전체' }

function LegCard({ c, gait, pv, limb, align }: { c: ReportContentOut; gait: ReportContentGait | null; pv: Record<'FORE' | 'HIND', PairView>; limb: string; align: 'l' | 'r' }) {
  const weak = isWeak(pv, limb)
  const v = pv[limb.endsWith('F') ? 'FORE' : 'HIND']
  const color = weak && v.level ? LEVEL_STYLE[v.level].text : '#5B6472'
  const fill = legFills(pv)[limb]
  const mets = legCard(gait, limb, c.edition, pv)
  return (
    <div style={css(`display:flex;flex-direction:column;gap:6px;align-items:${align === 'r' ? 'flex-end' : 'flex-start'};text-align:${align === 'r' ? 'right' : 'left'}`)}>
      <span style={css(`display:flex;align-items:center;gap:6px;font-size:14px;font-weight:800;color:${color};flex-direction:${align === 'r' ? 'row-reverse' : 'row'}`)}><span style={css(`width:12px;height:12px;border-radius:4px;background:${fill};border:1px solid #B8B0A4`)}></span>{LIMB[limb]}{weak ? ' · 덜 씁니다' : ''}</span>
      {c.edition !== 'VET' ? (
        mets[0] ? (
          <>
            <span style={css('font-size:13px;color:#5B6472')}>{mets[0].n}</span>
            <b style={css(`font-size:22px;letter-spacing:-0.5px;font-variant-numeric:tabular-nums;color:${weak ? color : '#1B2433'}`)}>{mets[0].v}</b>
          </>
        ) : null
      ) : (
        mets.map((m, i) => (
          <span key={i} style={css('font-size:13px;color:#5B6472;font-variant-numeric:tabular-nums')}>{m.n} <b style={css(`font-size:15px;color:${m.lower && weak ? color : '#1B2433'}`)}>{m.v}</b> <span style={css('color:#5B6472')}>/ {m.other}</span></span>
        ))
      )}
    </div>
  )
}

/** 수의사용: 좌우 비교 표(서버 compare 그대로) */
function CompareTable({ g, vet }: { g: ReportContentGait; vet: boolean }) {
  if (!g.compare.length) return null
  const top = g.compare.filter((x) => x.comparable && x.symmetry_value != null).reduce<typeof g.compare[number] | null>((a, b) => (!a || b.symmetry_value! > a.symmetry_value! ? b : a), null)
  const cols = vet ? '1.9fr 1fr 1fr 1fr 1fr' : '1.9fr 1fr 1fr 1fr'
  return (
    <div style={css('display:flex;flex-direction:column;font-size:14px;font-variant-numeric:tabular-nums')}>
      <div style={css(`display:grid;grid-template-columns:${cols};gap:8px;color:#5B6472;font-size:13px;padding:8px 6px 6px;border-bottom:1px solid #ECE8E2`)}>
        <b>{g.label}</b><span style={css('text-align:right')}>왼쪽</span><span style={css('text-align:right')}>오른쪽</span><span style={css('text-align:right')}>차이</span>{vet ? <span style={css('text-align:right')}>대칭 지수</span> : null}
      </div>
      {g.compare.map((x, i) => (
        <div key={i} style={css(`display:grid;grid-template-columns:${cols};gap:8px;align-items:center;padding:9px 6px;border-bottom:1px solid #F2EFEA;background:${x === top ? '#FAF8F5' : 'transparent'}`)}>
          <span><b style={css('font-size:14px')}>{x.pair_label} {x.label}</b>{!x.comparable && x.reason ? <><br /><span style={css('font-size:12px;color:#5B6472')}>{x.reason}</span></> : null}</span>
          <span style={css('text-align:right')}>{x.left}</span>
          <span style={css('text-align:right')}>{x.right}</span>
          <b style={css('text-align:right')}>{x.diff}</b>
          {vet ? <span style={css('text-align:right')}>{x.symmetry_index}</span> : null}
        </div>
      ))}
    </div>
  )
}

const CHANGE_BADGE: Record<string, [string, string]> = { INCREASE: ['#1B2433', '#fff'], DECREASE: ['#1B2433', '#fff'], WITHIN_RANGE: ['#EEE8DF', '#3A4250'] }

function ChangeBadge({ x }: { x: ReportContentChangeCell }) {
  const label = x.change_label ?? (x.note ? '비교 불가' : null)
  if (!label) return <span></span>
  const [bg, fg] = (x.change && CHANGE_BADGE[x.change]) || ['#fff', '#5B6472']
  return <span style={css(`justify-self:end;height:24px;padding:0 9px;border-radius:12px;background:${bg};color:${fg};border:1px solid ${bg === '#fff' ? '#D8D2C8' : bg};font-size:12px;font-weight:700;display:flex;align-items:center;white-space:nowrap`)}>{label}</span>
}

/** 직전 회차와 비교 표(서버 changes 그대로): 수치·다리 | 직전 → 이번 | 차이 | 변화 */
function ChangesTable({ g }: { g: ReportContentGait }) {
  if (!g.changes.length) return null
  return (
    <div style={css('display:flex;flex-direction:column;font-variant-numeric:tabular-nums')}>
      <b style={css('font-size:14px;color:#3A4250;padding:10px 0 6px;border-bottom:1px solid #ECE8E2')}>{g.label}</b>
      {g.changes.flatMap((row) => LIMB_ORDER.filter((l) => row.cells[l]).map((limb) => {
        const x = row.cells[limb]!
        return (
          <div key={row.metric_code + limb} className="rep-cmp-row" style={css('display:grid;grid-template-columns:1.6fr 1.4fr 0.9fr 92px;gap:12px;align-items:center;min-height:42px;box-sizing:border-box;padding:9px 6px;border-bottom:1px solid #F2EFEA')}>
            <span style={css('font-size:14px')}><b>{row.label}</b> <span style={css('color:#5B6472;font-size:13px;font-weight:600')}>{LIMB_NAME[limb] ?? limb}</span>{x.note ? <><br /><span style={css('font-size:12px;color:#5B6472')}>{x.note}</span></> : null}</span>
            <span style={css('font-size:14px;color:#5B6472;text-align:right')}>{x.previous} → <b style={css('color:#1B2433')}>{x.current}</b></span>
            <span style={css('font-size:14px;text-align:right')}>{x.diff ?? ''}</span>
            <ChangeBadge x={x} />
          </div>
        )
      }))}
    </div>
  )
}

/** knee: 수의사용 뒷무릎 각도 곡선(이 회차 실제 각도). 없으면 그 칸을 뺀다 */
export function ServerReportPaper({ c, knee }: { c: ReportContentOut; knee?: KneeChartView | null }) {
  const s = c.sentences
  const vet = c.edition === 'VET'
  const gait = cardGait(c)
  const gaits = [...c.gaits].sort((a, b) => (GAIT_ORDER.indexOf(a.gait_type) + 1 || 9) - (GAIT_ORDER.indexOf(b.gait_type) + 1 || 9))
  const pv = pairViews(c, gait)
  const svg = paintBody(_svg(sizeCode(c.session.size_class)), legFills(pv), c.dog.focus_limb)
  const score = c.session.symmetry_score
  const lv = symLevel(c)
  const bdiff = baselineDiff(c)
  const trend = trendPoints(c.history, c.session.round)
  const sub = [
    `${c.session.measured_on} 측정`, `${c.session.round}회차`, c.dog.breed,
    c.session.weight_kg != null ? `체중 ${c.session.weight_kg}kg` : null,
    c.session.model_name ? `분석 모델 ${c.session.model_name}${c.session.model_version ? ` ${c.session.model_version}` : ''}` : null,
  ].filter(Boolean).join(' · ')
  const previous = [s.previous_note, ...s.previous_gaps].filter((x): x is string => !!x)

  return (
    <div className="print-paper" data-report-source="server" data-template-version={c.template_version} style={css('background:#fff;border-radius:6px;box-shadow:0 18px 50px rgba(27,36,51,.1);padding:48px 52px;display:flex;flex-direction:column;gap:22px;min-height:960px')}>
      <div style={css('display:flex;align-items:center;justify-content:space-between')}><div style={css('display:flex;align-items:center;gap:8px;font-size:15px;font-weight:800')}><img src={staticUrl('assets/logo.png')} alt="" style={css('width:28px;height:28px;object-fit:contain')} />Paw oh Paw</div><span style={css('font-size:13px;color:#5B6472')}>{s.edition_label}</span></div>
      <div style={css('height:3px;background:#D2601A;width:56px')}></div>
      <div>
        <div className="rep-title" style={css('font-size:28px;font-weight:800;letter-spacing:-0.9px')}>{s.title}</div>
        <div style={css('font-size:14px;color:#5B6472;margin-top:6px')}>{sub}</div>
        <p className="rep-intro" style={css('margin:12px 0 0;font-size:15px;line-height:1.6;color:#3A4250')}>{s.intro}</p>
      </div>

      {/* 첫 쪽 요약: 주요 결과(sentences.summary) · 직전 회차(previous_note·previous_gaps) */}
      <div className="rep-summary" style={css('display:grid;grid-template-columns:88px 1fr;row-gap:8px;column-gap:14px;padding:16px 20px;border-radius:14px;border:1.5px solid #E9D3C2;background:#FFF9F4;font-size:15px;line-height:1.5')}>
        <b style={css('color:#A8481A')}>주요 결과</b><span style={css('display:flex;flex-direction:column;gap:4px')}>{s.summary.map((x, i) => <span key={i}>{x}</span>)}</span>
        {previous.length ? <><b style={css('color:#A8481A')}>직전 회차</b><span style={css('display:flex;flex-direction:column;gap:4px')}>{previous.map((x, i) => <span key={i}>{x}</span>)}</span></> : null}
      </div>

      {/* 한눈에: 좌우 대칭 점수(session.symmetry_score), 기준 회차 대비(baseline) */}
      {score != null ? (
        <div style={css('display:grid;grid-template-columns:auto 1fr;gap:22px;align-items:center;padding:20px 22px;border-radius:14px;background:#FAF7F2')}>
          <div style={css('display:flex;flex-direction:column;gap:2px')}>
            <span style={css('font-size:14px;font-weight:700;color:#5B6472')}>좌우 대칭 지수</span>
            <b style={css(`font-size:44px;letter-spacing:-1px;line-height:1.1;color:${lv ? LEVEL_STYLE[lv].text : '#1B2433'}`)}>{score}<span style={css('font-size:18px')}>%</span></b>
          </div>
          <div style={css('display:flex;flex-direction:column;gap:8px')}>
            <div style={css('position:relative;height:12px;border-radius:6px;background:linear-gradient(90deg,#F2A898 0%,#F2A898 60%,#F7D6AE 60%,#F7D6AE 80%,#DCEFE2 80%,#DCEFE2 100%)')}>
              <span style={css(`position:absolute;top:-5px;left:calc(${Math.max(0, Math.min(100, score))}% - 2px);width:4px;height:22px;border-radius:2px;background:#1B2433`)}></span>
            </div>
            <div style={css('display:flex;justify-content:space-between;font-size:12px;color:#5B6472')}><span>0</span><span>80</span><span>90</span><span>100 (완전 대칭)</span></div>
            <span style={css('font-size:15px;color:#3A4250')}>
              {bdiff != null && c.baseline ? <>기준 회차({c.baseline.measured_on})보다 <b style={css(`color:${bdiff > 0 ? '#2E8B57' : bdiff < 0 ? '#C2412D' : '#3A4250'}`)}>{bdiff > 0 ? '+' : ''}{bdiff}%p</b></> : c.baseline && c.baseline.session_id === c.session_id ? '이 회차가 기준 회차입니다' : null}
              {c.dog.focus_limb && LIMB[c.dog.focus_limb] ? <>{bdiff != null || c.baseline ? ' · ' : ''}관심 다리 <b>{LIMB[c.dog.focus_limb]}</b>(점선)</> : null}
            </span>
          </div>
        </div>
      ) : null}

      {/* 몸 그림 + 다리별 수치(gaits[].rows) */}
      <div style={css('display:grid;grid-template-columns:1fr 228px 1fr;align-items:stretch;gap:8px')}>
        <div style={css('position:relative')}>
          <div style={css('position:absolute;top:23%;left:0;right:8px')}><LegCard c={c} gait={gait} pv={pv} limb="LF" align="l" /></div>
          <div style={css('position:absolute;top:70%;left:0;right:8px')}><LegCard c={c} gait={gait} pv={pv} limb="LH" align="l" /></div>
        </div>
        <div className="rep-map" style={css('width:228px;height:560px')} dangerouslySetInnerHTML={{ __html: svg }}></div>
        <div style={css('position:relative')}>
          <div style={css('position:absolute;top:23%;right:0;left:8px')}><LegCard c={c} gait={gait} pv={pv} limb="RF" align="r" /></div>
          <div style={css('position:absolute;top:70%;right:0;left:8px')}><LegCard c={c} gait={gait} pv={pv} limb="RH" align="r" /></div>
        </div>
      </div>
      <div style={css('display:flex;justify-content:center;gap:16px;flex-wrap:wrap;font-size:13px;color:#5B6472')}>
        {gait ? <span style={css('font-weight:700;color:#3A4250')}>{gait.label}</span> : null}
        <span><span style={css('display:inline-block;width:11px;height:11px;border-radius:3px;background:#DCEFE2;border:1px solid #B8B0A4;vertical-align:-1px')}></span> 좌우 비슷 (차이 5% 미만)</span>
        <span><span style={css('display:inline-block;width:11px;height:11px;border-radius:3px;background:#F7D6AE;border:1px solid #B8B0A4;vertical-align:-1px')}></span> 조금 덜 씀 (5~10%)</span>
        <span><span style={css('display:inline-block;width:11px;height:11px;border-radius:3px;background:#F2A898;border:1px solid #B8B0A4;vertical-align:-1px')}></span> 많이 덜 씀 (10% 이상)</span>
      </div>

      {/* 다리 한 쌍씩: 단계와 그 단계를 정한 비교 줄(compare) */}
      <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:12px')}>
        {(['FORE', 'HIND'] as const).map((pair) => {
          const p = pv[pair]
          const x = p.line
          return (
            <div key={pair} className="rep-pair" style={css('padding:16px 18px;border-radius:12px;border:1px solid #ECE8E2;display:flex;flex-direction:column;gap:6px')}>
              <span style={css('display:flex;justify-content:space-between;font-size:14px;font-weight:700')}><span>{pair === 'FORE' ? '앞다리' : '뒷다리'}</span>{p.level ? <span style={css(`color:${LEVEL_STYLE[p.level].text}`)}>{LEVEL_STYLE[p.level].name}</span> : null}</span>
              {x ? (
                <>
                  <span style={css(`font-size:15px;line-height:1.55;font-weight:600`)}>{x.label}</span>
                  <span style={css('font-size:13px;line-height:1.5;color:#5B6472')}>왼쪽 <b style={css('color:#1B2433')}>{x.left}</b> · 오른쪽 <b style={css('color:#1B2433')}>{x.right}</b> · 차이 <b style={css('color:#1B2433')}>{x.diff}</b>{vet ? <> · 대칭 지수 {x.symmetry_index}</> : null}</span>
                </>
              ) : <span style={css(SUB)}>{gait?.compare.find((y) => y.pair === pair)?.reason ?? ''}</span>}
            </div>
          )
        })}
      </div>

      {/* 보호자용 둘째 쪽: 참고(sentences.caution) */}
      {!vet && s.caution.length ? (
        <div className="rep-p2" style={css('display:flex;flex-direction:column;gap:10px')}>
          <b style={css('font-size:18px')}>참고</b>
          {s.caution.map((x, i) => <div key={i} style={css('padding:12px 18px;border-radius:12px;background:#FFF9F4;border:1px solid #F0DCCB;font-size:15px;line-height:1.6')}>{x}</div>)}
        </div>
      ) : null}

      {vet ? (
        <div style={css('display:flex;flex-direction:column;gap:28px')}>
          {/* 좌우 비교(보행 유형별 compare·notes) */}
          <section className="rep-sec rep-pb" style={css('display:flex;flex-direction:column;gap:10px')}>
            <h2 style={css(H2)}>왼쪽과 오른쪽 비교</h2>
            {gaits.map((g) => (
              <div key={g.gait_type} style={css('display:flex;flex-direction:column;gap:6px')}>
                <CompareTable g={g} vet />
                {g.notes.map((n, i) => <span key={i} style={css(SUB)}>{n}</span>)}
              </div>
            ))}
          </section>
          {/* 뒷무릎 각도 · 보행 주기: 이 회차의 실제 각도(GET /shots/{id}/angles)로 만든 곡선이 있을 때만. 견본·합성 곡선은 쓰지 않는다 */}
          {knee ? <section className="rep-sec rep-knee"><KneeChart kc={knee} /></section> : null}
          <section className="rep-sec rep-pb" style={css('display:flex;flex-direction:column;gap:8px')}>
            <h2 style={css(H2)}>직전 회차와 비교{c.previous ? <span style={css('font-size:14px;font-weight:600;color:#5B6472;margin-left:8px')}>{c.previous.measured_on} · {c.previous.round}회차</span> : null}</h2>
            {previous.map((x, i) => <span key={i} style={css(SUB)}>{x}</span>)}
            {gaits.map((g) => <ChangesTable key={g.gait_type} g={g} />)}
          </section>
        </div>
      ) : null}

      {/* 지금까지 좌우 대칭 지수(history) */}
      {trend.length > 1 ? (
        <div className="rep-sec" style={css('display:flex;flex-direction:column;gap:6px')}>
          <b style={css('font-size:15px')}>지금까지 좌우 대칭 지수</b>
          <svg className="rep-trend" viewBox="0 0 360 100" style={css('width:100%;max-width:560px')}>
            <polyline points={trend.map((p) => `${p.x},${p.y}`).join(' ')} fill="none" stroke="#D2601A" strokeWidth="2.5" strokeLinejoin="round"></polyline>
            {trend.map((p, i) => (
              <Fragment key={i}><circle cx={p.x} cy={p.y} r={p.cur ? 5 : 3.5} fill={p.cur ? '#D2601A' : '#fff'} stroke="#D2601A" strokeWidth="2"></circle><text x={p.x} y={p.y - 9} textAnchor="middle" fontSize="12" fill="#3A4250" fontWeight={p.cur ? 700 : 400}>{p.v}</text><text x={p.x} y="97" textAnchor="middle" fontSize="12" fill="#5B6472">{p.t}</text></Fragment>
            ))}
          </svg>
        </div>
      ) : null}

      {vet && s.caution.length ? <div style={css('display:flex;flex-direction:column;gap:4px')}>{s.caution.map((x, i) => <span key={i} style={css(SUB)}>{x}</span>)}</div> : null}
      <div style={css('flex:1')}></div>
      {s.glossary.length ? (
        <div className="rep-glossary" style={css('display:flex;flex-direction:column;gap:3px;font-size:12px;color:#5B6472')}>
          <b style={css('font-size:13px;color:#3A4250')}>용어 설명</b>
          {s.glossary.map((x) => <span key={x.term}><b>{x.term}</b>: {x.explanation}</span>)}
        </div>
      ) : null}
      <span className="rep-disclaimer" style={css('font-size:12px;color:#5B6472')}>{s.disclaimer}</span>
    </div>
  )
}
