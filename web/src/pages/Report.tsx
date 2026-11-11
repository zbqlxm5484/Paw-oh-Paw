// report.html + main.py result_detail()·report(): 회차 결과 = 보고서(보호자용·수의사용), 실패 회차는 다시 찍기 안내
import { Fragment, useCallback, useEffect, useState, type MouseEvent } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { staticUrl, usePage, useTitle } from '../app/page'
import { redirect, setToast, type Go } from '../app/session'
import { dogOf, resultOf } from '../store/db'
import { body_map, memo_panel, owner_guide, result_view, seg } from '../views/views'
import { pystr } from '../views/pyfmt'
import { DogPanel } from './parts/DogPanel'
import { link } from '../config'
import { MOCK, isRemote, syncDogChart } from '../store/backend'
import type { Account, Result } from '../store/types'
import { PrintPdf } from './parts/ServerPdf'
import { VetSections } from './parts/VetSections'
import { api } from '../api/client'
import { kneeChartView, loadKneeCurve, type KneeChartView } from '../views/reportContent'

/** 서버의 RedirectResponse: 지금 주소를 바꿔 치운다 */
function useRedirect(g: Go | null) {
  const navigate = useNavigate()
  useEffect(() => {
    if (!g) return
    if (g.toast) setToast(g.toast)
    navigate(g.to, { replace: true })
  })
}

type BM = NonNullable<ReturnType<typeof body_map>>
type ResultView = NonNullable<ReturnType<typeof result_view>>

// 보호자용 "읽는 법"(PR-F08-08): 수치마다 같은 쪽에 한 줄. 판정·정상 범위는 말하지 않고 무엇을 잰 값인지만
const READ: Record<string, string> = {
  '팔꿈치 가동 범위': '걸을 때 팔꿈치를 접었다 펴는 폭이에요', '무릎 가동 범위': '걸을 때 무릎을 접었다 펴는 폭이에요',
  '고관절 가동 범위': '걸을 때 엉덩이 관절이 앞뒤로 움직이는 폭이에요', '걸음 길이': '한 걸음에 나아가는 거리예요(몸통 길이 대비)',
  '입각기 비율': '한 걸음 중 발이 땅을 딛고 있는 시간의 비율이에요',
}

// {% macro leg_card(code, align) %}
function LegCard({ bm, kind, code, align }: { bm: BM; kind: string; code: string; align: string }) {
  const g = bm.legs[code]
  const m0 = g.mets[0]
  return (
    <div style={css(`display:flex;flex-direction:column;gap:6px;align-items:${align === 'r' ? 'flex-end' : 'flex-start'};text-align:${align === 'r' ? 'right' : 'left'}`)}>
      <span style={css(`display:flex;align-items:center;gap:6px;font-size:14px;font-weight:800;color:${g.c};flex-direction:${align === 'r' ? 'row-reverse' : 'row'}`)}><span style={css(`width:12px;height:12px;border-radius:4px;background:${g.dot};border:1px solid #B8B0A4`)}></span>{g.label}{g.weak ? ' · 덜 씁니다' : ''}</span>
      {kind === 'g' ? (
        <>
          <span style={css('font-size:13px;color:#5B6472')}>{m0.n}</span>
          <b style={css(`font-size:24px;letter-spacing:-0.5px;font-variant-numeric:tabular-nums;color:${g.weak ? g.c : '#1B2433'}`)}>{m0.v}</b>
        </>
      ) : (
        g.mets.map((m, i) => (
          <span key={i} style={css('font-size:13px;color:#5B6472;font-variant-numeric:tabular-nums')}>{m.n} <b style={css(`font-size:15px;color:${m.lower && g.weak ? g.c : '#1B2433'}`)}>{m.v}</b> <span style={css('color:#A0A7B2')}>/ {m.other}</span></span>
        ))
      )}
    </div>
  )
}

/** 첫 쪽 요약(PR-F08-05): 주요 결과 · 측정 품질 · 이전 대비 변화 */
function FirstSummary({ bm, rd }: { bm: BM; rd: { pm?: unknown; pu?: unknown; part?: unknown } }) {
  const prev = bm.trend.length > 1 ? bm.trend[bm.trend.length - 2] : null
  return (
    <div style={css('display:grid;grid-template-columns:88px 1fr;row-gap:8px;column-gap:14px;padding:16px 20px;border-radius:14px;border:1.5px solid #E9D3C2;background:#FFF9F4;font-size:14.5px;line-height:1.5')}>
      <b style={css('color:#A8481A')}>주요 결과</b><span>{owner_guide(bm).summary}</span>
      <b style={css('color:#A8481A')}>측정 품질</b><span>걸은 횟수 {String(rd.pm)}번 중 {String(rd.pu)}번을 분석에 썼어요{rd.part ? ' · 일부만 써서 덜 정확할 수 있어요' : ''}</span>
      <b style={css('color:#A8481A')}>이전 대비</b><span>{prev ? `지난 측정(${prev.t})보다 좌우 대칭 점수 ${bm.sym > prev.v ? '+' : ''}${bm.sym - prev.v}점` : '첫 측정이라 비교할 회차가 없어요'}</span>
    </div>
  )
}

/** 보호자가 알아 두면 좋은 점(둘째 쪽 시작). 병명·질환 가능성은 말하지 않는다 */
function OwnerGuideBox({ bm }: { bm: BM }) {
  const og = owner_guide(bm)
  return (
    <div className="rep-p2" style={css('display:flex;flex-direction:column;gap:14px')}>
      <b style={css('font-size:18px')}>보호자가 알아 두면 좋은 점</b>
      <div style={css('padding:14px 18px;border-radius:12px;background:#FFF9F4;border:1px solid #F0DCCB;font-size:15px;line-height:1.6;font-weight:600')}>{og.what}</div>
      <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:12px')}>
        {og.look.length ? (
          <div style={css('padding:14px 18px;border-radius:12px;border:1px solid #ECE8E2;display:flex;flex-direction:column;gap:8px')}>
            <b style={css('font-size:14px;color:#3A4250')}>집에서 보일 수 있는 모습</b>
            {og.look.map((x) => <span key={x} style={css('font-size:14px;line-height:1.55;padding-left:12px;border-left:3px solid #F2C9AE')}>{x}</span>)}
          </div>
        ) : null}
        <div style={css('padding:14px 18px;border-radius:12px;border:1px solid #ECE8E2;display:flex;flex-direction:column;gap:8px')}>
          <b style={css('font-size:14px;color:#3A4250')}>집에서 도와줄 수 있는 것</b>
          {og.help.map((x) => <span key={x} style={css('font-size:14px;line-height:1.55;padding-left:12px;border-left:3px solid #CFE3D6')}>{x}</span>)}
        </div>
      </div>
      <div style={css('padding:12px 18px;border-radius:12px;background:#FBEAE6;font-size:14px;line-height:1.6;color:#8A2E1E')}><b>이럴 땐 담당 수의사에게 바로 알려 주세요</b><div style={css('margin-top:6px;display:flex;flex-direction:column;gap:2px')}>{og.urgent.map((u, i) => <span key={i}>· {u}</span>)}</div></div>
      <span style={css('font-size:12px;color:#8E949C')}>일반적인 안내예요. 우리 아이에게 맞는 관리는 담당 수의사와 상의해 주세요.</span>
    </div>
  )
}

const BTN = 'height:44px;padding:0 18px;border-radius:12px;background:#fff;border:1px solid #E2DCD3;display:flex;align-items:center;font-size:15px;font-weight:700'

export default function Report() {
  const { rid = '' } = useParams()
  const loc = useLocation()
  const navigate = useNavigate()
  const isOld = loc.pathname.endsWith('/report') // 예전 보고서 주소(로그인 확인 없이 회차 결과로 보낸다)
  const { acct, me, toast, query } = usePage({ login: !isOld })
  const type = query.get('type') ?? 'g'
  const r = acct && !isOld ? resultOf(acct, rid) : undefined
  const d = acct && r ? dogOf(acct, r.dog) : undefined
  const v = acct && r ? result_view(acct, r) : null
  useTitle(`${v ? v.rd.name : ''} 분석 결과 · Paw oh Paw`)
  // 오른쪽 칸 메모·진료 기록: 백엔드 기관이면 그 반려견 차트를 서버에서 읽는다(271)
  const acctId = acct?.id ?? '', dogId = d?.id ?? ''
  useEffect(() => {
    if (acctId && dogId && isRemote(acctId)) void syncDogChart(acctId, dogId).catch(() => undefined)
  }, [acctId, dogId])
  // PDF 저장 파일명: "261108 콩이 분석 결과 (보호자용)" — 회차 측정일 YYMMDD
  const pdfName = r ? `${r.day.replace(/-/g, '').slice(2)} ${v ? v.rd.name : ''} 분석 결과 (${type === 'v' ? '수의사용' : '보호자용'})` : undefined
  let go: Go | null = null
  if (isOld) go = redirect(`/results/${rid}?type=${type}`)
  else if (acct && !r) go = redirect('/home', '회차를 찾을 수 없습니다')
  useRedirect(go)
  if (!acct || !r || !v || go) return null

  const rd = v.rd
  const panel = d ? memo_panel(acct, d, r.id) : null
  const fail = r.st === 'fail'
  const fromServer = !MOCK && (r.src ?? '').startsWith('backend:') // 백엔드 회차(수의사용 실제 각도 등 서버 값을 쓴다). PDF 는 회차와 상관없이 화면 그대로 브라우저 인쇄
  const kind = fail ? 'v' : type === 'g' || type === 'v' ? type : 'g'
  const rp = v.rp
  const bm = fail ? null : body_map(acct, r)
  const segs = fail ? [] : seg([['g', '보호자용'], ['v', '수의사용']], kind)
  const status = fail ? '' : `분석 모델 ${r.model}`
  const rel = (href: string) => (e: MouseEvent) => {
    if (e.button !== 0 || e.metaKey || e.ctrlKey) return
    e.preventDefault()
    navigate(loc.pathname + href)
  }
  const next_url = `/results/${rd.id}` + (!rd.fail ? `?type=${kind}` : '')

  return (
    <Base acct={acct} me={me} toast={toast}>
      <main className="print-main" style={css('max-width:1320px;margin:0 auto;padding:24px 32px 96px;display:flex;gap:24px;align-items:flex-start')}>
        <div style={css('flex:1;min-width:0;max-width:920px;display:flex;flex-direction:column;gap:20px')}>
          <div className="no-print" style={css('display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap')}>
            <a className="lk" href={link(`/dogs/${rd.dog}`)} style={css('display:flex;align-items:center;gap:4px;font-size:14px;font-weight:600;color:#5B6472')}><svg width="16" height="16" viewBox="0 0 24 24"><use href="#w-back"></use></svg>{rd.name} 차트</a>
            {!rd.fail ? (
              <div style={css('display:flex;gap:10px;flex-wrap:wrap')}><a className="lk hv-border" href={link(`/compare/${rd.dog}`)} style={css(BTN)}>경과 비교</a><a className="lk hv-border" href={link(`/results/${rd.id}/3d`)} style={css(BTN)}>3D로 보기</a><PrintPdf fileName={pdfName} /></div>
            ) : null}
          </div>
          {rd.fail || !bm ? (
            <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:28px;display:flex;flex-direction:column;gap:12px')}>
              <div style={css('display:flex;align-items:center;gap:10px')}><b style={css('font-size:20px')}>{rd.name} · {rd.when}</b><span style={css(`padding:4px 10px;border-radius:8px;background:${rd.bg};color:${rd.c};font-size:13px;font-weight:700`)}>{rd.st}</span></div>
              <b style={css('font-size:17px')}>분석하지 못했습니다</b>
              <span style={css('font-size:15px;line-height:1.6;color:#5B6472')}>{r.fail_msg || '쓸 수 있는 통과가 없었습니다. 반려견이 뛰지 않고, 멈추거나 앉지 않고, 일직선으로 걷도록 다시 찍어 주세요.'}</span>
              {r.ex.length ? (
                <div style={css('display:flex;flex-wrap:wrap;gap:6px')}>{r.ex.map(([n, c], i) => <span key={i} style={css('height:28px;padding:0 10px;border-radius:8px;background:#F2EEE8;color:#3A4250;font-size:13px;font-weight:600;display:flex;align-items:center;font-variant-numeric:tabular-nums')}>{n} {c}회</span>)}</div>
              ) : null}
              <a className="lk hv-orange" href={link(`/upload?dog=${rd.dog}`)} style={css('align-self:flex-start;height:46px;padding:0 20px;border-radius:12px;background:#D2601A;color:#fff;display:flex;align-items:center;gap:8px;font-size:15px;font-weight:700')}><svg width="18" height="18" viewBox="0 0 24 24"><use href="#w-up"></use></svg>다시 올리기</a>
            </div>
          ) : (
            <>
              <div className="no-print" style={css('display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap')}>
                <div style={css('display:grid;grid-template-columns:1fr 1fr;padding:4px;border-radius:12px;background:#EEE8DF;width:320px;max-width:100%')}>
                  {segs.map((g) => <a key={g.key} className="lk" href={link(`?type=${g.key}`)} onClick={rel(`?type=${g.key}`)} style={css(`height:42px;border-radius:9px;background:${g.bg};color:${g.c};box-shadow:${g.sh};display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700;transition:background .2s`)}>{g.label}</a>)}
                </div>
                <span style={css('display:flex;align-items:center;gap:6px;font-size:13.5px;color:#5B6472;font-variant-numeric:tabular-nums')}><span style={css('width:7px;height:7px;border-radius:4px;background:#2E8B57')}></span>{status}</span>
              </div>

              <ReportPaper acct={acct} r={r} rd={rd} rp={rp} bm={bm} kind={kind} fromServer={fromServer} />
            </>
          )}
        </div>
        {panel ? <DogPanel panel={panel} next_url={next_url} /> : null}
      </main>
    </Base>
  )
}

/** 수의사용 뒷무릎 곡선(백엔드 회차): 이 회차 영상의 실제 관절 각도(GET /sessions/{id} → /shots/{id}/angles)로만 그린다.
 *  undefined = 읽는 중, null = 못 만듦(그 칸을 뺀다). 측정값이 아닌 합성 곡선은 싣지 않는다(11-10) */
function useRealKnee(sessionId: string | null): KneeChartView | null | undefined {
  const [state, setState] = useState<{ id: string; v: KneeChartView | null }>({ id: '', v: null })
  useEffect(() => {
    if (!sessionId) return
    let alive = true
    loadKneeCurve({ session: (id) => api.session(id), angles: (id) => api.angles(id) }, sessionId, null)
      .then((k) => alive && setState({ id: sessionId, v: k ? kneeChartView(k) : null }))
      .catch(() => alive && setState({ id: sessionId, v: null }))
    return () => {
      alive = false
    }
  }, [sessionId])
  if (!sessionId) return null
  return state.id === sessionId ? state.v : undefined
}

/** 보고서 종이 한 장(화면·인쇄 공용). 회차 결과 화면과 인쇄 전용 화면(/print/reports/:rid)이 같이 쓴다 */
export function ReportPaper({ acct, r, rd, rp, bm, kind, fromServer, onReady }: {
  acct: Account; r: Result; rd: ResultView['rd']; rp: ResultView['rp']; bm: BM; kind: string; fromServer: boolean; onReady?: () => void
}) {
  // 백엔드 회차의 무릎 곡선은 실제 각도로만. 시연 데이터 회차는 회차에 붙은 곡선(rd.kc)
  const sid = fromServer && kind === 'v' ? ((r.src ?? '').split(':')[1] || r.id) : null
  const realKnee = useRealKnee(sid)
  const kneeEl = !fromServer ? <div className="rep-sec"><KneeChart kc={rd.kc} /></div> : realKnee ? <div className="rep-sec"><KneeChart kc={realKnee} /></div> : null
  // 인쇄 준비 완료: 지난 측정 비교(VetSections)와 무릎 곡선을 모두 받은 뒤
  const [vetReady, setVetReady] = useState(false)
  const vetDone = useCallback(() => setVetReady(true), [])
  useEffect(() => {
    if (vetReady && realKnee !== undefined) onReady?.()
  }, [vetReady, realKnee, onReady])
  return (
    <div className="print-paper" style={css('background:#fff;border-radius:6px;box-shadow:0 18px 50px rgba(27,36,51,.1);padding:48px 52px;display:flex;flex-direction:column;gap:22px;min-height:960px')}>
      <div style={css('display:flex;align-items:center;justify-content:space-between')}><div style={css('display:flex;align-items:center;gap:8px;font-size:15px;font-weight:800')}><img src={staticUrl('assets/logo.png')} alt="" style={css('width:28px;height:28px;object-fit:contain')} />Paw oh Paw</div><span style={css('font-size:13px;color:#5B6472')}>{kind === 'v' ? '보행 분석 보고서 · 수의사용' : '보행 분석 보고서 · 보호자용'}</span></div>
      <div style={css('height:3px;background:#D2601A;width:56px')}></div>
      <div><div style={css('font-size:32px;font-weight:800;letter-spacing:-0.9px')}>{rp.title}</div><div style={css('font-size:14px;color:#5B6472;margin-top:6px')}>{rp.when}</div></div>

      {kind === 'g' ? <FirstSummary bm={bm} rd={rd} /> : null}

      {/* 한눈에: 좌우 대칭 점수 */}
      <div style={css('display:grid;grid-template-columns:auto 1fr;gap:22px;align-items:center;padding:20px 22px;border-radius:14px;background:#FAF7F2')}>
        <div style={css('display:flex;flex-direction:column;gap:2px')}>
          <span style={css('font-size:13.5px;font-weight:700;color:#5B6472')}>좌우 대칭 점수</span>
          <b style={css(`font-size:44px;letter-spacing:-1px;line-height:1.1;color:${bm.sym_level[3]}`)}>{bm.sym}<span style={css('font-size:20px')}>점</span></b>
        </div>
        <div style={css('display:flex;flex-direction:column;gap:8px')}>
          <div style={css('position:relative;height:12px;border-radius:6px;background:linear-gradient(90deg,#F2A898 0%,#F2A898 60%,#F7D6AE 60%,#F7D6AE 80%,#DCEFE2 80%,#DCEFE2 100%)')}>
            <span style={css(`position:absolute;top:-5px;left:calc(${bm.sym}% - 2px);width:4px;height:22px;border-radius:2px;background:#1B2433`)}></span>
          </div>
          <div style={css('display:flex;justify-content:space-between;font-size:11.5px;color:#8E949C')}><span>0</span><span>80</span><span>90</span><span>100 (완전 대칭)</span></div>
          {kind === 'g' ? <span style={css('font-size:12px;color:#8E949C')}>왼쪽·오른쪽 다리를 얼마나 고르게 쓰는지예요. 100에 가까울수록 양쪽을 비슷하게 써요</span> : null}
          <span style={css('font-size:14.5px;color:#3A4250')}>{bm.vs_base != null ? <>기준 회차({bm.base_date})보다 <b style={css(`color:${bm.vs_base > 0 ? '#2E8B57' : bm.vs_base < 0 ? '#C2412D' : '#3A4250'}`)}>{bm.vs_base > 0 ? '+' : ''}{bm.vs_base}점</b></> : '첫 측정입니다'}{bm.focus ? <> · 관심 다리 <b>{bm.focus}</b>(점선)</> : null}</span>
        </div>
      </div>

      {/* 몸 그림 + 다리별 수치 */}
      <div style={css('display:grid;grid-template-columns:1fr 228px 1fr;align-items:stretch;gap:8px')}>
        <div style={css('position:relative')}>
          <div style={css('position:absolute;top:23%;left:0;right:8px')}><LegCard bm={bm} kind={kind} code="LF" align="l" /></div>
          <div style={css('position:absolute;top:70%;left:0;right:8px')}><LegCard bm={bm} kind={kind} code="LH" align="l" /></div>
        </div>
        <div className="rep-map" style={css('width:228px;height:560px')} dangerouslySetInnerHTML={{ __html: bm.svg }}></div>
        <div style={css('position:relative')}>
          <div style={css('position:absolute;top:23%;right:0;left:8px')}><LegCard bm={bm} kind={kind} code="RF" align="r" /></div>
          <div style={css('position:absolute;top:70%;right:0;left:8px')}><LegCard bm={bm} kind={kind} code="RH" align="r" /></div>
        </div>
      </div>
      <div style={css('display:flex;justify-content:center;gap:16px;flex-wrap:wrap;font-size:12.5px;color:#5B6472')}>
        <span><span style={css('display:inline-block;width:11px;height:11px;border-radius:3px;background:#DCEFE2;border:1px solid #B8B0A4;vertical-align:-1px')}></span> 좌우 비슷 (차이 5% 미만)</span>
        <span><span style={css('display:inline-block;width:11px;height:11px;border-radius:3px;background:#F7D6AE;border:1px solid #B8B0A4;vertical-align:-1px')}></span> 조금 덜 씀 (5~10%)</span>
        <span><span style={css('display:inline-block;width:11px;height:11px;border-radius:3px;background:#F2A898;border:1px solid #B8B0A4;vertical-align:-1px')}></span> 많이 덜 씀 (10% 이상)</span>
      </div>

      {/* 다리 한 쌍씩 한 줄 설명 */}
      <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:12px')}>
        {([['front', '앞다리'], ['hind', '뒷다리']] as const).map(([part, label]) => {
          const p = bm.legs[part]
          return (
            <div key={part} style={css('padding:16px 18px;border-radius:12px;border:1px solid #ECE8E2;display:flex;flex-direction:column;gap:6px')}>
              <span style={css('display:flex;justify-content:space-between;font-size:13.5px;font-weight:700')}><span>{label}</span><span style={css(`color:${p.c}`)}>{p.level}</span></span>
              <span style={css(`font-size:${kind === 'g' ? '16px' : '14.5px'};line-height:1.55;font-weight:600`)}>{p.say}</span>
              {kind === 'v' ? <span style={css('font-size:13px;color:#5B6472')}>가장 큰 차이: {p.metric} {p.diff} · 대칭 지수 차이 {pystr(p.si)}%</span>
                : <span style={css('font-size:13px;line-height:1.5;color:#5B6472')}>{p.metric} 왼쪽 <b style={css('color:#1B2433')}>{p.left}</b> · 오른쪽 <b style={css('color:#1B2433')}>{p.right}</b>{READ[p.metric] ? <><br /><span style={css('color:#8E949C')}>{READ[p.metric]}</span></> : null}</span>}
            </div>
          )
        })}
      </div>

      {/* 측정 품질: 쓴 통과·뺀 통과와 이유를 숨김없이 (REQ-GD-005, PR-F08-05). 보호자용은 바로 위 안내 상자에서 둘째 쪽, 수의사용은 첫 쪽 끝(11-05) */}
      {kind === 'g' ? <OwnerGuideBox bm={bm} /> : null}

      <div style={css('display:flex;align-items:center;gap:18px;flex-wrap:wrap;padding:14px 18px;border-radius:12px;background:#FAF7F2;font-size:14px')}>
        <b>측정 품질</b>
        <span>걸은 횟수 {rd.pm}번 중 <b>{rd.pu}번</b> 사용</span>
        {rd.ex && rd.ex.length ? <span style={css('color:#5B6472')}>뺀 이유: {(rd.ex as [string, number][]).map(([n, c]) => `${n} ${c}번`).join(', ')}</span> : null}
        {rd.part ? <span style={css('color:#9A6A12;font-weight:700')}>일부만 사용해서 결과가 덜 정확할 수 있습니다</span> : null}
        {kind === 'g' ? <span style={css('flex-basis:100%;font-size:12px;color:#8E949C')}>걸은 횟수는 영상에서 반려견이 화면을 지나간 횟수예요. 뛰거나 멈춘 걸음은 빼고 계산해요</span> : null}
      </div>

      {kind === 'g' ? (
        /* 지금까지 변화 */
        bm.trend.length > 1 ? (
          <div style={css('display:flex;flex-direction:column;gap:6px')}>
            <b style={css('font-size:15px')}>지금까지 좌우 대칭 점수</b>
            <span style={css('font-size:12px;color:#8E949C')}>점 하나가 그날 측정한 대칭 점수예요. 위로 갈수록 양쪽 다리를 고르게 썼어요</span>
            <svg className="rep-trend" viewBox="0 0 360 100" style={css('width:100%;max-width:560px')}>
              <polyline points={bm.trend_line} fill="none" stroke="#D2601A" strokeWidth="2.5" strokeLinejoin="round"></polyline>
              {bm.trend.map((p, i) => (
                <Fragment key={i}><circle cx={p.x} cy={p.y} r={p.cur ? 5 : 3.5} fill={p.cur ? '#D2601A' : '#fff'} stroke="#D2601A" strokeWidth="2"></circle><text x={p.x} y={p.y - 9} textAnchor="middle" fontSize="10" fill="#3A4250" fontWeight={p.cur ? 700 : 400}>{p.v}</text><text x={p.x} y="97" textAnchor="middle" fontSize="9.5" fill="#8E949C">{p.t}</text></Fragment>
              ))}
            </svg>
          </div>
        ) : null
      ) : (
        <>
          {/* 백엔드 보고서 시안 반영: 좌우 비교·지난 측정과 비교·무릎 가동 범위 변화·그 밖의 수치 */}
          <VetSections acct={acct} r={r} fromServer={fromServer} onReady={vetDone} knee={kneeEl} />
        </>
      )}
      <div style={css('flex:1')}></div>
      {/* 보호자용 용어 설명(보고서 검사 terms.yaml 의 설명 문구 그대로, 토씨까지 같아야 검사를 통과한다) */}
      {kind === 'g' ? <div style={css('display:flex;flex-direction:column;gap:3px;font-size:12px;color:#5B6472')}><b style={css('font-size:12.5px;color:#3A4250')}>용어 설명</b><span><b>좌우 대칭 점수</b>: 왼쪽·오른쪽 다리를 얼마나 고르게 쓰는지를 0~100 으로 나타낸 점수. 100에 가까울수록 고르게 씀</span><span><b>가동 범위</b>: 걸을 때 관절을 접었다 펴는 각도의 폭</span><span><b>오차 범위</b>: 같은 상태를 다시 재도 생길 수 있는 값의 차이</span><span><b>기준 회차</b>: 재활 시작 무렵에 잰 회차. 이후 변화를 견주는 기준</span></div> : null}
      <span style={css('font-size:12px;color:#A0A7B2')}>보행 평가 보조 자료이며 진단을 대신하지 않습니다.</span>
    </div>
  )
}

type Tick = { y: number; x: number; t: string }
type KC = { y: Tick[]; x: Tick[]; x0: number; x1: number; ref_band: string; ref_mean: string; L: string; R: string }

/** 수의사용: 뒷무릎 각도 · 보행 주기 */
export function KneeChart({ kc }: { kc: KC }) {
  return (
    <div>
      <b style={css('font-size:15px')}>뒷무릎 각도 · 보행 주기</b>
      <svg viewBox="0 0 320 150" style={css('width:100%;max-width:520px;display:block;margin-top:8px;font-family:inherit')}>
        <g stroke="#ECE8E2" strokeDasharray="3 4">{kc.y.map((t: Tick, i: number) => <line key={i} x1={kc.x0} y1={t.y} x2={kc.x1} y2={t.y}></line>)}</g>
        <g fontSize="9.5" fill="#8E949C">{kc.y.map((t: Tick, i: number) => <text key={i} x={kc.x0 - 5} y={t.y + 3} textAnchor="end">{t.t}</text>)}
          {kc.x.map((t: Tick, i: number) => <text key={'x' + i} x={t.x} y="133" textAnchor="middle">{t.t}</text>)}
          <text x={(kc.x0 + kc.x1) / 2} y="146" textAnchor="middle">한 걸음 (뒷발 착지 → 다음 착지, %)</text>
          <text x="10" y="66" textAnchor="middle" transform="rotate(-90 10 66)">무릎 각도</text></g>
        <polygon points={kc.ref_band} fill="#E9E6E1" opacity=".75"></polygon>
        <polyline points={kc.ref_mean} fill="none" stroke="#A0A7B2" strokeWidth="1.3" strokeDasharray="2 3"></polyline>
        <polyline points={kc.L} fill="none" stroke="#3B6FE0" strokeWidth="2"></polyline>
        <polyline points={kc.R} fill="none" stroke="#E5604D" strokeWidth="2" strokeDasharray="5 4"></polyline>
      </svg>
      <div style={css('display:flex;gap:14px;flex-wrap:wrap;font-size:12.5px;color:#5B6472;margin-top:4px')}>
        <span><span style={css('display:inline-block;width:16px;border-top:2px solid #3B6FE0;vertical-align:middle;margin-right:5px')}></span>왼쪽</span>
        <span><span style={css('display:inline-block;width:16px;border-top:2px dashed #E5604D;vertical-align:middle;margin-right:5px')}></span>오른쪽</span>
        <span><span style={css('display:inline-block;width:16px;height:9px;background:#E9E6E1;vertical-align:middle;margin-right:5px')}></span>정상 참고 범위</span>
      </div>
    </div>
  )
}
