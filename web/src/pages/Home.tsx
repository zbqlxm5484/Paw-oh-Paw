// home.html + main.py home(): 버튼으로 목록 하나(오늘·분석·반려견·촬영 담당자)만 띄운다. 반려견을 누르면 반려견 차트로 간다.
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { GetForm, usePage, useTitle } from '../app/page'
import { dogOf, isoToday } from '../store/db'
import { activity_days, fmt_date, home_view } from '../views/views'
import { PetModal } from './parts/Modals'
import { DayPicker, dayLabel } from './parts/DayPicker'
import { VV } from './parts/Vital'
import { link } from '../config'
import { isRemote, syncTodayCharts } from '../store/backend'

// EMR 첫 화면처럼 오늘 온 반려견부터(11-02)
const HOME_VIEWS: [string, string][] = [['today', '오늘'], ['analyses', '분석'], ['dogs', '반려견'], ['staff', '촬영 담당자']]

const tone: Record<string, [string, string]> = {
  surg: ['#FCEEE3', '#A8481A'], diag: ['#EEF1F6', '#4A5A78'], warn: ['#FAF1DF', '#9A6A12'],
  bad: ['#F8E7E3', '#C2412D'], good: ['#E8F3EC', '#2E8B57'], plain: ['#F0EEEA', '#5B6472'],
}

interface Chip { t: string; bg: string; c: string }
interface Badge { t: string; full?: string; kind: string }

/** FastAPI 의 int 쿼리: 숫자가 아니면 기본값 */
const intParam = (s: string | null, dflt: number): number => (s && /^[+-]?\d+$/.test(s.trim()) ? parseInt(s, 10) : dflt)

export default function Home() {
  const { acct, me, toast, query } = usePage({ login: true })
  const navigate = useNavigate()
  useTitle('홈 · Paw oh Paw')
  const dog = query.get('dog') || ''
  const toDog = acct && dog && dogOf(acct, dog) ? `/dogs/${dog}` : ''
  useEffect(() => {
    if (toDog) navigate(toDog, { replace: true }) // 반려견은 차트에서 본다
  }, [toDog, navigate])
  // 서버 기관: 오늘 진료 기록·바이탈이 있는 반려견 차트를 뒤에서 읽어 '오늘' 목록을 채운다(차트를 안 열어 본 반려견도)
  const acctId = acct?.id ?? ''
  useEffect(() => {
    if (acctId && isRemote(acctId)) void syncTodayCharts(acctId, isoToday()).catch(() => undefined)
  }, [acctId])
  if (!acct || toDog) return null

  const q = query.get('q') || ''
  const by = query.get('by') || ''
  const changed = query.get('changed') || ''
  const stage = query.get('stage') || ''
  const modal = query.get('modal') || ''
  const page_no = intParam(query.get('page'), 1)
  const v0 = query.get('view') ?? 'today'
  const view = by ? 'analyses' : HOME_VIEWS.some(([k]) => k === v0) ? v0 : 'today'
  // 오늘 탭의 날짜(달력). 형식이 틀리거나 오늘 이후면 오늘
  const d0 = query.get('d') || ''
  const day = /^\d{4}-\d{2}-\d{2}$/.test(d0) && d0 <= isoToday() ? d0 : isoToday()
  const hv = home_view(acct, view, q, '', by, changed === 'retake' ? 'retake' : !!changed, stage, page_no, day)
  const keep: Record<string, string | number> = { view, q, by, changed, stage, d: day === isoToday() ? '' : day }
  const qs = (kw: Record<string, string | number>): string => {
    const p = new URLSearchParams()
    for (const [k, v] of Object.entries({ ...keep, ...kw })) if (v) p.append(k, String(v))
    return '/home?' + p.toString()
  }
  const today = fmt_date(isoToday())
  const today_iso = day
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rows: any[] = hv.rows

  const cards: [string, number, string, boolean, boolean][] = [
    ['전체 반려견', hv.dogs, qs({ view: 'dogs', changed: '', by: '', page: '' }), view === 'dogs' && !changed, false],
    ['일주일 간 변동 발생', hv.changed, qs({ view: 'dogs', changed: '1', by: '', page: '' }), view === 'dogs' && changed === '1', false],
    ['재촬영 필요', hv.retake, qs({ view: 'dogs', changed: 'retake', by: '', page: '' }), view === 'dogs' && changed === 'retake', true],
  ]
  const bt = (i: number) => (i ? '1px solid #F2EFEA' : 'none')

  let table
  if (view === 'today') {
    const cols = '70px minmax(190px,1.4fr) minmax(170px,1.3fr) minmax(220px,1.6fr) minmax(120px,.8fr) 110px'
    const colsN = '64px minmax(150px,1.2fr) minmax(120px,1fr) minmax(170px,1.4fr) 104px' // 좁은 창: 담당 칸 숨김
    table = (
      <div className="tbl" style={css('--tw:900px;--tw-n:680px')}>
        <div className="tbl-r" style={css(`--tc:${cols};--tc-n:${colsN};display:grid;gap:12px;padding:12px 20px;background:#FAF7F2;border-bottom:1px solid #ECE8E2;font-size:13px;font-weight:700;color:#7A808A`)}>
          <span>시각</span><span>반려견</span><span>병명</span><span>{day === isoToday() ? '오늘 한 것' : '그날 한 것'}</span><span className="tbl-opt">담당</span><span>진료 기록</span>
        </div>
        {rows.map((r, i) => (
          <div key={r.id} className="hv-row tbl-r" data-href={`/dogs/${r.id}`} style={css(`--tc:${cols};--tc-n:${colsN};display:grid;gap:12px;padding:12px 20px;border-top:${bt(i)};align-items:center;cursor:pointer;background:#fff`)}>
            <b style={css('font-size:15px;font-variant-numeric:tabular-nums')}>{r.time}</b>
            <span style={css('display:flex;flex-direction:column;gap:2px;min-width:0')}>
              <span style={css('font-size:12px;color:#8E949C;font-variant-numeric:tabular-nums')}>{r.no}</span>
              <span style={css('white-space:nowrap;overflow:hidden;text-overflow:ellipsis')}><b style={css('font-size:15.5px')}>{r.name}</b>{' '}<span style={css('font-size:13.5px;color:#5B6472')}>({r.breed})</span></span>
            </span>
            <span style={css('font-size:14.5px;font-weight:600;color:#3A4250;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap')} title={r.dx}>{r.dx}</span>
            <span style={css('display:flex;gap:5px;flex-wrap:wrap')}>{r.steps.map((s: Chip, j: number) => <span key={j} style={css(`padding:3px 9px;border-radius:7px;background:${s.bg};color:${s.c};font-size:12.5px;font-weight:700`)}>{s.t}</span>)}</span>
            <span className="tbl-opt" style={css('font-size:13.5px;color:#5B6472;white-space:nowrap;overflow:hidden;text-overflow:ellipsis')}>{r.who}</span>
            <span>{r.todo ? <a className="lk" href={link(`/dogs/${r.id}?v=${today_iso}`)} style={css('padding:4px 10px;border-radius:8px;border:1px solid #D2601A;color:#B4501A;font-size:12.5px;font-weight:700;white-space:nowrap')}>{r.todo} ›</a> : <span style={css('font-size:13px;color:#2E7A4F;font-weight:700')}>작성함</span>}</span>
          </div>
        ))}
      </div>
    )
  } else if (view === 'analyses') {
    const cols = '104px minmax(190px,1.5fr) minmax(170px,1.4fr) 66px 128px 96px minmax(100px,.8fr)'
    const colsN = '92px minmax(140px,1.3fr) minmax(110px,1fr) 56px 110px 88px' // 좁은 창: 촬영 칸 숨김
    table = (
      <div className="tbl" style={css('--tw:900px;--tw-n:680px')}>
        <div className="tbl-r" style={css(`--tc:${cols};--tc-n:${colsN};display:grid;gap:12px;padding:12px 20px;background:#FAF7F2;border-bottom:1px solid #ECE8E2;font-size:13px;font-weight:700;color:#7A808A`)}>
          <span>측정일</span><span>반려견</span><span>병명</span><span>회차</span><span>대칭 지수</span><span>상태</span><span className="tbl-opt">촬영</span>
        </div>
        {rows.map((r, i) => (
          <div key={r.id} className="hv-row tbl-r" data-href={`/results/${r.id}`} style={css(`--tc:${cols};--tc-n:${colsN};display:grid;gap:12px;padding:12px 20px;border-top:${bt(i)};align-items:center;cursor:pointer;background:#fff`)}>
            <span style={css('font-size:14px;color:#5B6472;font-variant-numeric:tabular-nums')}>{r.when}</span>
            <span style={css('display:flex;flex-direction:column;gap:2px;min-width:0')}>
              <span style={css('font-size:12px;color:#8E949C;font-variant-numeric:tabular-nums')}>{r.no}</span>
              <span style={css('white-space:nowrap;overflow:hidden;text-overflow:ellipsis')}><a className="lk" href={link(`/dogs/${r.dog}`)} style={css('font-size:15.5px;font-weight:700;border-bottom:1px dashed #C9C2B8')}>{r.name}</a>{' '}<span style={css('font-size:13.5px;color:#5B6472')}>({r.breed})</span></span>
            </span>
            <span style={css('font-size:14.5px;font-weight:600;color:#3A4250;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap')} title={r.dx}>{r.dx}</span>
            <span style={css('font-size:14px;color:#5B6472')}>{r.no_s}</span>
            <span style={css('display:flex;align-items:center;gap:6px')}><b style={css(`padding:4px 10px;border-radius:8px;background:${r.sym_bg};color:${r.sym_c};font-size:14px;font-variant-numeric:tabular-nums`)}>{r.sym}</b>{r.sym_d ? <span style={css(`font-size:12.5px;font-weight:700;color:${r.sym_dc}`)}>{r.sym_d}</span> : null}</span>
            <span><span style={css(`padding:4px 9px;border-radius:8px;background:${r.bg};color:${r.c};font-size:12.5px;font-weight:700;white-space:nowrap`)}>{r.st}</span></span>
            <a className="lk tbl-opt" href={link(qs({ by: r.by, page: '' }))} style={css('font-size:13.5px;color:#5B6472;white-space:nowrap;overflow:hidden;text-overflow:ellipsis')}>{r.by}</a>
          </div>
        ))}
      </div>
    )
  } else if (view === 'dogs') {
    const cols = 'minmax(140px,1fr) minmax(130px,.9fr) minmax(190px,1.2fr) minmax(200px,1.6fr) ' + (changed ? 'minmax(150px,1.1fr) ' : '') + '110px 84px'
    const colsN = 'minmax(120px,1fr) minmax(212px,1.2fr) ' + (changed ? 'minmax(130px,1.1fr) ' : 'minmax(150px,1.4fr) ') + '78px' // 좁은 창
    const dxOpt = changed ? 'tbl-opt' : undefined
    table = (
      <div className="tbl" style={css(`--tw:${changed ? 1080 : 940}px;--tw-n:620px`)}>
        <div className="tbl-r" style={css(`--tc:${cols};--tc-n:${colsN};display:grid;gap:14px;padding:12px 20px;background:#FAF7F2;border-bottom:1px solid #ECE8E2;font-size:13px;font-weight:700;color:#7A808A`)}>
          <span>반려견</span><span className="tbl-opt">견종 · 체급</span><span>체중 · 체온 · 심박 · 혈압</span><span className={dxOpt}>수술 · 진단</span>{changed ? <span>일주일 간 변동</span> : null}<span className="tbl-opt">분석</span><span>단계</span>
        </div>
        {rows.map((r, i) => {
          const bs = r.badges.filter((b: Badge) => b.kind !== 'warn')
          return (
            <div key={r.id} className="hv-row tbl-r" data-href={`/dogs/${r.id}`} style={css(`--tc:${cols};--tc-n:${colsN};display:grid;gap:14px;padding:13px 20px;border-top:${bt(i)};align-items:center;cursor:pointer`)}>
              <div style={css('display:flex;flex-direction:column;gap:2px;min-width:0')}><span style={css('font-size:12.5px;color:#8E949C;font-variant-numeric:tabular-nums')}>{r.no}</span><b style={css('font-size:16px')}>{r.name}</b><span style={css('font-size:13px;color:#5B6472')}>{r.sex} · {r.age}</span><span className="tbl-n" style={css('font-size:13px;color:#5B6472')}>{r.breed} · {r.size}</span></div>
              <div className="tbl-opt" style={css('display:flex;flex-direction:column;gap:2px')}><span style={css('font-size:14.5px;font-weight:600')}>{r.breed}</span><span style={css('font-size:13px;color:#5B6472')}>{r.size}</span></div>
              <div style={css('display:grid;grid-template-columns:repeat(4,auto);justify-content:start;column-gap:12px;row-gap:2px;font-variant-numeric:tabular-nums')}>
                {['체중', '체온', '심박', '혈압'].map((k) => <span key={k} style={css('font-size:11.5px;color:#8E949C;white-space:nowrap')}>{k}</span>)}
                {['kg', 'temp', 'hr', 'bp'].map((key) => <VV key={key} value={r.v[key]} f={r.v.f[key]} size={14} />)}
              </div>
              <div className={dxOpt} style={css('display:flex;flex-wrap:wrap;gap:5px;min-width:0')}>
                {bs.map((b: Badge, j: number) => <span key={j} title={b.full || b.t} style={css(`padding:4px 9px;border-radius:8px;background:${tone[b.kind][0]};color:${tone[b.kind][1]};font-size:12.5px;font-weight:700;white-space:nowrap;max-width:100%;overflow:hidden;text-overflow:ellipsis`)}>{b.t}</span>)}
                {!bs.length ? <span style={css('font-size:13px;color:#A0A7B2')}>없음</span> : null}
              </div>
              {changed ? <div style={css('display:flex;flex-wrap:wrap;gap:5px')}>{r.changes.map((c: { t: string; tone: string }, j: number) => <span key={j} style={css(`padding:4px 9px;border-radius:8px;background:${tone[c.tone][0]};color:${tone[c.tone][1]};font-size:12.5px;font-weight:700;white-space:nowrap`)}>{c.t}</span>)}</div> : null}
              <div className="tbl-opt" style={css('display:flex;flex-direction:column;gap:2px')}><b style={css('font-size:14.5px')}>{r.n}건</b><span style={css('font-size:12px;color:#8E949C')}>{r.last}</span></div>
              <span><span style={css(`padding:4px 10px;border-radius:8px;background:${r.st_bg};color:${r.st_c};font-size:13px;font-weight:700;white-space:nowrap`)}>{r.stage}</span></span>
            </div>
          )
        })}
      </div>
    )
  } else {
    const cols = 'minmax(180px,1.4fr) 110px 110px 110px 120px'
    const colsN = cols
    table = (
      <div className="tbl" style={css('--tw:640px')}>
        <div className="tbl-r" style={css(`--tc:${cols};--tc-n:${colsN};display:grid;gap:12px;padding:12px 20px;background:#FAF7F2;border-bottom:1px solid #ECE8E2;font-size:13px;font-weight:700;color:#7A808A`)}>
          <span>촬영 담당자</span><span>촬영한 분석</span><span>반려견</span><span>분석 실패</span><span>마지막 촬영</span>
        </div>
        {rows.map((r, i) => (
          <div key={r.name} className="hv-row tbl-r" data-href={qs({ view: 'analyses', by: r.name, page: '' })} style={css(`--tc:${cols};--tc-n:${colsN};display:grid;gap:12px;padding:14px 20px;border-top:${bt(i)};align-items:center;cursor:pointer;font-size:15px`)}>
            <b>{r.name}</b><span>{r.n}건</span><span>{r.dogs}마리</span><span style={css(`color:${r.fail ? '#C2412D' : '#5B6472'}`)}>{r.fail}건</span><span style={css('color:#5B6472')}>{r.last}</span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <Base acct={acct} me={me} nav="home" q={q} toast={toast} modals={<PetModal next_url="/home" open={modal === 'pet'} dogs={acct.dogs} />}>
      <main style={css('padding:28px 32px 64px;max-width:1480px;margin:0 auto;display:flex;flex-direction:column;gap:18px')}>

        <div style={css('display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap')}>
          <div style={css('display:flex;flex-direction:column;gap:4px')}>
            <span style={css('font-size:14px;font-weight:600;color:#7A808A')}>{today}</span>
            <h1 style={css('margin:0;font-size:28px;letter-spacing:-0.6px')}>{acct.name}</h1>
          </div>
          <div data-pet="new" className="hv-border" style={css('height:44px;padding:0 18px;border-radius:12px;border:1px solid #E2DCD3;background:#fff;display:flex;align-items:center;gap:6px;font-size:15px;font-weight:700;cursor:pointer')}>+ 반려견 등록</div>
        </div>

        <div style={css('display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px')}>
          {cards.map(([label, n, href, on, warn]) => (
            <a key={label} className="lk hv-border" href={link(href)} style={css(`padding:16px 18px;border-radius:16px;background:#fff;border:1.5px solid ${on ? '#D2601A' : '#ECE8E2'};display:flex;flex-direction:column;gap:4px`)}>
              <span style={css('font-size:14px;font-weight:600;color:#5B6472')}>{label}</span>
              <b style={css(`font-size:28px;letter-spacing:-0.6px;color:${warn && n ? '#C2412D' : '#1B2433'}`)}>{n}<span style={css('font-size:15px;font-weight:600;color:#7A808A;margin-left:3px')}>마리</span></b>
            </a>
          ))}
        </div>

        {/* 무엇을 볼지 · 검색 · 조건 */}
        <GetForm action="/home" style={css('display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0')}>
          <input type="hidden" name="view" value={view} />
          {by ? <input type="hidden" name="by" value={by} /> : null}
          <div style={css('display:flex;padding:4px;border-radius:12px;background:#F1ECE5;gap:2px')}>
            {HOME_VIEWS.map(([key, label]) => {
              const on = view === key && !by
              return <a key={key} className="lk" href={link(qs({ view: key, by: '', page: '' }))} style={css(`height:38px;padding:0 16px;border-radius:9px;display:flex;align-items:center;font-size:15px;font-weight:${on ? 700 : 500};background:${on ? '#fff' : 'transparent'};color:${on ? '#1B2433' : '#5B6472'};box-shadow:${on ? '0 1px 3px rgba(27,36,51,.12)' : 'none'}`)}>{label}</a>
            })}
          </div>
          {view === 'today' && !by ? <DayPicker day={day} today={isoToday()} marks={activity_days(acct)} go={(d) => navigate(qs({ d: d === isoToday() ? '' : d, page: '' }))} /> : null}
          {view === 'today' && day !== isoToday() ? <input type="hidden" name="d" value={day} /> : null}
          {q ? <><input type="hidden" name="q" value={q} /><span style={css('height:38px;padding:0 12px;border-radius:9px;background:#FCEEE3;color:#A8481A;display:flex;align-items:center;font-size:14px;font-weight:700')}>‘{q}’ 검색 결과</span></> : null}
          <label style={css('height:44px;display:flex;align-items:center;gap:6px;font-size:14.5px;cursor:pointer')}><input type="checkbox" name="changed" value="1" defaultChecked={changed === '1'} onChange={(e) => e.currentTarget.form?.requestSubmit()} /> 일주일 간 변동 발생</label>
          {changed === 'retake' ? <span style={css('height:38px;padding:0 12px;border-radius:9px;background:#FBE0D9;color:#C2412D;display:flex;align-items:center;font-size:14px;font-weight:700')}>재촬영 필요만</span> : null}
          <select name="stage" defaultValue={stage} onChange={(e) => e.currentTarget.form?.requestSubmit()} style={css(`height:44px;border-radius:12px;border:1px solid ${stage ? '#D2601A' : '#E2DCD3'};background:#fff;padding:0 12px;font-size:14.5px;font-family:inherit`)}>
            {[['', '단계 전체'], ['pre', '수술 전'], ['rehab', '재활 중'], ['done', '종결']].map(([v, label]) => <option key={v} value={v}>{label}</option>)}
          </select>
          {q || changed || stage ? <a className="lk" href={link(qs({ q: '', changed: '', stage: '', page: '' }))} style={css('font-size:14px;font-weight:600;color:#7A808A')}>조건 지우기</a> : null}
        </GetForm>

        {/* 고른 반려견 · 촬영 담당자 */}
        {by ? (
          <div style={css('display:flex;align-items:center;gap:10px;flex-wrap:wrap')}>
            <span style={css('font-size:15px;color:#5B6472')}><b style={css('color:#1B2433')}>{by}</b> 님이 촬영한 분석 · {hv.total}건</span>
            <a className="lk" href={link(qs({ view: 'staff', by: '', page: '' }))} style={css('height:32px;padding:0 12px;border-radius:9px;border:1px solid #E2DCD3;background:#fff;display:flex;align-items:center;font-size:13.5px;font-weight:600')}>✕ 담당자 목록으로</a>
          </div>
        ) : null}

        <div style={css('display:flex;gap:18px;align-items:flex-start')}>
          <div style={css('flex:1;min-width:0;border-radius:18px;background:#fff;border:1px solid #ECE8E2;overflow-x:auto')}>
            {table}
            {!rows.length ? <div style={css('padding:48px 20px;text-align:center;font-size:15px;color:#5B6472')}>{view === 'today' ? (day === isoToday() ? '오늘 진행한 분석 및 진료가 없습니다.' : `${dayLabel(day)}에 진행한 분석 및 진료가 없습니다.`) : '조건에 맞는 ' + (view === 'analyses' ? '분석이' : view === 'dogs' ? '반려견이' : '담당자가') + ' 없습니다.'}</div> : null}
          </div>

        </div>

        {hv.pages > 1 ? (
          <div style={css('display:flex;justify-content:center;gap:6px;flex-wrap:wrap')}>
            {Array.from({ length: hv.pages }, (_, i) => i + 1).map((p) => (
              <a key={p} className="lk" href={link(qs({ page: p }))} style={css(`min-width:38px;height:38px;padding:0 10px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:14.5px;font-weight:${p === hv.page ? 700 : 500};background:${p === hv.page ? '#1B2433' : '#fff'};color:${p === hv.page ? '#fff' : '#3A4250'};border:1px solid ${p === hv.page ? '#1B2433' : '#E2DCD3'}`)}>{p}</a>
            ))}
          </div>
        ) : null}
      </main>
    </Base>
  )
}
