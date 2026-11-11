/* eslint-disable @typescript-eslint/no-explicit-any */
// 앱의 홈·반려견 차트·분석 결과 화면. 웹(web/src/pages/Home.tsx·Dog.tsx·Results.tsx)과 같은 정보·구성을 폰 폭에 맞춘 것.
// 값은 AppProto.renderVals 가 만들고(webHome·webDog·webResults), 여기는 그리기만 한다.
import { Fragment, type CSSProperties, type ReactNode } from 'react'
import { useVitView } from '../../app/emr'

const INK = '#1B2433', INK2 = '#3A4250', SUB = '#5B6472', DIM = '#8E949C', LINE = '#ECE8E2', LINE2 = '#F2EFEA', ORANGE = '#D2601A'
const card: CSSProperties = { background: '#fff', border: `1px solid ${LINE}`, borderRadius: 16 }
const chip = (bg: string, c: string, extra: CSSProperties = {}): CSSProperties => ({ display: 'inline-flex', alignItems: 'center', height: 22, padding: '0 8px', borderRadius: 7, background: bg, color: c, fontSize: 11.5, fontWeight: 700, whiteSpace: 'nowrap', ...extra })
const tnum: CSSProperties = { fontVariantNumeric: 'tabular-nums' }
const Chev = () => <svg width="18" height="18" viewBox="0 0 24 24" style={{ color: '#A0A7B2', flex: 'none' }}><use href="#i-chev"></use></svg>

export interface Tone { bg: string; c: string }
export interface HomeRow {
  key: string
  /** 오늘·분석: 시각/측정일. 반려견: 마지막 측정 */
  when: string
  name: string
  sub: string
  chips: { t: string; bg: string; c: string }[]
  /** 분석 탭: 대칭 지수 배지·증감 */
  sym?: { t: string; bg: string; c: string; d?: string; dc?: string }
  st?: { t: string; bg: string; c: string }
  right?: string
  live?: boolean
  open: () => void
}
export interface WebHome {
  today: string
  acctName: string
  acctInit: string
  hasUnread: boolean
  goNotif: () => void
  goMy: () => void
  goPetNew: () => void
  goCapture: () => void
  cards: { label: string; n: number; unit: string; warn?: boolean; on?: boolean; pick: () => void }[]
  views: { key: string; label: string; on: boolean; pick: () => void }[]
  /** 촬영 담당자 목록에서 고른 담당자(분석 목록을 그 담당자로 거른다) */
  by: { t: string; clear: () => void } | null
  /** 분석 탭의 기간 거르기 */
  period: { opts: { label: string; on: boolean; pick: () => void }[]; custom: boolean; from: string; to: string; max: string; onFrom: (e: any) => void; onTo: (e: any) => void } | null
  view: string
  q: string
  onQ: (e: any) => void
  rows: HomeRow[]
  empty: string
  ana: { on: boolean; thumb: ReactNode; name: string; label: string; hint: string; pct: number; step: string; n: number; measuring: boolean; open: () => void }
}

export function HomeBody({ h }: { h: WebHome }) {
  return (
    <div style={{ position: 'absolute', inset: 0, padding: '36px 0 96px', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px 6px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><img src="/assets/d/4240fb11.webp" alt="" style={{ width: 26, height: 26 }} /><b style={{ fontSize: 17, fontWeight: 800, letterSpacing: '-0.4px' }}>Paw oh Paw</b></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <div onClick={h.goNotif} style={{ width: 44, height: 44, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', position: 'relative' }}><svg width="24" height="24" viewBox="0 0 24 24"><use href="#i-bell"></use></svg>{h.hasUnread ? <span style={{ position: 'absolute', top: 10, right: 11, width: 7, height: 7, borderRadius: 4, background: ORANGE }} /> : null}</div>
          <div onClick={h.goMy} style={{ height: 36, display: 'flex', alignItems: 'center', gap: 7, padding: '0 12px 0 4px', borderRadius: 18, background: '#fff', border: `1px solid ${LINE}`, cursor: 'pointer', maxWidth: 190 }}><span style={{ width: 28, height: 28, flex: 'none', borderRadius: '50%', background: '#FCEEE3', color: ORANGE, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 800 }}>{h.acctInit}</span><b style={{ fontSize: 13.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{h.acctName}</b></div>
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '0 20px 12px', display: 'flex', flexDirection: 'column', gap: 12 }} className="pp-s aw-col">
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 10 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}><span style={{ fontSize: 12.5, fontWeight: 600, color: DIM }}>{h.today}</span><b style={{ fontSize: 22, letterSpacing: '-0.5px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{h.acctName}</b></div>
          <div onClick={h.goPetNew} style={{ flex: 'none', height: 38, padding: '0 12px', borderRadius: 10, background: '#FCEEE3', color: '#B4501A', display: 'flex', alignItems: 'center', fontSize: 13.5, fontWeight: 700, cursor: 'pointer' }}>+ 반려견 등록</div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,minmax(0,1fr))', gap: 8 }}>
          {h.cards.map((c) => (
            <div key={c.label} onClick={c.pick} style={{ ...card, border: `1.5px solid ${c.on ? ORANGE : LINE}`, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 2, cursor: 'pointer' }}>
              <span style={{ fontSize: 11.5, fontWeight: 600, color: SUB, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.label}</span>
              <b style={{ fontSize: 20, letterSpacing: '-0.4px', color: c.warn && c.n ? '#C2412D' : INK, ...tnum }}>{c.n}<span style={{ fontSize: 12, fontWeight: 600, color: DIM, marginLeft: 2 }}>{c.unit}</span></b>
            </div>
          ))}
        </div>
        {h.ana.on ? (
          <div onClick={h.ana.open} style={{ ...card, padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}>
            {h.ana.thumb}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14.5, fontWeight: 700 }}>{h.ana.name}{h.ana.label}</div>
              {h.ana.measuring ? <div style={{ fontSize: 12.5, color: SUB, marginTop: 3 }}>{h.ana.hint}</div> : (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}><div style={{ flex: 1, height: 5, borderRadius: 3, background: '#FCEEE3' }}><div style={{ width: `${h.ana.pct}%`, height: '100%', borderRadius: 3, background: ORANGE, transition: 'width .2s' }} /></div><span style={{ fontSize: 12, color: SUB, whiteSpace: 'nowrap', ...tnum }}>{h.ana.step} · {h.ana.pct}%</span></div>
              )}
            </div>
          </div>
        ) : null}
        <div style={{ display: 'flex', padding: 4, borderRadius: 12, background: '#F1ECE5', gap: 2 }}>
          {h.views.map((t) => <div key={t.key} onClick={t.pick} style={{ flex: 1, height: 36, borderRadius: 9, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: t.on ? 700 : 500, background: t.on ? '#fff' : 'transparent', color: t.on ? INK : SUB, boxShadow: t.on ? '0 1px 3px rgba(27,36,51,.12)' : 'none', cursor: 'pointer' }}>{t.label}</div>)}
        </div>
        {h.by ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <span style={{ fontSize: 14, color: SUB }}><b style={{ color: INK }}>{h.by.t}</b> 님이 촬영한 분석</span>
            <span onClick={h.by.clear} style={{ height: 32, padding: '0 12px', borderRadius: 9, border: `1px solid #E2DCD3`, background: '#fff', display: 'flex', alignItems: 'center', fontSize: 13, fontWeight: 600, cursor: 'pointer', flex: 'none' }}>✕ 담당자 목록으로</span>
          </div>
        ) : null}
        <label style={{ height: 44, borderRadius: 12, background: '#fff', border: `1px solid ${LINE}`, display: 'flex', alignItems: 'center', gap: 10, padding: '0 14px', color: DIM }}>
          <svg width="18" height="18" viewBox="0 0 24 24" style={{ flex: 'none' }}><use href="#i-search"></use></svg>
          <input value={h.q} onChange={h.onQ} placeholder="반려견 이름·견종 검색" style={{ flex: 1, minWidth: 0, border: 'none', outline: 'none', background: 'transparent', fontSize: 15, color: INK }} />
        </label>
        {h.period ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', gap: 6, overflowX: 'auto' }} className="pp-s">
              {h.period.opts.map((o) => <span key={o.label} onClick={o.pick} style={{ flex: 'none', height: 34, padding: '0 13px', borderRadius: 17, display: 'flex', alignItems: 'center', fontSize: 13.5, fontWeight: o.on ? 700 : 500, background: o.on ? INK : '#fff', color: o.on ? '#fff' : INK2, border: `1px solid ${o.on ? INK : LINE}`, cursor: 'pointer' }}>{o.label}</span>)}
            </div>
            {h.period.custom ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input type="date" value={h.period.from} max={h.period.to || h.period.max} onChange={h.period.onFrom} aria-label="시작일" style={{ flex: 1, minWidth: 0, height: 42, borderRadius: 10, border: `1px solid ${LINE}`, background: '#fff', padding: '0 10px', fontSize: 14, color: INK, fontFamily: 'inherit' }} />
                <span style={{ color: DIM, flex: 'none' }}>~</span>
                <input type="date" value={h.period.to} min={h.period.from || undefined} max={h.period.max} onChange={h.period.onTo} aria-label="끝 날짜" style={{ flex: 1, minWidth: 0, height: 42, borderRadius: 10, border: `1px solid ${LINE}`, background: '#fff', padding: '0 10px', fontSize: 14, color: INK, fontFamily: 'inherit' }} />
              </div>
            ) : null}
          </div>
        ) : null}
        <div style={{ ...card, padding: '0 14px' }}>
          {h.rows.map((r, i) => (
            <div key={r.key} onClick={r.open} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 0', borderTop: i ? `1px solid ${LINE2}` : 'none', cursor: 'pointer' }}>
              <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <b style={{ fontSize: 15.5 }}>{r.name}</b>
                  {r.live ? <span style={chip('#FCEEE3', '#A8481A')}><span style={{ width: 6, height: 6, borderRadius: 3, background: ORANGE, marginRight: 4 }} />측정 중</span> : null}
                  {r.st ? <span style={chip(r.st.bg, r.st.c)}>{r.st.t}</span> : null}
                </div>
                <span style={{ fontSize: 12.5, color: SUB, ...tnum, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.when}{r.when && r.sub ? ' · ' : ''}{r.sub}</span>
                {r.chips.length ? <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>{r.chips.map((c, j) => <span key={j} style={chip(c.bg, c.c)}>{c.t}</span>)}</div> : null}
              </div>
              {r.sym ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3, flex: 'none' }}>
                  <b style={{ padding: '3px 9px', borderRadius: 8, background: r.sym.bg, color: r.sym.c, fontSize: 13.5, ...tnum }}>{r.sym.t}</b>
                  {r.sym.d ? <span style={{ fontSize: 12, fontWeight: 700, color: r.sym.dc }}>{r.sym.d}</span> : r.right ? <span style={{ fontSize: 12, color: DIM }}>{r.right}</span> : null}
                </div>
              ) : r.right ? <span style={{ fontSize: 12.5, color: SUB, flex: 'none', textAlign: 'right', ...tnum }}>{r.right}</span> : null}
              <Chev />
            </div>
          ))}
          {!h.rows.length ? <div style={{ padding: '32px 8px', textAlign: 'center', fontSize: 14, color: SUB }}>{h.empty}</div> : null}
        </div>
      </div>
    </div>
  )
}

export interface WebDog {
  none: boolean
  missing: boolean
  name: string
  init: string
  desc: string
  live: boolean
  tags: string[]
  cells: { k: string; v: string; sub?: string }[]
  memo: string
  /** 바이탈·진단/수술 카드에 쓸 반려견(값은 DogBody 가 API 로 읽는다). 전체 진료 기록은 웹에서 본다 */
  emr: { dogId: string | null; kg: string }
  trend: { has: boolean; pts: { x: number; y: number; v: number; t: string; cur?: boolean }[]; line: string; label: string; c: string; sym: number | null }
  hist: { id: string; no: string; date: string; w: string; pass: string; model: string; rep: string; base: boolean; canBase: boolean; st: string; bg: string; c: string; open: () => void; setBase: (e: any) => void }[]
  count: string
  back: () => void
  edit: () => void
  compare: () => void
  start: () => void
}

export function DogBody({ d }: { d: WebDog }) {
  const vit = useVitView(d.emr.dogId ?? undefined, d.emr.kg)
  return (
    <div style={{ position: 'absolute', inset: 0, paddingTop: 36, display: 'flex', flexDirection: 'column' }}>
      <div style={{ flex: 'none', height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px 0 8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}><div onClick={d.back} style={{ width: 44, height: 44, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}><svg width="24" height="24" viewBox="0 0 24 24"><use href="#i-back"></use></svg></div><b style={{ fontSize: 18 }}>반려견 차트</b></div>
        {!d.none ? <span onClick={d.edit} style={{ fontSize: 15, fontWeight: 600, color: ORANGE, cursor: 'pointer', padding: '8px 4px' }}>정보 수정</span> : null}
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '4px 20px 24px', display: 'flex', flexDirection: 'column', gap: 12 }} className="pp-s aw-col">
        <div style={{ ...card, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 52, height: 52, borderRadius: '50%', background: '#FCEEE3', color: '#A8481A', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 20, flex: 'none' }}>{d.init}</div>
            <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}><b style={{ fontSize: 21, letterSpacing: '-0.5px' }}>{d.name}</b>{d.live ? <span style={chip('#FCEEE3', '#A8481A')}>측정 중</span> : null}</div>
              <span style={{ fontSize: 13.5, color: SUB }}>{d.desc}</span>
            </div>
          </div>
          {d.tags.length ? <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>{d.tags.map((t) => <span key={t} style={chip('#F2EEE8', INK2, { height: 26, fontSize: 12.5, fontWeight: 600 })}>{t}</span>)}</div> : null}
        </div>
        {d.missing ? <div style={{ ...card, padding: '24px 16px', textAlign: 'center', fontSize: 14, color: SUB }}>지웠거나 이 기관의 반려견이 아닙니다</div> : null}
        {!d.none ? (
          <>
            <div style={{ ...card, padding: '14px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 14px' }}>
              {d.cells.map((c) => <div key={c.k} style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}><span style={{ fontSize: 12, fontWeight: 600, color: SUB }}>{c.k}</span><b style={{ fontSize: 14.5, ...tnum }}>{c.v}</b>{c.sub ? <span style={{ fontSize: 11.5, color: '#A0A7B2' }}>{c.sub}</span> : null}</div>)}
              <div style={{ gridColumn: 'span 2', display: 'flex', flexDirection: 'column', gap: 2 }}><span style={{ fontSize: 12, fontWeight: 600, color: SUB }}>메모</span><span style={{ fontSize: 13.5, lineHeight: 1.5, color: INK2, whiteSpace: 'pre-line' }}>{d.memo}</span></div>
            </div>
            <div style={{ ...card, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}><b style={{ fontSize: 15 }}>바이탈</b>{vit.when ? <span style={{ fontSize: 12, color: DIM, ...tnum }}>{vit.when}</span> : null}</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,minmax(0,1fr))', gap: 6 }}>
                {vit.cells.map((c) => <div key={c.k} style={{ background: '#F7F4EF', borderRadius: 10, padding: '8px 6px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, minWidth: 0 }}><span style={{ fontSize: 11.5, fontWeight: 600, color: SUB }}>{c.k}</span><b style={{ fontSize: 14, whiteSpace: 'nowrap', ...tnum }}>{c.v}</b>{c.sub ? <span style={{ fontSize: 10.5, color: '#A0A7B2' }}>{c.sub}</span> : null}</div>)}
              </div>
              {vit.note ? <span style={{ fontSize: 12.5, color: '#A0A7B2' }}>{vit.note}</span> : null}
            </div>
            <div style={{ ...card, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
              <b style={{ fontSize: 15 }}>진단 · 수술</b>
              {vit.hist.length ? vit.hist.map((x, i) => (
                <div key={x.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, paddingTop: i ? 8 : 0, borderTop: i ? `1px solid ${LINE2}` : 'none' }}>
                  <span style={chip(x.kind === '수술' ? '#FCEEE3' : x.kind === '진단' ? '#EEF1F6' : '#F2EEE8', x.kind === '수술' ? '#A8481A' : x.kind === '진단' ? '#4A5A78' : INK2, { flex: 'none' })}>{x.kind}</span>
                  <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}><b style={{ fontSize: 14, lineHeight: 1.4 }}>{x.title}</b><span style={{ fontSize: 12, color: SUB, ...tnum }}>{x.day}{x.site ? ` · ${x.site}` : ''}{x.by ? ` · ${x.by}` : ''}</span></div>
                </div>
              )) : <span style={{ fontSize: 13.5, color: '#A0A7B2' }}>기록된 진단·수술이 없습니다</span>}
            </div>
            <div style={{ ...card, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}><b style={{ fontSize: 15 }}>경과 한눈에 보기</b>{d.trend.has ? <span style={{ fontSize: 12.5, color: SUB }}>최근 대칭 점수 <b style={{ color: INK, ...tnum }}>{d.trend.sym}점</b> · <b style={{ color: d.trend.c }}>{d.trend.label}</b></span> : null}</div>
              {d.trend.has ? (
                <svg viewBox="0 0 320 110" style={{ width: '100%', display: 'block' }}>
                  {[20, 50, 80].map((y) => <line key={y} x1="24" x2="300" y1={y} y2={y} stroke="#F0ECE6" />)}
                  {d.trend.pts.length > 1 ? <polyline points={d.trend.line} fill="none" stroke={ORANGE} strokeWidth="2.5" strokeLinejoin="round" /> : null}
                  {d.trend.pts.map((p, i) => (
                    <Fragment key={i}>
                      <circle cx={p.x} cy={p.y} r={p.cur ? 5 : 3.5} fill={p.cur ? ORANGE : '#fff'} stroke={ORANGE} strokeWidth="2" />
                      <text x={p.x} y={p.y - 9} textAnchor="middle" fontSize="10" fill={INK2} fontWeight={p.cur ? 700 : 400}>{p.v}</text>
                      <text x={p.x} y="104" textAnchor="middle" fontSize="9.5" fill={DIM}>{p.t}</text>
                    </Fragment>
                  ))}
                </svg>
              ) : <span style={{ fontSize: 13.5, color: '#A0A7B2' }}>유효한 회차가 쌓이면 대칭 점수 변화를 보여 줍니다.</span>}
            </div>
            <b style={{ fontSize: 16, letterSpacing: '-0.3px', padding: '6px 2px 0' }}>측정 이력 <span style={{ color: '#A0A7B2', fontWeight: 600, fontSize: 14 }}>{d.count}</span></b>
            <div style={{ ...card, padding: '0 14px' }}>
              {d.hist.map((h, i) => (
                <div key={h.id} onClick={h.open} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '13px 0', borderTop: i ? `1px solid ${LINE2}` : 'none', cursor: 'pointer' }}>
                  <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}><b style={{ fontSize: 15, ...tnum }}>{h.no}</b><span style={{ fontSize: 13.5, color: SUB, ...tnum }}>{h.date}</span>{h.base ? <span style={chip(INK, '#fff', { height: 20, fontSize: 11 })}>기준</span> : null}{h.rep !== '—' ? <span style={chip('#F2EEE8', INK2, { height: 20, fontSize: 11 })}>보고서</span> : null}</div>
                    <span style={{ fontSize: 12.5, color: SUB, ...tnum }}>체중 {h.w} · 유효 통과 {h.pass} · 모델 {h.model}</span>
                    {h.canBase ? <span onClick={h.setBase} style={{ alignSelf: 'flex-start', fontSize: 12.5, fontWeight: 700, color: '#B4501A', padding: '2px 0', cursor: 'pointer' }}>기준 회차로 지정</span> : null}
                  </div>
                  <span style={chip(h.bg, h.c, { height: 24, fontSize: 12 })}>{h.st}</span>
                  <Chev />
                </div>
              ))}
              {!d.hist.length ? <div style={{ padding: '24px 8px', textAlign: 'center', fontSize: 14, color: SUB }}>아직 측정 기록이 없습니다</div> : null}
            </div>
          </>
        ) : null}
      </div>
      {!d.none ? (
        <div style={{ flex: 'none', padding: '12px 20px 28px', borderTop: `1px solid ${LINE}`, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.4fr)', gap: 10 }}>
          <div onClick={d.compare} style={{ height: 56, borderRadius: 16, background: '#fff', border: `1px solid ${LINE}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, fontWeight: 600, cursor: 'pointer' }}>경과 비교</div>
          <div onClick={d.start} className="appview-h1" style={{ height: 56, borderRadius: 16, background: ORANGE, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, fontSize: 17, fontWeight: 700, cursor: 'pointer' }}><svg width="20" height="20" viewBox="0 0 24 24"><use href="#i-cam"></use></svg>새 측정</div>
        </div>
      ) : null}
    </div>
  )
}

export interface WebReports {
  total: number
  q: string
  onQ: (e: any) => void
  chips: { id: string; init: string; name: string; on: boolean; pick: () => void }[]
  rows: { id: string; thumb: ReactNode; name: string; when: string; sub: string; owner: boolean; vet: boolean; openOwner: () => void; openVet: () => void }[]
  more: string
  loadMore: () => void
  empty: string
}

/** 보고서 탭: 보고서가 만들어진 회차를 최신순으로. 위에서 반려견 이름·견종 검색과 반려견 고르기 */
export function ReportsBody({ r }: { r: WebReports }) {
  const btn = (on: boolean, primary: boolean): CSSProperties => ({ height: 34, padding: '0 12px', borderRadius: 9, display: 'flex', alignItems: 'center', fontSize: 13, fontWeight: 700, whiteSpace: 'nowrap', cursor: on ? 'pointer' : 'default', background: !on ? '#F2EFEA' : primary ? '#FCEEE3' : '#fff', color: !on ? '#B8BDC4' : primary ? '#A8481A' : INK2, border: `1px solid ${!on ? '#F2EFEA' : primary ? '#F6D9C4' : LINE}` })
  return (
    <div style={{ position: 'absolute', inset: 0, padding: '36px 0 96px', display: 'flex', flexDirection: 'column' }}>
      <div style={{ flex: 'none', height: 56, display: 'flex', alignItems: 'center', gap: 8, padding: '0 20px' }}><b style={{ fontSize: 20, letterSpacing: '-0.4px' }}>보고서</b><span style={{ fontSize: 14, fontWeight: 600, color: '#A0A7B2', ...tnum }}>{r.total}건</span></div>
      <div style={{ flex: 'none', padding: '0 20px 10px' }}>
        <label style={{ height: 44, borderRadius: 12, background: '#fff', border: `1px solid ${LINE}`, display: 'flex', alignItems: 'center', gap: 10, padding: '0 14px', color: DIM }}>
          <svg width="18" height="18" viewBox="0 0 24 24" style={{ flex: 'none' }}><use href="#i-search"></use></svg>
          <input value={r.q} onChange={r.onQ} placeholder="반려견 이름·견종 검색" style={{ flex: 1, minWidth: 0, border: 'none', outline: 'none', background: 'transparent', fontSize: 15, color: INK }} />
        </label>
      </div>
      <div style={{ flex: 'none', display: 'flex', gap: 14, padding: '7px 20px 10px', overflowX: 'auto' }} className="pp-s">
        {r.chips.map((c) => (
          <div key={c.id} onClick={c.pick} style={{ flex: 'none', width: 64, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <div style={{ width: 52, height: 52, borderRadius: '50%', background: c.on ? '#FCEEE3' : '#EEEAE4', color: c.on ? '#A8481A' : '#7A808A', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: c.id === 'all' ? 13 : 20, fontWeight: 800, boxShadow: c.on ? '0 0 0 3px #FAF9F6,0 0 0 5px #D2601A' : 'none' }}>{c.init}</div>
            <span style={{ fontSize: 12.5, color: c.on ? INK : SUB, fontWeight: c.on ? 700 : 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 64 }}>{c.name}</span>
          </div>
        ))}
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '0 20px 12px' }} className="pp-s">
        <div style={{ ...card, padding: '0 14px' }}>
          {r.rows.map((x, i) => (
            <div key={x.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 0', borderTop: i ? `1px solid ${LINE2}` : 'none' }}>
              {x.thumb}
              <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
                <b style={{ fontSize: 15 }}>{x.name}</b>
                <span style={{ fontSize: 12.5, color: SUB, ...tnum }}>{x.when}</span>
                <span style={{ fontSize: 12.5, color: SUB, ...tnum, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{x.sub}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 'none' }}>
                <span onClick={x.owner ? x.openOwner : undefined} style={btn(x.owner, true)}>보호자용</span>
                <span onClick={x.vet ? x.openVet : undefined} style={btn(x.vet, false)}>수의사용</span>
              </div>
            </div>
          ))}
          {r.more ? <div onClick={r.loadMore} style={{ padding: 14, textAlign: 'center', borderTop: `1px solid ${LINE2}`, fontSize: 14, fontWeight: 700, color: INK2, cursor: 'pointer' }}>{r.more}</div> : null}
          {!r.rows.length ? <div style={{ padding: '40px 12px', textAlign: 'center', fontSize: 14, lineHeight: 1.5, color: SUB }}>{r.empty}</div> : null}
        </div>
      </div>
    </div>
  )
}
