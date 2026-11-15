// dog.html + main.py dog_chart(): 반려견 차트. EMR 처럼 진료 기록 = 왼쪽 방문 목록 + 가운데 그날 기록, 오른쪽 진단 이력.
// 경과 = 그래프·측정 이력(두 회차 비교 버튼)·바이탈 표, 진단 이력 = 기록 추가 + 목록(11-02). 11-09 QA: 경과 비교를 위 버튼에서 경과 탭 안으로
import { Fragment, useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { PostForm, staticUrl, usePage, useTitle } from '../app/page'
import { setToast } from '../app/session'
import { IMG_KIND, MEMO_CAT, SITE, SOAP, STAGE_NAMES, link } from '../config'
import { activeJobs, dogOf, isoToday } from '../store/db'
import { deleteDogImage, isRemote, syncDogChart, uploadDogImage } from '../store/backend'
import { fileHref } from '../api/client'
import { care_team, chart_summary, dog_detail, dx_history, image_list, kg_trend, memos as memos_of, patient_row, valid, visits, vital_rows } from '../views/views'
import { MemoCard, MemoForm, type MemoX } from './parts/DogPanel'
import { PetModal } from './parts/Modals'
import { VFlagBadge, VV } from './parts/Vital'

/** 서버 사진은 서명 주소(http·/api/…), 시연 사진은 static 경로 */
const imgSrc = (p: string): string => (/^(https?:)?\//.test(p) ? fileHref(p) : staticUrl(p))

/** 경과 탭: 반려견 사진 올리기(15.11). 서버 기관에서만 보인다 */
function ImageUpload({ acctId, dogId, today }: { acctId: string; dogId: string; today: string }) {
  const [kind, setKind] = useState('photo')
  const [day, setDay] = useState(today)
  const [caption, setCaption] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [key, setKey] = useState(0)
  const send = async () => {
    if (!file || busy) return
    setBusy(true); setMsg('')
    try {
      await uploadDogImage(acctId, dogId, file, kind, day || undefined, caption.trim() || undefined)
      setFile(null); setCaption(''); setKey((k) => k + 1); setMsg('사진을 올렸습니다')
    } catch (e) {
      setMsg(e instanceof Error && e.message ? e.message : '사진을 올리지 못했습니다')
    } finally {
      setBusy(false)
    }
  }
  const FIN = 'height:40px;border-radius:10px;border:1px solid #E2DCD3;background:#fff;padding:0 10px;font-size:14px;font-family:inherit;min-width:0'
  return (
    <div style={css('display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding-top:4px;border-top:1px solid #F0ECE6')}>
      <select aria-label="사진 종류" value={kind} onChange={(e) => setKind(e.target.value)} style={css(FIN)}>
        {Object.entries(IMG_KIND).map(([k, n]) => <option key={k} value={k}>{n}</option>)}
      </select>
      <input aria-label="찍은 날" type="date" value={day} max={today} onChange={(e) => setDay(e.target.value)} style={css(FIN)} />
      <input aria-label="설명" placeholder="설명(선택, 100자)" maxLength={100} value={caption} onChange={(e) => setCaption(e.target.value)} style={css(FIN + ';flex:1 1 160px')} />
      <input key={key} aria-label="사진 파일" type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} style={css('font-size:14px;max-width:100%')} />
      <button type="button" className="btn tap" disabled={!file || busy} onClick={send} style={css('height:44px;padding:0 16px;border-radius:10px;border:0;background:#D2601A;color:#fff;font-weight:700;font-size:14px;cursor:pointer;opacity:' + (!file || busy ? '0.5' : '1'))}>{busy ? '올리는 중…' : '사진 올리기'}</button>
      {msg ? <span role="status" style={css('font-size:13px;color:#5B6472;flex-basis:100%')}>{msg}</span> : null}
      <span style={css('font-size:12px;color:#5B6472;flex-basis:100%')}>사람 얼굴은 서버가 가려서 저장합니다(방사선 사진 제외).</span>
    </div>
  )
}

const CHART_TABS: [string, string][] = [['visits', '진료 기록'], ['progress', '경과'], ['dx', '진단 이력']]
const _OLD_TABS: Record<string, string> = { summary: 'progress', gait: 'progress', vitals: 'visits', notes: 'visits', history: 'dx' } // 예전 주소

const tone: Record<string, [string, string]> = { surg: ['#FCEEE3', '#A8481A'], diag: ['#EEF1F6', '#4A5A78'], warn: ['#FAF1DF', '#9A6A12'] }
type VK = 'kg' | 'temp' | 'hr' | 'bp'
const VKEYS: [string, VK][] = [['체중', 'kg'], ['체온', 'temp'], ['심박', 'hr'], ['혈압', 'bp']]
const VIN = 'height:36px;border-radius:9px;border:1px solid #E2DCD3;background:#fff;padding:0 10px;font-size:14px;font-family:inherit;outline:none;min-width:0;width:100%;font-variant-numeric:tabular-nums'
const FI = 'height:44px;border-radius:10px;border:1px solid #E2DCD3;background:#fff;padding:0 12px;font-size:15px;font-family:inherit;outline:none;min-width:0'

export default function DogPage() {
  const { dog_id = '' } = useParams()
  const { acct, me, toast, query } = usePage({ login: true })
  const navigate = useNavigate()
  const loc = useLocation()
  const cur = acct ? dogOf(acct, dog_id) : undefined
  const missing = !!acct && !cur
  useTitle(cur ? cur.name : 'Paw oh Paw')
  // 백엔드 기관이면 차트를 열 때 바이탈·진단 이력·메모·상세(연락처 전체)를 서버에서 읽는다(271)
  const acctId = acct?.id ?? ''
  useEffect(() => {
    if (acctId && dog_id && isRemote(acctId)) void syncDogChart(acctId, dog_id).catch(() => undefined)
  }, [acctId, dog_id])
  useEffect(() => {
    if (missing) {
      setToast('반려견을 찾을 수 없습니다')
      navigate('/home', { replace: true })
    }
  }, [missing, navigate])
  // 주소의 #id(진료 기록 고치기)로 스크롤: 시제품은 브라우저가 한다
  useEffect(() => {
    if (!loc.hash) return
    const el = document.getElementById(decodeURIComponent(loc.hash.slice(1)))
    if (el) el.scrollIntoView()
  }, [loc.hash])
  if (!acct || !cur) return null

  let tab = query.get('tab') ?? 'visits'
  const edit = query.get('edit') || ''
  let v = query.get('v') || ''
  tab = _OLD_TABS[tab] ?? tab
  tab = CHART_TABS.some(([k]) => k === tab) ? tab : 'visits'
  const vis = visits(acct, cur)
  const today_iso = isoToday()
  // 고른 날짜가 방문 목록에 없으면 가장 최근 방문. 단, 날짜를 골라 지난 방문을 새로 쓰려는 경우(오늘 전 날짜)는 그대로 둔다(271 방문일)
  if (v !== today_iso && !vis.some((x) => x.day === v) && !(/^\d{4}-\d{2}-\d{2}$/.test(v) && v < today_iso)) v = vis.length ? vis[0].day : today_iso
  const live = new Set(activeJobs(acct).map((j) => j.dog))
  const dd = dog_detail(acct, cur)
  const row = patient_row(acct, cur, live)
  const sm = chart_summary(acct, cur)
  const memos: MemoX[] = memos_of(cur)
  const team = care_team(acct, cur)
  const sel = vis.find((x) => x.day === v) || null
  const dx = dx_history(acct, cur)
  const imgs = image_list(cur)
  const kgt = kg_trend(cur)
  const vt = vital_rows(cur)

  const edit_memo = edit ? memos.find((x) => x.id === edit) || null : null
  const here = `/dogs/${cur.id}` + (tab !== 'visits' ? `?tab=${tab}` : `?v=${v}`)
  const tv = cur.vitals.find((x) => x.day === v) // 고른 방문 날의 바이탈(있으면 채워 둔다)
  const remote = isRemote(acct.id)
  const vedit = query.get('vedit') || ''
  const hedit = query.get('hedit') || ''
  // 진단 이력 한 줄마다 고치기·지우기에 쓸 키: 서버 id, 시연 데이터는 순번
  const hrows = cur.history.map((h, i) => ({ h, key: h.id || `i${i}` })).reverse()
  // QA 4: 진료 기록(SOAP)의 A(평가)를 진단 이력 탭에서도 본다. 최신순
  const assess = cur.notes.filter((n) => n.cat === 'A').sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0))

  let body
  if (tab === 'visits') {
    body = (
      <div className="visit-grid">
        {/* 왼쪽: 방문 목록. 같은 날짜의 측정·바이탈·진료 기록·진단/수술·영상을 한 방문으로 묶는다 */}
        <aside className="v-list">
          <a className="lk v-new" href={link(`/dogs/${cur.id}?v=${today_iso}`)}>+ 오늘 진료 기록</a>
          {/* 지난 방문 기록: 날짜를 골라 그날로 쓴다(방문일 271) */}
          <form method="get" action={link(`/dogs/${cur.id}`)} style={css('display:flex;gap:6px;align-items:center;margin:0 0 4px')}>
            <input className="inp" type="date" name="v" max={today_iso} required aria-label="기록할 날짜" style={css('flex:1;min-width:0;height:36px;border-radius:9px;border:1px solid #E2DCD3;padding:0 8px;font-size:13px;font-family:inherit')} />
            <button className="bt" type="submit" style={css('height:44px;padding:0 10px;border-radius:9px;background:#fff;border:1px solid #E2DCD3;font-size:13px;font-weight:700;white-space:nowrap')}>날짜 골라 기록</button>
          </form>
          {vis.map((x) => (
            <a key={x.day} className={`lk v-card${x.day === v ? ' on' : ''}`} href={link(`/dogs/${cur.id}?v=${x.day}`)}>
              <span style={css('display:flex;align-items:center;justify-content:space-between;gap:8px')}><b style={css('font-size:15px;font-variant-numeric:tabular-nums')}>{x.date}{x.today ? <>{' '}<span style={css('color:#D2601A')}>오늘</span></> : null}</b>{x.st ? <span style={css(`font-size:12px;font-weight:700;color:${x.st.c}`)}>{x.st.st}</span> : null}</span>
              {x.title ? <span style={css('font-size:14px;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden')}>{x.title}</span> : null}
              <span style={css('display:flex;gap:4px;flex-wrap:wrap;align-items:center')}>{x.tags.map((t, i) => <span key={i} style={css(`padding:1px 7px;border-radius:6px;background:${t.bg};color:${t.c};font-size:12px;font-weight:700`)}>{t.t}</span>)}{x.n_soap ? <span style={css('font-size:12px;color:#5B6472')}>기록 {x.n_soap}</span> : null}<span style={css('margin-left:auto;font-size:12px;color:#5B6472')}>{x.who.split(' ')[0]}</span></span>
            </a>
          ))}
          {!vis.length ? <span style={css('font-size:14px;color:#5B6472;padding:8px 4px')}>아직 방문 기록이 없습니다.</span> : null}
        </aside>

        {/* 가운데: 고른 방문의 기록 */}
        <section className="v-body">
          <div style={css('display:flex;align-items:baseline;gap:10px;flex-wrap:wrap')}>
            <b style={css('font-size:18px;font-variant-numeric:tabular-nums')}>{v.replaceAll('-', '.')}</b>
            {v === today_iso ? <span style={css('font-size:13px;font-weight:700;color:#D2601A')}>오늘 방문</span> : null}
            {sel ? sel.tags.map((t, i) => <span key={i} style={css(`padding:2px 8px;border-radius:6px;background:${t.bg};color:${t.c};font-size:12px;font-weight:700`)}>{t.t}</span>) : null}
          </div>

          {sel && sel.hist.length ? (
            <div className="v-sec">{sel.hist.map((h, i) => <div key={i} style={css('font-size:15px')}><b style={css(`color:${h.kind == '수술' ? '#A8481A' : '#3A4250'}`)}>{h.kind}</b> {h.title}{h.site ? `, ${SITE[h.site]}` : ''}{h.by ? <>{' '}<span style={css('color:#5B6472')}>({h.by})</span></> : null}</div>)}</div>
          ) : null}

          {/* 진료 기록(SOAP): 고른 방문 날짜(오늘까지)로 쓴다(방문일 271). 오늘은 바이탈 필수, 지난 방문은 바이탈을 비워도 된다 */}
          <div className="v-sec">
            <b className="v-h">진료 기록</b>
            {v <= today_iso ? (
              <PostForm action={`/dogs/${cur.id}/notes`} style={css('display:flex;flex-direction:column;gap:8px;margin:0')}>
                <input type="hidden" name="next_url" value={`/dogs/${cur.id}?v=${v}`} />
                <input type="hidden" className="author-inp" name="author" defaultValue="" />
                <input type="hidden" name="visit" value="1" />
                <input type="hidden" name="visit_day" value={v} />
                {/* 바이탈은 방문마다 반드시 잰다. 오늘 이미 잰 값이 있으면 채워 두고 고치면 바뀐다 */}
                <div className="vit-in">
                  {([['kg', '체중 kg', cur.kg, tv ? tv.kg : ''], ['temp', '체온 ℃', '38.6', tv ? tv.temp : ''], ['hr', '심박 bpm', '92', tv ? tv.hr : ''], ['sbp', '수축기 mmHg', '140', tv ? tv.sbp : ''], ['dbp', '이완기 mmHg', '85', tv ? tv.dbp : '']] as [string, string, string, string][]).map(([nm, label, ph, val]) => (
                    <label key={nm}><span>{label}{v === today_iso ? <>{' '}<b style={css('color:#C2412D')}>*</b></> : null}</span><input className="inp" name={nm} inputMode="decimal" required={v === today_iso} placeholder={ph} defaultValue={val} /></label>
                  ))}
                </div>
                {Object.entries(SOAP).map(([k, [name, hint]]) => (
                  <label key={k} style={css('display:grid;grid-template-columns:88px 1fr;gap:10px;align-items:start')}>
                    <span style={css('display:flex;align-items:center;gap:7px;padding-top:9px')}><b className="soap-k">{k}</b><b style={css('font-size:14px')}>{name}</b></span>
                    <textarea name={k.toLowerCase()} rows={1} placeholder={hint} className="inp" style={css('min-height:42px;border-radius:10px;border:1px solid #E2DCD3;padding:10px 12px;font-size:15px;line-height:1.5;font-family:inherit;outline:none;resize:vertical;width:100%')}></textarea>
                  </label>
                ))}
                <div style={css('display:flex;justify-content:flex-end')}><button className="bt" type="submit" style={css('height:44px;padding:0 18px;border-radius:10px;background:#1B2433;color:#fff;font-size:14px;font-weight:700')}>기록 남기기</button></div>
              </PostForm>
            ) : null}
            {(sel ? sel.soap : []).map((g, gi) => (
              <div key={gi} style={css('display:flex;flex-direction:column;gap:7px;padding-top:10px;border-top:1px solid #F2EFEA')}>
                <div style={css('display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:13px;color:#5B6472')}>
                  <b style={css('color:#3A4250')}>{g.at.slice(9)}</b>{g.author ? <span>{g.author}</span> : null}
                  {g.rid ? <a className="lk" href={link(`/results/${g.rid}`)} style={css('display:inline-flex;align-items:center;min-height:44px')}><span style={css('padding:1px 8px;border-radius:6px;background:#EEF1F6;color:#4A5A78;font-weight:700')}>{g.run} 결과</span></a> : null}
                </div>
                {g.parts.map((n) => (
                  <div key={n.id} id={n.id} style={css('display:grid;grid-template-columns:88px 1fr;gap:10px;align-items:start')}>
                    <span style={css('display:flex;align-items:center;gap:7px')}><b className="soap-k" style={css('background:#F1ECE5;color:#3A4250')}>{n.cat}</b><span style={css('font-size:13px;color:#5B6472')}>{n.soap}</span></span>
                    <div style={css('display:flex;flex-direction:column;gap:4px;min-width:0')}>
                      {edit === n.id ? (
                        <PostForm action={`/dogs/${cur.id}/notes`} style={css('display:flex;flex-direction:column;gap:8px;margin:0')}>
                          <input type="hidden" name="note_id" value={n.id} /><input type="hidden" name="next_url" value={`/dogs/${cur.id}?v=${v}`} />
                          <textarea className="inp" name="text" style={css('min-height:64px;border-radius:10px;border:1px solid #D2601A;padding:10px 12px;font-size:15px;line-height:1.55;font-family:inherit;outline:none')} defaultValue={n.text}></textarea>
                          <input type="hidden" className="author-inp" name="author" defaultValue="" />
                          <div style={css('display:flex;gap:10px;align-items:center')}><button className="bt" type="submit" style={css('height:44px;padding:0 14px;border-radius:9px;background:#1B2433;color:#fff;font-size:14px;font-weight:700')}>고친 내용 저장</button><a className="lk" href={link(`/dogs/${cur.id}?v=${v}`)} style={css('font-size:14px;color:#5B6472')}>취소</a></div>
                        </PostForm>
                      ) : (
                        <div style={css('display:flex;gap:10px;align-items:flex-start')}><span style={css('flex:1;font-size:15px;line-height:1.6;white-space:pre-line;padding-top:2px')}>{n.text}</span><a className="lk tap" href={link(`/dogs/${cur.id}?v=${v}&edit=${n.id}#${n.id}`)} style={css('font-size:13px;font-weight:600;color:#B4501A;white-space:nowrap;position:relative;top:4px')}>고치기</a><PostForm action={`/dogs/${cur.id}/notes`} style={css('display:inline;margin:0')} onBefore={() => window.confirm('이 기록을 지울까요? 고친 이력도 함께 지워지고 되돌릴 수 없습니다.')}><input type="hidden" name="note_id" value={n.id} /><input type="hidden" name="delete" value="1" /><input type="hidden" name="next_url" value={`/dogs/${cur.id}?v=${v}`} /><button className="bt tap" type="submit" style={css('background:none;font-size:13px;font-weight:600;color:#B4501A;padding:0;white-space:nowrap;position:relative;top:1px')}>지우기</button></PostForm></div>
                      )}
                      {n.revs && n.revs.length ? <details style={css('font-size:13px;color:#5B6472')}><summary style={css('cursor:pointer')}>고친 이력 {n.revs.length}건</summary>{[...n.revs].reverse().map((r, ri) => <div key={ri} style={css('padding:5px 0 0 10px;border-left:2px solid #ECE8E2;margin-top:5px')}><span>{r.at}, {r.author}</span><div style={css('text-decoration:line-through;white-space:pre-line')}>{r.text}</div></div>)}</details> : null}
                    </div>
                  </div>
                ))}
              </div>
            ))}
            {v !== today_iso && !(sel && sel.soap.length) ? <span style={css('font-size:14px;color:#5B6472')}>이 방문에 남긴 진료 기록이 없습니다.</span> : null}
          </div>

          {sel && sel.res.length ? (
            <div className="v-sec">
              <b className="v-h">보행 측정</b>
              {sel.res.map((r) => (
                <div key={r.id} style={css('display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:12px 14px;border-radius:12px;background:#FAF8F5')}>
                  <b style={css('font-size:15px')}>{r.no}</b><span style={css('font-size:13px;color:#5B6472')}>{r.time}, {r.by}</span>
                  <span style={css(`height:24px;padding:0 9px;border-radius:7px;font-size:12px;font-weight:700;background:${r.bg};color:${r.c};display:inline-flex;align-items:center`)}>{r.st}</span>
                  {!r.fail ? <span style={css('font-size:14px')}>대칭 점수 <b style={css(`padding:2px 8px;border-radius:7px;background:${r.sym_bg};color:${r.sym_c}`)}>{r.sym}점</b>{r.sym_d ? <>{' '}<b style={css(`font-size:13px;color:${r.sym_dc}`)}>{r.sym_d}</b></> : null}</span> : null}
                  <span style={css('margin-left:auto;display:flex;gap:6px')}><a className="lk" href={link(`/results/${r.id}`)} style={css('height:44px;padding:0 12px;border-radius:9px;background:#D2601A;color:#fff;display:flex;align-items:center;font-size:14px;font-weight:700')}>결과 보기</a>{!r.fail ? <a className="lk" href={link(`/results/${r.id}/3d`)} style={css('height:44px;padding:0 12px;border-radius:9px;border:1px solid #E2DCD3;background:#fff;display:flex;align-items:center;font-size:14px;font-weight:600')}>3D</a> : null}</span>
                </div>
              ))}
            </div>
          ) : null}

          {sel && sel.vital && v !== today_iso ? (
            <div className="v-sec">
              <b className="v-h">바이탈</b>
              <div style={css('display:flex;gap:22px;flex-wrap:wrap;font-variant-numeric:tabular-nums')}>{VKEYS.map(([k, key]) => <span key={key} style={css('display:flex;flex-direction:column')}><span className="cs-lb">{k}</span><VV value={sel.vital![key]} f={sel.vital!.f[key]} /></span>)}<span style={css('align-self:flex-end;font-size:13px;color:#5B6472')}>{sel.vital_by}</span></div>
            </div>
          ) : null}

          {sel && sel.imgs.length ? (
            <div className="v-sec">
              <b className="v-h">영상/사진</b>
              <div style={css('display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px')}>
                {sel.imgs.map((im) => (
                  <a key={im.id} className="lk img-card" href={imgSrc(im.path)} data-lightbox="" data-caption={`${im.caption}, ${im.kind}`}>
                    <span className="img-thumb"><img src={imgSrc(im.path)} alt={im.caption} loading="lazy" /></span>
                    <b style={css('font-size:14px')}>{im.caption}</b><span style={css('font-size:12px;color:#5B6472')}>{im.kind}{im.by ? `, ${im.by}` : ''}</span>
                  </a>
                ))}
              </div>
            </div>
          ) : null}
        </section>

        {/* 오른쪽: 진단 이력. 진단 하나에 뒤따른 수술·재활을 묶는다 */}
        <aside className="v-dx">
          <span style={css('display:flex;justify-content:space-between;align-items:baseline')}><b style={css('font-size:15px')}>진단 이력</b><a className="lk tap" href={link(`/dogs/${cur.id}?tab=dx`)} style={css('font-size:13px;font-weight:600;color:#B4501A')}>추가 ›</a></span>
          {dx.map((e, i) => (
            <div key={i} className="dx-card">
              <span style={css('display:flex;align-items:center;justify-content:space-between;gap:6px')}><b style={css('font-size:13px;font-variant-numeric:tabular-nums')}>{e.range}</b><span style={css(`padding:1px 8px;border-radius:999px;font-size:12px;font-weight:700;${e.done ? 'background:#F0EEEA;color:#5B6472' : 'background:#E7EEFB;color:#3B5BA9'}`)}>{e.done ? '종결' : '진행중'}</span></span>
              <b style={css('font-size:14px')}>{e.title}{e.site ? <>{' '}<span style={css('color:#5B6472;font-weight:600')}>({e.site})</span></> : null}</b>
              {e.events.map((x, j) => <span key={j} style={css('font-size:13px;color:#5B6472')}><span style={css('font-variant-numeric:tabular-nums;color:#5B6472')}>{x.day}</span> {x.kind}, {x.title.split(' (')[0]}</span>)}
              <span style={css('display:flex;justify-content:space-between;font-size:12px;color:#5B6472')}><span>보행 측정 {e.n}회</span><span>{e.by}</span></span>
            </div>
          ))}
          {!dx.length ? <span style={css('font-size:14px;color:#5B6472')}>진단 기록이 없습니다.</span> : null}
        </aside>
      </div>
    )
  } else if (tab === 'progress') {
    const H_B = sm.has ? sm.H - sm.B : 0
    body = (
      <>
        {/* 환자 단위 영상·사진: 방문마다 흩어진 것을 촬영일 순으로 모아 수술 전·후를 나란히 본다 */}
        <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:20px 24px;display:flex;flex-direction:column;gap:12px')}>
          <b style={css('font-size:15px')}>영상/사진 <span style={css('color:#5B6472;font-weight:600;font-size:14px')}>{imgs.length}</span></b>
          {imgs.length ? (
            <div style={css('display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px')}>
              {imgs.map((im) => (
                <div key={im.id} className="img-card">
                  <a className="lk img-thumb" href={imgSrc(im.path)} data-lightbox="" data-caption={`${im.caption}, ${im.kind}, ${im.date}`}><img src={imgSrc(im.path)} alt={im.caption} loading="lazy" /></a>
                  <span style={css('display:flex;align-items:center;gap:6px')}><span style={css(`padding:1px 7px;border-radius:6px;font-size:12px;font-weight:700;${im.pre ? 'background:#EEF1F6;color:#4A5A78' : im.post ? 'background:#FCEEE3;color:#A8481A' : 'background:#F1ECE5;color:#5B6472'}`)}>{im.kind}</span><b style={css('font-size:14px')}>{im.caption}</b></span>
                  <span style={css('display:flex;align-items:center;justify-content:space-between;gap:8px')}>
                    <a className="lk tap" href={link(`/dogs/${cur.id}?v=${im.day}`)} style={css('font-size:12px;color:#5B6472')}>{im.date} 방문{im.by ? `, ${im.by}` : ''} ›</a>
                    {remote ? <button type="button" className="tap" onClick={() => { if (window.confirm('이 사진을 지울까요? 되돌릴 수 없습니다.')) deleteDogImage(acctId, cur.id, im.id).catch((e) => window.alert(e instanceof Error ? e.message : '지우지 못했습니다')) }} style={css('min-height:44px;padding:0 12px;border-radius:9px;border:1px solid #E2DCD3;background:#fff;color:#B4501A;font-size:13px;font-weight:600;cursor:pointer')}>삭제</button> : null}
                  </span>
                </div>
              ))}
            </div>
          ) : <span style={css('font-size:14px;color:#5B6472')}>올린 영상·사진이 없습니다.</span>}
          {remote ? <ImageUpload acctId={acctId} dogId={cur.id} today={today_iso} /> : null}
        </div>
        {sm.has ? (
          <div style={css('display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px')}>
            {sm.facts.map((f, i) => (
              <div key={i} style={css('padding:16px 18px;border-radius:16px;background:#fff;border:1px solid #ECE8E2;display:flex;flex-direction:column;gap:4px')}>
                <span style={css('font-size:13px;font-weight:600;color:#5B6472')}>{f.k}</span><b style={css('font-size:22px;letter-spacing:-0.4px')}>{f.v}</b><span style={css('font-size:13px;color:#5B6472')}>{f.sub}</span>
              </div>
            ))}
          </div>
        ) : null}
        <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:20px 24px;display:flex;flex-direction:column;gap:14px')}>
          <div style={css('display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap')}><b style={css('font-size:15px')}>경과 한눈에 보기</b>
            <span style={css('display:flex;gap:14px;flex-wrap:wrap;font-size:13px;color:#5B6472')}><span><span style={css('display:inline-block;width:14px;height:3px;background:#D2601A;vertical-align:middle')}></span> 대칭 점수</span><span><span style={css('display:inline-block;width:2px;height:12px;background:#A8481A;vertical-align:middle')}></span> 수술</span><span><span style={css('display:inline-block;width:2px;height:12px;background:#7A8FB5;vertical-align:middle')}></span> 재활 단계</span><span><span style={css('color:#B9BEC6')}>●</span> 메모</span><span style={css('color:#9AA3AF')}>▲ <span style={css('color:#5B6472')}>바이탈</span></span></span></div>
          {sm.has ? (
            <svg viewBox={`0 0 ${sm.W} ${sm.H}`} style={css('width:100%;height:auto;max-height:300px')}>
              {sm.yt.map((t, i) => <Fragment key={`y${i}`}><line x1={sm.L} x2={sm.W - sm.R} y1={t.y} y2={t.y} stroke="#F0ECE6"></line><text x={sm.L - 8} y={t.y + 4} textAnchor="end" fontSize="12" fill="#5B6472">{t.v}%</text></Fragment>)}
              {sm.marks.map((mk, i) => <Fragment key={`m${i}`}><line x1={mk.x} x2={mk.x} y1={sm.T - 6} y2={H_B} stroke={mk.kind == '수술' ? '#A8481A' : '#7A8FB5'} strokeWidth="1.5" strokeDasharray={mk.kind == '수술' ? '' : '4 3'}><title>{`${mk.day} ${mk.kind}, ${mk.label}`}</title></line><text x={mk.x + 4} y={sm.T + 2} fontSize="12" fontWeight="700" fill={mk.kind == '수술' ? '#A8481A' : '#5A6F95'}>{mk.label.slice(0, 12)}</text></Fragment>)}
              {sm.pts.length > 1 ? <polyline points={sm.line} fill="none" stroke="#D2601A" strokeWidth="2.5" strokeLinejoin="round"></polyline> : null}
              {sm.pts.map((p, i) => <a key={`p${i}`} href={link(`/results/${p.id}`)}><circle cx={p.x} cy={p.y} r="5" fill="#fff" stroke="#D2601A" strokeWidth="2.5"><title>{`${p.day} 대칭 점수 ${p.sym}점, ${p.by}`}</title></circle></a>)}
              {sm.notes.map((n, i) => <circle key={`n${i}`} cx={n.x} cy={H_B + 16} r="4.5" fill="#B9BEC6"><title>{`${n.day} ${n.t}`}</title></circle>)}
              {sm.vit.map((x, i) => <path key={`v${i}`} d={`M${x.x - 4},${H_B + 34} L${x.x + 4},${H_B + 34} L${x.x},${H_B + 27} Z`} fill="#9AA3AF"></path>)}
              {sm.ticks.map((t, i) => <text key={`t${i}`} x={t.x} y={sm.H - 4} textAnchor="middle" fontSize="12" fill="#5B6472">{t.t}</text>)}
            </svg>
          ) : <span style={css('font-size:14px;color:#5B6472')}>아직 기록이 없습니다.</span>}
        </div>
        <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:20px 24px;display:flex;flex-direction:column;gap:16px')}>
          <div style={css('display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px 20px')}>
            {dd.cells.map((a, i) => <div key={i} style={css('display:flex;flex-direction:column;gap:4px;min-width:0')}><span style={css('font-size:13px;color:#5B6472;font-weight:600')}>{a.k}</span><b style={css('font-size:15px;font-variant-numeric:tabular-nums')}>{a.v}</b>{a.sub ? <span style={css('font-size:12px;color:#5B6472')}>{a.sub}</span> : null}</div>)}
          </div>
        </div>
        <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;overflow-x:auto')}>
          <div style={css('min-width:720px')}>
            <div style={css('display:flex;align-items:center;justify-content:space-between;padding:18px 24px 10px')}><b style={css('font-size:18px')}>측정 이력 <span style={css('color:#5B6472;font-weight:600;font-size:15px')}>{dd.count}</span></b>{valid(acct!, cur.id).length >= 2 ? <a className="lk hv-border" href={link(`/compare/${cur.id}`)} style={css('height:44px;padding:0 14px;border-radius:10px;border:1px solid #E2DCD3;background:#fff;display:flex;align-items:center;gap:4px;font-size:14px;font-weight:700;color:#B4501A')}>두 회차 비교 ›</a> : <span title="유효한 회차가 2개 이상 있어야 비교할 수 있습니다" style={css('font-size:13px;color:#5B6472')}>두 회차 비교는 유효 회차 2개부터</span>}</div>
            <div style={css('display:grid;grid-template-columns:1.1fr 1fr .9fr 1fr .8fr .8fr 1fr 1.2fr;gap:12px;padding:10px 24px;border-top:1px solid #ECE8E2;border-bottom:1px solid #ECE8E2;font-size:13px;font-weight:700;color:#5B6472')}><span>회차</span><span>측정일</span><span>체중</span><span>유효 통과</span><span>측정자/모델</span><span>보고서</span><span>상태</span><span></span></div>
            {dd.hist.map((h) => (
              <div key={h.id} className="hv-row" data-href={`/results/${h.id}`} style={css(`display:grid;grid-template-columns:1.1fr 1fr .9fr 1fr .8fr .8fr 1fr 1.2fr;gap:12px;align-items:center;padding:14px 24px;border-top:${h.bt};cursor:pointer;font-size:15px;font-variant-numeric:tabular-nums`)}>
                <span style={css('display:flex;align-items:center;gap:6px')}><b>{h.no}</b>{h.base ? <span style={css('height:20px;padding:0 7px;border-radius:5px;background:#1B2433;color:#fff;font-size:12px;font-weight:700;display:flex;align-items:center')}>기준</span> : null}</span>
                <span style={css('color:#5B6472')}>{h.date}</span><span>{h.w}</span><span>{h.pass}</span><span>{h.by.split(' ')[0]}, {h.model}</span><span>{h.rep}</span>
                <span><span style={css(`height:26px;padding:0 10px;border-radius:8px;font-size:13px;font-weight:700;background:${h.bg};color:${h.c};display:inline-flex;align-items:center`)}>{h.st}</span></span>
                <span style={css('text-align:right')}>{h.canBase ? <PostForm action={`/dogs/${cur.id}/base`} style={css('display:inline;margin:0')}><input type="hidden" name="rid" value={h.id} /><button className="bt tap" type="submit" style={css('background:none;font-size:13px;font-weight:700;color:#B4501A;padding:6px 0')}>기준 회차로 지정</button></PostForm> : null}</span>
              </div>
            ))}
            {!dd.hist.length ? <div style={css('padding:28px 24px;font-size:15px;color:#5B6472')}>아직 측정 기록이 없습니다.</div> : null}
          </div>
        </div>
        <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:20px 24px;display:flex;flex-direction:column;gap:14px')}>
          <span style={css('display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap')}><b style={css('font-size:15px')}>바이탈 기록</b><a className="lk tap" href={link(`/dogs/${cur.id}?tab=progress&vedit=new`)} style={css('font-size:13px;font-weight:700;color:#B4501A')}>+ 날짜 골라 기록</a></span>
          {vedit === 'new' ? <VitalForm dog_id={cur.id} day={today_iso} today={today_iso} author={me?.name ?? ''} /> : null}
          {vt.kg_spark ? <div style={css('display:flex;align-items:center;gap:12px')}><span style={css('font-size:13px;color:#5B6472')}>체중 추이</span><svg width="200" height="40" viewBox="0 0 200 40"><polyline points={vt.kg_spark} fill="none" stroke="#D2601A" strokeWidth="2"></polyline></svg><b style={css('font-size:14px')}>{vt.kg_range}</b></div> : null}
          {/* 좁은 창(800px)에서 칸이 잘리지 않게 표만 가로로 민다(QA 10) */}
          <div style={css('overflow-x:auto')}>
            <div style={css('min-width:640px;display:flex;flex-direction:column;gap:14px')}>
              <div style={css('display:grid;grid-template-columns:110px repeat(4,1fr) 160px 96px;gap:12px;font-size:13px;font-weight:700;color:#5B6472;padding-bottom:8px;border-bottom:1px solid #ECE8E2')}><span>날짜</span><span>체중</span><span>체온</span><span>심박</span><span>혈압</span><span>기록</span><span></span></div>
              {vt.rows.map((x, i) => {
                const raw = cur.vitals[i]
                return vedit === raw.day ? <VitalForm key={i} dog_id={cur.id} day={raw.day} today={today_iso} author={me?.name ?? ''} v={raw} /> : (
                  <div key={i} style={css('display:grid;grid-template-columns:110px repeat(4,1fr) 160px 96px;gap:12px;font-size:15px;font-variant-numeric:tabular-nums')}><span style={css('color:#5B6472')}>{x.day}</span>{(['kg', 'temp', 'hr', 'bp'] as VK[]).map((key) => <span key={key}><VV value={x[key]} f={x.f[key]} size={15} /></span>)}<span style={css('font-size:13px;color:#5B6472')}>{x.author}</span><span style={css('display:flex;gap:10px;justify-content:flex-end')}><a className="lk tap" href={link(`/dogs/${cur.id}?tab=progress&vedit=${raw.day}`)} style={css('font-size:13px;font-weight:600;color:#B4501A')}>고치기</a><PostForm action={`/dogs/${cur.id}/vitals`} style={css('display:inline;margin:0')} onBefore={() => window.confirm(`${raw.day} 바이탈을 지울까요? 되돌릴 수 없습니다.`)}><input type="hidden" name="day" value={raw.day} /><input type="hidden" name="delete" value="1" /><input type="hidden" name="next_url" value={`/dogs/${cur.id}?tab=progress`} /><button className="bt tap" type="submit" style={css('background:none;font-size:13px;font-weight:600;color:#B4501A;padding:0')}>지우기</button></PostForm></span></div>
                )
              })}
            </div>
          </div>
          {!vt.rows.length ? <span style={css('font-size:14px;color:#5B6472')}>기록이 없습니다.</span> : null}
        </div>
      </>
    )
  } else {
    body = (
      <>
        <PostForm action={`/dogs/${cur.id}/history`} style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:20px 24px;display:flex;flex-direction:column;gap:14px;margin:0')}>
          <b style={css('font-size:15px')}>기록 추가</b>
          <div style={css('display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;align-items:end')}>
            <label style={css('display:flex;flex-direction:column;gap:4px')}><span style={css('font-size:13px;color:#5B6472')}>날짜</span><input className="inp" type="date" name="day" defaultValue={today_iso} style={css(FI)} /></label>
            <label style={css('display:flex;flex-direction:column;gap:4px')}><span style={css('font-size:13px;color:#5B6472')}>종류</span><select name="kind" style={css(FI)}>{['진단', '수술', '재활'].map((k) => <option key={k}>{k}</option>)}</select></label>
            <label style={css('display:flex;flex-direction:column;gap:4px;min-width:0;grid-column:span 2')}><span style={css('font-size:13px;color:#5B6472')}>내용</span><input className="inp" name="title" placeholder="예) TPLO (경골 고원 수평화 절골술)" style={css(FI)} /></label>
            <label style={css('display:flex;flex-direction:column;gap:4px')}><span style={css('font-size:13px;color:#5B6472')}>부위</span><select name="site" style={css(FI)}><option value="">없음</option>{Object.entries(SITE).map(([k, x]) => <option key={k} value={k}>{x}</option>)}</select></label>
            <label style={css('display:flex;flex-direction:column;gap:4px;min-width:0')}><span style={css('font-size:13px;color:#5B6472')}>담당 수의사 <span style={css('color:#5B6472')}>선택</span></span><input className="inp" name="by" style={css(FI)} /></label>
            <label style={css('display:flex;flex-direction:column;gap:4px')}><span style={css('font-size:13px;color:#5B6472')}>단계 바꾸기</span><select name="stage" style={css(FI)}><option value="">그대로 ({row.stage})</option>{Object.entries(STAGE_NAMES).map(([k, x]) => <option key={k} value={k}>{x}</option>)}</select></label>
            {remote ? null : <label style={css('display:flex;flex-direction:column;gap:4px;min-width:0')}><span style={css('font-size:13px;color:#5B6472')}>작성자</span><input className="inp author-inp" name="author" placeholder="예) 최지우 수의사" style={css(FI)} /></label>}
          </div>
          <button className="bt" type="submit" style={css('align-self:flex-start;height:44px;padding:0 18px;border-radius:10px;background:#1B2433;color:#fff;font-size:15px;font-weight:700')}>기록하기</button>
        </PostForm>
        <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:20px 24px;display:flex;flex-direction:column;gap:12px')}>
          {dx.map((e, i) => (
            <div key={i} style={css(`display:flex;flex-direction:column;gap:5px;padding-top:${i ? '12px' : '0'};border-top:${i ? '1px solid #F2EFEA' : 'none'}`)}>
              <span style={css('display:flex;align-items:center;gap:10px;flex-wrap:wrap')}><b style={css('font-size:15px')}>{e.title}{e.site ? `, ${e.site}` : ''}</b><span style={css(`padding:1px 8px;border-radius:999px;font-size:12px;font-weight:700;${e.done ? 'background:#F0EEEA;color:#5B6472' : 'background:#E7EEFB;color:#3B5BA9'}`)}>{e.done ? '종결' : '진행중'}</span><span style={css('margin-left:auto;font-size:13px;color:#5B6472;font-variant-numeric:tabular-nums')}>{e.range}, 보행 측정 {e.n}회, {e.by}</span></span>
              {e.events.map((x, j) => <span key={j} style={css('font-size:14px;color:#3A4250;padding-left:12px;border-left:2px solid #ECE8E2')}><span style={css('color:#5B6472;font-variant-numeric:tabular-nums')}>{x.day}</span> <b>{x.kind}</b> {x.title}</span>)}
            </div>
          ))}
          {!dx.length ? <span style={css('font-size:14px;color:#5B6472')}>기록이 없습니다.</span> : null}
        </div>
        {/* 한 줄씩 고치기·지우기(!130) */}
        {hrows.length ? (
          <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:20px 24px;display:flex;flex-direction:column;gap:10px')}>
            <b style={css('font-size:15px')}>기록 고치기 <span style={css('color:#5B6472;font-weight:600;font-size:14px')}>{hrows.length}</span></b>
            {hrows.map(({ h, key }) => hedit === key ? (
              <PostForm key={key} action={`/dogs/${cur.id}/history/${encodeURIComponent(key)}`} style={css('display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;align-items:end;padding:12px;border-radius:12px;background:#FAF8F5;margin:0')}>
                <label style={css('display:flex;flex-direction:column;gap:4px')}><span style={css('font-size:13px;color:#5B6472')}>날짜</span><input className="inp" type="date" name="day" defaultValue={h.day} max={today_iso} style={css(FI)} /></label>
                <label style={css('display:flex;flex-direction:column;gap:4px')}><span style={css('font-size:13px;color:#5B6472')}>종류</span><select name="kind" defaultValue={h.kind} style={css(FI)}>{['진단', '수술', '재활'].map((k) => <option key={k}>{k}</option>)}</select></label>
                <label style={css('display:flex;flex-direction:column;gap:4px;min-width:0;grid-column:span 2')}><span style={css('font-size:13px;color:#5B6472')}>내용</span><input className="inp" name="title" defaultValue={h.title} style={css(FI)} /></label>
                <label style={css('display:flex;flex-direction:column;gap:4px')}><span style={css('font-size:13px;color:#5B6472')}>부위</span><select name="site" defaultValue={h.site} style={css(FI)}><option value="">없음</option>{Object.entries(SITE).map(([k, x]) => <option key={k} value={k}>{x}</option>)}</select></label>
                <label style={css('display:flex;flex-direction:column;gap:4px;min-width:0')}><span style={css('font-size:13px;color:#5B6472')}>담당 수의사</span><input className="inp" name="by" defaultValue={h.by} style={css(FI)} /></label>
                <span style={css('display:flex;gap:10px;align-items:center;height:44px')}><button className="bt" type="submit" style={css('height:44px;padding:0 14px;border-radius:9px;background:#1B2433;color:#fff;font-size:14px;font-weight:700')}>저장</button><a className="lk" href={link(`/dogs/${cur.id}?tab=dx`)} style={css('font-size:14px;color:#5B6472')}>취소</a></span>
              </PostForm>
            ) : (
              <div key={key} style={css('display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:14px;padding-top:8px;border-top:1px solid #F2EFEA')}>
                <span style={css('color:#5B6472;font-variant-numeric:tabular-nums')}>{h.day.slice(2).replaceAll('-', '.')}</span>
                <b style={css(`color:${h.kind === '수술' ? '#A8481A' : '#3A4250'}`)}>{h.kind}</b>
                <span style={css('flex:1;min-width:160px')}>{h.title}{h.site ? `, ${SITE[h.site] ?? ''}` : ''}{h.by ? <span style={css('color:#5B6472')}>, {h.by}</span> : null}</span>
                <a className="lk tap" href={link(`/dogs/${cur.id}?tab=dx&hedit=${encodeURIComponent(key)}`)} style={css('font-size:13px;font-weight:600;color:#B4501A')}>고치기</a>
                <PostForm action={`/dogs/${cur.id}/history/${encodeURIComponent(key)}`} style={css('display:inline;margin:0')} onBefore={() => window.confirm('이 기록을 지울까요? 되돌릴 수 없습니다.')}>
                  <input type="hidden" name="delete" value="1" />
                  <button className="bt tap" type="submit" style={css('background:none;font-size:13px;font-weight:600;color:#B4501A;padding:0')}>지우기</button>
                </PostForm>
              </div>
            ))}
          </div>
        ) : null}
        {/* QA 4: 진료 기록의 A(평가)도 진단 이력에서 본다. 고치기는 그 방문의 진료 기록에서 */}
        <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:20px 24px;display:flex;flex-direction:column;gap:10px')}>
          <b style={css('font-size:15px')}>진료 기록의 평가(A) <span style={css('color:#5B6472;font-weight:600;font-size:14px')}>{assess.length}</span></b>
          {assess.map((n) => (
            <a key={n.id} className="lk" href={link(`/dogs/${cur.id}?v=${n.at.slice(0, 10)}#${n.id}`)} style={css('display:flex;gap:10px;align-items:flex-start;min-height:44px;font-size:14px;padding-top:8px;border-top:1px solid #F2EFEA')}>
              <span style={css('color:#5B6472;font-variant-numeric:tabular-nums;white-space:nowrap')}>{n.at.slice(2, 10).replaceAll('-', '.')}</span>
              <span style={css('flex:1;min-width:0;white-space:pre-line;line-height:1.55')}>{n.text}</span>
              <span style={css('font-size:13px;color:#5B6472;white-space:nowrap')}>{n.author ? `${n.author.split(' ')[0]}, ` : ''}방문 ›</span>
            </a>
          ))}
          {!assess.length ? <span style={css('font-size:14px;color:#5B6472')}>진료 기록에 남긴 평가가 없습니다.</span> : null}
        </div>
      </>
    )
  }

  return (
    <Base acct={acct} me={me} nav="home" toast={toast} modals={<PetModal next_url={`/dogs/${cur.id}`} dogs={acct.dogs} />}>
      <main style={css('padding:20px 32px 64px;max-width:1600px;margin:0 auto;display:flex;flex-direction:column;gap:14px')}>
        <div style={css('display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap')}>
          <a className="lk tap" href={link('/home')} style={css('display:flex;align-items:center;gap:4px;font-size:14px;font-weight:600;color:#5B6472')}><svg width="16" height="16" viewBox="0 0 24 24"><use href="#w-back"></use></svg>목록</a>
          <div style={css('display:flex;gap:8px;flex-wrap:wrap')}><span data-pet={cur.id} style={css('height:40px;padding:0 14px;border-radius:10px;border:1px solid #E2DCD3;background:#fff;display:flex;align-items:center;font-size:14px;font-weight:600;cursor:pointer')}>정보 수정</span><a className="lk" href={link(`/upload?dog=${cur.id}`)} style={css('height:44px;padding:0 16px;border-radius:10px;background:#D2601A;color:#fff;display:flex;align-items:center;gap:6px;font-size:14px;font-weight:700')}><svg width="16" height="16" viewBox="0 0 24 24"><use href="#w-up"></use></svg>새 측정</a></div>
        </div>

        {/* 차트 위 고정 줄(EMR 처럼): 환자 정보 · 바이탈 · 메모 · 담당. 어느 탭에서든 보이고, 메모는 여기서 바로 쓴다 */}
        <div className="chart-strip">
          <section className="cs-card">
            <span className="cs-lb">환자 정보, {row.no}</span>
            <span style={css('display:flex;align-items:center;gap:8px')}><b style={css('font-size:22px;letter-spacing:-0.4px')}>{row.name}</b><span style={css(`padding:2px 8px;border-radius:7px;background:${row.st_bg};color:${row.st_c};font-size:13px;font-weight:700`)}>{row.stage}</span></span>
            <span style={css('font-size:14px;color:#3A4250')}>{row.breed}, {row.size}, {row.age}, {row.sex}</span>
            <span style={css('font-size:13px;color:#5B6472')}>보호자 <b style={css('color:#1B2433')}>{row.owner}</b>{cur.phone ? <>{' '}<span style={css('font-variant-numeric:tabular-nums')}>{cur.phone}</span></> : null}</span>
            {row.badges.length ? <span style={css('display:flex;gap:5px;flex-wrap:wrap')}>{row.badges.map((b, i) => <span key={i} style={css(`padding:2px 8px;border-radius:6px;background:${tone[b.kind][0]};color:${tone[b.kind][1]};font-size:12px;font-weight:700`)}>{b.full || b.t}</span>)}</span> : null}
          </section>
          <section className="cs-card">
            <span className="cs-lb">바이탈</span>
            <div className="cs-vit">{VKEYS.map(([k, key]) => <span key={key}><span className="cs-lb" style={css('white-space:nowrap')}>{k}<VFlagBadge f={row.v.f[key]} /></span><VV value={row.v[key]} f={row.v.f[key]} size={18} badge={false} /></span>)}</div>
            {kgt.has ? <span title={`최근 ${kgt.n}번 방문 체중(${kgt.since}부터)`} style={css('display:flex;align-items:center;gap:6px;font-size:12px;color:#5B6472;white-space:nowrap')}><span className="cs-lb" style={css('font-weight:600')}>체중 추이</span><svg width={kgt.W} height={kgt.H} viewBox={`0 0 ${kgt.W} ${kgt.H}`}><polyline points={kgt.line} fill="none" stroke="#D2601A" strokeWidth="1.8" strokeLinejoin="round"></polyline><circle cx={kgt.last[0]} cy={kgt.last[1]} r="2.6" fill="#D2601A"></circle></svg><span style={css('font-variant-numeric:tabular-nums')}>{kgt.text}{' '}<b style={css(`color:${kgt.c}`)}>{kgt.ch}</b></span></span> : null}
          </section>
          <section className="cs-card" style={css('min-width:0')}>
            <span className="cs-lb">메모 ({memos.length})</span>
            <div className="memo-row">
              {memos.map((x, i) => <MemoCard key={x.id || `m${i}`} x={x} edit_url={here + '&edit='} />)}
              {!memos.length ? <span style={css('font-size:13px;color:#5B6472;padding:8px 0')}>입질·약 알레르기·연락 시간처럼 매번 알아야 할 것을 적어 두세요.</span> : null}
            </div>
            <MemoForm dog_id={cur.id} next_url={here} memo_cat={MEMO_CAT} edit={edit_memo} />
          </section>
          <section className="cs-card">
            <span className="cs-lb">담당</span>
            <span style={css('font-size:14px')}><span style={css('color:#5B6472')}>주치의</span>{' '}<b>{team.doctor}</b></span>
            <span style={css('font-size:14px')}><span style={css('color:#5B6472')}>최근 측정</span>{' '}<b>{team.measurer}</b></span>
          </section>
        </div>

        <div style={css('display:flex;gap:4px;border-bottom:1px solid #E2DCD3;overflow-x:auto;overflow-y:hidden')}>
          {CHART_TABS.map(([key, label]) => (
            <a key={key} className="lk" href={link(`/dogs/${cur.id}?tab=${key}`)} style={css(`padding:12px 16px;font-size:15px;white-space:nowrap;font-weight:${tab == key ? 700 : 500};color:${tab == key ? '#B4501A' : '#5B6472'};border-bottom:2.5px solid ${tab == key ? '#D2601A' : 'transparent'};margin-bottom:-1px`)}>{label}{key === 'visits' ? <>{' '}<span style={css('font-size:13px;color:#5B6472')}>{vis.length}</span></> : null}</a>
          ))}
        </div>

        {body}
      </main>
    </Base>
  )
}

/** 바이탈 한 날짜 쓰기·고치기(진행 탭 표 안). 백엔드는 PUT /dogs/{id}/vitals/{날짜}: 적은 값만 바뀐다. 지우기는 표의 '지우기'(DELETE) */
function VitalForm({ dog_id, day, today, author, v }: { dog_id: string; day: string; today: string; author: string; v?: { kg: string; temp: string; hr: string; sbp: string; dbp: string } }) {
  const back = `/dogs/${dog_id}?tab=progress`
  return (
    <PostForm action={`/dogs/${dog_id}/vitals`} style={css('display:grid;grid-template-columns:130px repeat(5,minmax(0,1fr)) auto;gap:8px;align-items:end;padding:10px 12px;border-radius:12px;background:#FAF8F5;margin:0')}>
      <input type="hidden" name="next_url" value={back} />
      <input type="hidden" className="author-inp" name="author" defaultValue={author} />
      <label style={css('display:flex;flex-direction:column;gap:4px;font-size:12px;color:#5B6472;font-weight:600')}>날짜{v ? <><input type="hidden" name="day" value={day} /><b style={css('height:36px;display:flex;align-items:center;font-size:14px;color:#1B2433')}>{day.slice(2).replaceAll('-', '.')}</b></> : <input className="inp" type="date" name="day" defaultValue={day} max={today} style={css(VIN)} />}</label>
      {([['kg', '체중 kg'], ['temp', '체온 ℃'], ['hr', '심박 bpm'], ['sbp', '수축기'], ['dbp', '이완기']] as const).map(([nm, label]) => (
        <label key={nm} style={css('display:flex;flex-direction:column;gap:4px;min-width:0;font-size:12px;color:#5B6472;font-weight:600')}>{label}<input className="inp" name={nm} inputMode="decimal" defaultValue={v ? v[nm] : ''} style={css(VIN)} /></label>
      ))}
      <span style={css('display:flex;gap:8px;align-items:center;height:36px')}><button className="bt" type="submit" style={css('height:44px;padding:0 12px;border-radius:9px;background:#1B2433;color:#fff;font-size:13px;font-weight:700;white-space:nowrap')}>저장</button><a className="lk" href={link(back)} style={css('font-size:13px;color:#5B6472;white-space:nowrap')}>취소</a></span>
    </PostForm>
  )
}
