// 앱 보고서 본문(보호자용·수의사용). 웹 보고서(web/src/pages/Report.tsx)와 같은 구성을 폰 폭에 맞춘 것:
// 요약(보호자용) → 좌우 대칭 지수 → 몸 그림 + 다리별 수치 → 앞·뒷다리 한 줄 → 측정 품질 → 지금까지 대칭 지수(보호자용) /
// 좌우 비교·지난 측정과 비교·무릎 가동 범위 변화(수의사용, AppVetSections).
// 몸 그림 색·문구 규칙은 웹 views.ts body_map 과 같다(대칭 지수 차이 5%·10% 경계).
import type { ReactNode } from 'react'
import { AppOwnerSummary } from './AppOwnerSummary'
import type { SessionResultOut } from '../../api/types'
import { AppExcludeLine, AppQualityLine } from './AppQuality'
import dogSmall from './dog/dog_small.svg?raw'
import dogMedium from './dog/dog_medium.svg?raw'
import dogLarge from './dog/dog_large.svg?raw'

type Level = [number, string, string, string]
const LEVEL: Level[] = [[5, '비슷합니다', '#DCEFE2', '#2E8B57'], [10, '조금 차이 나요', '#F7D6AE', '#9A6A12'], [999, '차이가 큽니다', '#F2A898', '#C2412D']]
/** 수치가 없는 부위: '비슷합니다' 로 보이지 않게 */
const NA_LEVEL: Level = [0, '측정 불가', '#E9E4DC', '#5B6472']
const level = (si: number) => LEVEL.find((x) => si < x[0])!
const LEGS: [string, string, string][] = [['front_left', 'LF', '왼앞'], ['front_right', 'RF', '오른앞'], ['hind_left', 'LH', '왼뒤'], ['hind_right', 'RH', '오른뒤']]
const PARTS: ['front' | 'hind', string, [string, string, string][]][] = [
  ['front', '앞다리', [['rom_elbow', '팔꿈치 가동 범위', '°']]],
  ['hind', '뒷다리', [['rom_stifle', '무릎 가동 범위', '°'], ['rom_hip', '고관절 가동 범위', '°'], ['stride_length', '걸음 길이', '%'], ['stance_ratio', '입각기 비율', '%']]],
]
const WORD: Record<string, string> = {
  '팔꿈치 가동 범위': '팔꿈치를 굽히는 정도', '무릎 가동 범위': '무릎을 굽히는 정도', '고관절 가동 범위': '엉덩이 관절 움직임',
  '걸음 길이': '한 걸음 길이', '입각기 비율': '땅을 딛고 있는 시간',
}
const READ: Record<string, string> = {
  '팔꿈치 가동 범위': '걸을 때 팔꿈치를 접었다 펴는 폭', '무릎 가동 범위': '걸을 때 무릎을 접었다 펴는 폭',
  '고관절 가동 범위': '엉덩이 관절이 앞뒤로 움직이는 폭', '걸음 길이': '한 걸음에 나아가는 거리(등 길이 대비)', '입각기 비율': '한 걸음 중 발이 땅을 딛는 시간',
}
const r1 = (v: number) => Math.round(v * 10) / 10
const josa = (w: string) => ((w.charCodeAt(w.length - 1) - 0xac00) % 28 ? '이' : '가')

interface Met { n: string; l: number; r: number; u: string }
interface Part { si: number; lv: Level; say: string; worst: Met | null; weak: 'l' | 'r' }

function metsOf(result: SessionResultOut | null | undefined) {
  const g = result?.gaits.find((x) => x.gait_type === 'TROT' && x.metrics.length) ?? result?.gaits.find((x) => x.metrics.length)
  const val = (code: string, limb: string) => g?.metrics.find((m) => m.metric_code === code && m.limb === limb && m.measurable)?.value ?? null
  const parts = {} as Record<'front' | 'hind', { label: string; mets: Met[] }>
  for (const [part, label, codes] of PARTS) {
    const fh = part === 'front' ? 'F' : 'H'
    const mets = codes.map(([code, n, u]) => ({ n, l: val(code, 'L' + fh), r: val(code, 'R' + fh), u }))
      .filter((m): m is Met => m.l != null && m.r != null)
      .map((m) => ({ ...m, l: r1(m.l), r: r1(m.r) }))
    parts[part] = { label, mets }
  }
  return { gait: g?.gait_type ?? 'TROT', parts }
}

function partOf(label: string, mets: Met[]): Part {
  if (!mets.length) return { si: 0, lv: NA_LEVEL, say: `${label}는 비교할 수치가 없습니다`, worst: null, weak: 'l' }
  const sis = mets.map((m) => (m.l + m.r ? (Math.abs(m.l - m.r) / ((m.l + m.r) / 2)) * 100 : 0))
  const k = sis.indexOf(Math.max(...sis))
  const worst = mets[k], si = sis[k], weak: 'l' | 'r' = worst.l < worst.r ? 'l' : 'r'
  const w = WORD[worst.n] ?? worst.n
  const say = si < 5 ? `${label} 양쪽을 비슷하게 씁니다` : `${weak === 'l' ? '왼쪽' : '오른쪽'} ${label}의 ${w}${josa(w)} 반대쪽보다 작습니다`
  return { si: r1(si), lv: level(si), say, worst, weak }
}

function dogSvg(size: string, fills: Record<string, string>, focus: string | null): string {
  let s = size === 'S' ? dogSmall : size === 'L' ? dogLarge : dogMedium
  s = s.slice(s.indexOf('<svg')).replace('width="1024" height="1024"', 'width="100%" height="100%"').replace('viewBox="0 0 1024 1024"', 'viewBox="362 144 300 736"')
  for (const [pid, code] of LEGS) {
    const stroke = focus === code ? 'stroke="#D2601A" stroke-width="6" stroke-dasharray="14 8"' : 'stroke="#B8B0A4" stroke-width="2"'
    s = s.replace(`<path id="${pid}" fill="#E9E4DC" stroke="#B8B0A4" stroke-width="2"`, `<path id="${pid}" fill="${fills[code] ?? '#E9E4DC'}" ${stroke}`)
  }
  return s
}

const box = (extra: React.CSSProperties = {}): React.CSSProperties => ({ borderRadius: '12px', padding: '12px 14px', ...extra })

export interface AppReportProps {
  kind: 'g' | 'v'
  result: SessionResultOut | null | undefined
  dogName: string
  dogSize: string
  focus: string | null
  /** 이 회차 대칭 지수(%) */
  sym: number | null
  /** 오래된 회차부터 이 회차까지 [날짜 MM-DD, 대칭 지수] */
  symHist: [string, number][]
  /** 기준 회차 대비 대칭 지수 차이(%p)와 날짜 */
  /** 직전 회차 표기 "2회차, 11월 10일"(같은 날이면 시각까지). 없으면 날짜만 */
  prevLabel?: string
  vsBase: { d: number; date: string } | null
  passes: [number, number]
  excluded: [string, number][]
  /** 수의사용 추가 섹션(AppVetSections) */
  vet: ReactNode
}

export type LegCard = { label: string; weak: boolean; c: string; dot: string; mets: { n: string; v: string; other: string; lower: boolean }[] }
/** 다리 네 개의 색·문구·수치(몸 그림과 3D 보기가 같이 쓴다). 웹 views.ts body_map 과 같은 규칙 */
export function legCards(result: SessionResultOut | null | undefined) {
  const { parts } = metsOf(result)
  const front = partOf('앞다리', parts.front.mets), hind = partOf('뒷다리', parts.hind.mets)
  const fills: Record<string, string> = {}
  const cards: Record<string, LegCard> = {}
  for (const [part, P] of [['front', front], ['hind', hind]] as const) {
    for (const side of ['l', 'r'] as const) {
      const code = (side === 'l' ? 'L' : 'R') + (part === 'front' ? 'F' : 'H')
      const on = P.si >= 5 && side === P.weak
      fills[code] = on ? P.lv[2] : P.lv === NA_LEVEL ? '#E9E4DC' : P.si < 5 ? '#DCEFE2' : '#E9E4DC'
      const other = side === 'l' ? 'r' : 'l'
      cards[code] = {
        label: LEGS.find(([, c]) => c === code)![2], weak: on, c: on ? P.lv[3] : '#5B6472', dot: fills[code],
        mets: parts[part].mets.map((m) => ({ n: m.n, v: `${m[side]}${m.u}`, other: `${m[other]}${m.u}`, lower: m[side] < m[other] })),
      }
    }
  }
  return { parts, front, hind, fills, cards }
}

export function AppReport(p: AppReportProps) {
  const { front, hind, fills, cards } = legCards(p.result)
  const sym = p.sym ?? 0
  const symLv = level(100 - sym)
  const prev = p.symHist.length > 1 ? p.symHist[p.symHist.length - 2] : null
  const quality = `걸은 횟수 ${p.passes[0]}번 중 ${p.passes[1]}번 사용`

  const Card = ({ code, align }: { code: string; align: 'l' | 'r' }) => {
    const g = cards[code]
    if (!g) return null
    const m0 = g.mets[0]
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', alignItems: align === 'r' ? 'flex-end' : 'flex-start', textAlign: align === 'r' ? 'right' : 'left' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', fontWeight: 800, color: g.c, flexDirection: align === 'r' ? 'row-reverse' : 'row' }}>
          <span style={{ width: 9, height: 9, borderRadius: 3, background: g.dot, border: '1px solid #B8B0A4' }} />{g.label}{g.weak ? ' (덜 씁니다)' : ''}
        </span>
        {p.kind === 'g' ? (m0 ? (
          <>
            <span style={{ fontSize: '12px', color: '#5B6472' }}>{m0.n}</span>
            <b style={{ fontSize: '18px', fontVariantNumeric: 'tabular-nums', color: g.weak ? g.c : '#1B2433' }}>{m0.v}</b>
          </>
        ) : null) : g.mets.map((m, i) => (
          <span key={i} style={{ fontSize: '12px', color: '#5B6472', fontVariantNumeric: 'tabular-nums', lineHeight: 1.4 }}>{m.n.replace(' 가동 범위', '')} <b style={{ fontSize: '12px', color: m.lower && g.weak ? g.c : '#1B2433' }}>{m.v}</b> <span style={{ color: '#5B6472' }}>/ {m.other}</span></span>
        ))}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {p.kind === 'g' ? (
        <div style={{ ...box({ border: '1.5px solid #E9D3C2', background: '#FFF9F4' }), display: 'grid', gridTemplateColumns: '64px 1fr', rowGap: '6px', columnGap: '10px', fontSize: '13px', lineHeight: 1.5 }}>
          <b style={{ color: '#A8481A' }}>주요 결과</b><span>{hind.si >= front.si ? hind.say : front.say}</span>
          <b style={{ color: '#A8481A' }}>측정 품질</b><span>{quality}</span>
          <b style={{ color: '#A8481A' }}>이전 대비</b><span>{p.sym == null ? '이 회차는 쓸 수 있는 통과가 없어 비교할 수 없어요' : prev ? `직전 회차(${p.prevLabel || prev[0]})보다 좌우 대칭 점수 ${sym - prev[1] > 0 ? '+' : ''}${r1(sym - prev[1])}점` : '첫 측정이라 비교할 회차가 없어요'}</span>
        </div>
      ) : null}

      {/* 좌우 대칭 점수 */}
      <div style={{ ...box({ background: '#FAF7F2' }), display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '14px', alignItems: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#5B6472' }}>좌우 대칭 점수</span>
          <b style={{ fontSize: '28px', letterSpacing: '-1px', lineHeight: 1.1, color: symLv[3] }}>{p.sym == null ? '—' : sym}<span style={{ fontSize: '15px' }}>점</span></b>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ position: 'relative', height: 10, borderRadius: 5, background: 'linear-gradient(90deg,#F2A898 0%,#F2A898 60%,#F7D6AE 60%,#F7D6AE 80%,#DCEFE2 80%,#DCEFE2 100%)' }}>
            <span style={{ position: 'absolute', top: -4, left: `calc(${Math.max(0, Math.min(100, sym))}% - 2px)`, width: 4, height: 18, borderRadius: 2, background: '#1B2433' }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#5B6472' }}><span>0</span><span>80</span><span>90</span><span>100</span></div>
          <span style={{ fontSize: '12px', color: '#3A4250' }}>{p.vsBase ? <>기준 회차({p.vsBase.date})보다 <b style={{ color: p.vsBase.d > 0 ? '#2E8B57' : p.vsBase.d < 0 ? '#C2412D' : '#3A4250' }}>{p.vsBase.d > 0 ? '+' : ''}{r1(p.vsBase.d)}점</b></> : '기준 회차와 비교할 값이 없습니다'}</span>
        </div>
      </div>

      {/* 몸 그림 + 다리별 수치 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 104px 1fr', gap: '4px', alignItems: 'stretch' }}>
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-around' }}><Card code="LF" align="l" /><Card code="LH" align="l" /></div>
        <div style={{ width: 104, height: 256 }} dangerouslySetInnerHTML={{ __html: dogSvg(p.dogSize, fills, p.focus) }} />
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-around' }}><Card code="RF" align="r" /><Card code="RH" align="r" /></div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'center', gap: '10px', flexWrap: 'wrap', fontSize: '12px', color: '#5B6472' }}>
        {LEVEL.map(([, n, c], i) => <span key={i}><span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 3, background: c, border: '1px solid #B8B0A4', verticalAlign: -1, marginRight: 3 }} />{['좌우 비슷 (5% 미만)', '조금 덜 씀 (5~10%)', '많이 덜 씀 (10% 이상)'][i] ?? n}</span>)}
      </div>

      {/* 앞·뒷다리 한 줄 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {([['앞다리', front], ['뒷다리', hind]] as const).map(([label, P]) => (
          <div key={label} style={{ ...box({ border: '1px solid #ECE8E2' }), display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: 700 }}><span>{label}</span><span style={{ color: P.lv[3] }}>{P.lv[1]}</span></span>
            <span style={{ fontSize: p.kind === 'g' ? '14px' : '13px', lineHeight: 1.5, fontWeight: 600 }}>{P.say}</span>
            {p.kind === 'v' && P.worst ? <span style={{ fontSize: '12px', color: '#5B6472', lineHeight: 1.5 }}>가장 큰 차이: {P.worst.n} {r1(Math.abs(P.worst.l - P.worst.r))}{P.worst.u}, 대칭 지수 차이 {P.si}%</span> : null}
            {p.kind === 'g' && P.worst && READ[P.worst.n] ? <span style={{ fontSize: '12px', color: '#5B6472', lineHeight: 1.5 }}>{P.worst.n}: {READ[P.worst.n]}</span> : null}
          </div>
        ))}
      </div>

      {p.kind === 'g' ? <AppOwnerSummary front={front} hind={hind} /> : null}

      {/* 측정 품질 */}
      <div style={{ ...box({ background: '#FAF7F2' }), display: 'flex', flexWrap: 'wrap', gap: '6px 12px', fontSize: '13px' }}>
        <b>측정 품질</b><span>{quality}</span>
        <AppExcludeLine ex={p.excluded} kind={p.kind === 'v' ? 'v' : 'g'} />
        <AppQualityLine result={p.result} kind={p.kind === 'v' ? 'v' : 'g'} />
      </div>

      {p.kind === 'g' ? (p.symHist.length > 1 ? <SymTrend hist={p.symHist} /> : null) : p.vet}
    </div>
  )
}

function SymTrend({ hist }: { hist: [string, number][] }) {
  const h = hist.slice(-8)
  const vs = h.map(([, v]) => v)
  const lo = Math.min(...vs) - 3, hi = Math.max(...vs) + 3
  const X = (i: number) => 24 + (i * 272) / Math.max(1, h.length - 1)
  const Y = (v: number) => 80 - ((v - lo) / (hi - lo)) * 60
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
      <b style={{ fontSize: '14px' }}>지금까지 좌우 대칭 점수</b>
      <span style={{ fontSize: '12px', color: '#5B6472', lineHeight: 1.5 }}>점 하나가 그날 측정한 대칭 점수예요. 위로 갈수록 양쪽 다리를 고르게 썼어요</span>
      <svg viewBox="0 0 320 100" style={{ width: '100%' }}>
        <polyline points={h.map(([, v], i) => `${X(i)},${Y(v)}`).join(' ')} fill="none" stroke="#D2601A" strokeWidth="2.5" strokeLinejoin="round" />
        {h.map(([d, v], i) => (
          <g key={i}>
            <circle cx={X(i)} cy={Y(v)} r={i === h.length - 1 ? 5 : 3.5} fill={i === h.length - 1 ? '#D2601A' : '#fff'} stroke="#D2601A" strokeWidth="2" />
            <text x={X(i)} y={Y(v) - 9} textAnchor="middle" fontSize="12" fill="#3A4250" fontWeight={i === h.length - 1 ? 700 : 400}>{v}</text>
            <text x={X(i)} y={96} textAnchor="middle" fontSize="12" fill="#5B6472">{d}</text>
          </g>
        ))}
      </svg>
    </div>
  )
}
