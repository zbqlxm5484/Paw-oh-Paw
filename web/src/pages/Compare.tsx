// compare.html + main.py compare(): 경과 비교(기준·직전 회차 대비, 회차별 추이)
import { useEffect, useState, type MouseEvent } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { usePage, useTitle } from '../app/page'
import { redirect, setToast, type Go } from '../app/session'
import { dogOf } from '../store/db'
import { compare_view, seg, TREND_KEYS, valid } from '../views/views'
import { link } from '../config'
import { api, type CompareOut } from '../api/client'
import { MOCK } from '../store/backend'
import { serverCompareRows } from '../views/vet'
import { ChangeProfile } from './parts/ChangeProfile'
import { mainGait } from './parts/VetSections'

/** 서버의 RedirectResponse: 지금 주소를 바꿔 치운다 */
function useRedirect(g: Go | null) {
  const navigate = useNavigate()
  useEffect(() => {
    if (!g) return
    if (g.toast) setToast(g.toast)
    navigate(g.to, { replace: true })
  })
}

export default function Compare() {
  const { dog_id = '' } = useParams()
  const { acct, me, toast, query } = usePage({ login: true })
  const navigate = useNavigate()
  const loc = useLocation()
  const d = acct ? dogOf(acct, dog_id) : undefined
  useTitle(`${d ? d.name : ''} 경과 비교 · Paw oh Paw`)
  const cmpKey = query.get('cmp') === 'prev' ? 'prev' : 'base'
  const remoteDog = !MOCK && !!d && !!acct?.results.some((r) => r.dog === d.id && (r.src ?? '').startsWith('backend:'))
  const [srv, setSrv] = useState<{ key: string; o: CompareOut } | null>(null)
  useEffect(() => {
    if (!remoteDog || !d) return
    let alive = true
    // target 을 비우면 서버가 '가장 최근 완료 회차'를 쓰는데, 통과 0건(실패) 회차면 전 항목이 비교 불가가 된다 → 유효한 최근 회차를 지정
    api.compare(d.id, cmpKey === 'base' ? 'BASELINE' : 'PREVIOUS', acct ? valid(acct, d.id)[0]?.id : undefined)
      .then((o) => alive && setSrv({ key: cmpKey, o }))
      .catch(() => alive && setSrv(null)) // 비교 API 가 없거나 비교할 수 없으면 이 브라우저 계산 그대로
    return () => {
      alive = false
    }
  }, [remoteDog, d, cmpKey])
  let go: Go | null = null
  if (acct && !d) go = redirect('/home')
  else if (acct && d && valid(acct, d.id).length < 2) go = redirect(`/dogs/${dog_id}`, '유효한 회차가 2개 이상 있어야 비교할 수 있습니다')
  useRedirect(go)
  if (!acct || !d || go) return null

  const cmp0 = query.get('cmp') ?? 'base'
  const tk0 = query.get('tk') ?? 'rom'
  const cmp = cmp0 === 'base' || cmp0 === 'prev' ? cmp0 : 'base'
  const tk = TREND_KEYS.some(([k]) => k === tk0) ? tk0 : 'rom'
  const trend = TREND_KEYS.map(([k, label]) => ({ key: k, label, on: k === tk }))
  const cp0 = compare_view(acct, d, cmp, tk)
  // 백엔드 회차면 증가·감소 판정은 서버 비교 API(15.8, 수치별 오차 범위·통과 8회 조건)를 쓴다. 추이 그림은 그대로
  const cp = cp0.has && srv && srv.key === cmp ? { ...cp0, ...serverCompareRows(srv.o, d.focus) } : cp0
  const segs = seg([['base', '기준 회차 대비'], ['prev', '직전 회차 대비']], cmp)
  // href="?cmp=..." 는 상대 주소라 Base 가 가로채지 않는다 → 새로 불러오지 않게 여기서 이동
  const rel = (href: string) => (e: MouseEvent) => {
    if (e.button !== 0 || e.metaKey || e.ctrlKey) return
    e.preventDefault()
    navigate(loc.pathname + href)
  }

  return (
    <Base acct={acct} me={me} nav="home" toast={toast}>
      <main style={css('max-width:none;margin:0;padding:24px 80px 96px;display:flex;flex-direction:column;gap:20px')}>
        <a className="lk" href={link(`/dogs/${d.id}`)} style={css('align-self:flex-start;display:flex;align-items:center;gap:4px;font-size:14px;font-weight:600;color:#5B6472')}><svg width="16" height="16" viewBox="0 0 24 24"><use href="#w-back"></use></svg>{d.name} 차트</a>
        <div style={css('display:flex;flex-direction:column;gap:6px')}><h1 style={css('margin:0;font-size:32px;font-weight:800;letter-spacing:-0.8px')}>{cp.name} 경과 비교</h1></div>
        {!cp.has ? (
          <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:40px 32px;font-size:15px;color:#5B6472')}>비교하려면 유효한 회차가 2개 이상 필요합니다.</div>
        ) : (
          <>
            <div style={css('display:flex;align-items:center;gap:16px;flex-wrap:wrap')}>
              <div style={css('display:grid;grid-template-columns:1fr 1fr;padding:4px;border-radius:12px;background:#EEE8DF;width:380px;max-width:100%')}>
                {segs.map((g) => <a key={g.key} className="lk" href={link(`?cmp=${g.key}&tk=${tk}`)} onClick={rel(`?cmp=${g.key}&tk=${tk}`)} style={css(`height:42px;border-radius:9px;background:${g.bg};color:${g.c};box-shadow:${g.sh};display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700;transition:background .2s`)}>{g.label}</a>)}
              </div>
              <div style={css('flex:0 0 auto;max-width:100%;background:#fff;border:1px solid #ECE8E2;border-radius:14px;padding:12px 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap')}>
                <div><span style={css('font-size:12.5px;color:#5B6472;font-weight:600')}>{cp.baseLabel}</span><b style={css('display:block;font-size:16px;font-variant-numeric:tabular-nums')}>{cp.baseDate}</b></div>
                <svg width="22" height="22" viewBox="0 0 24 24" style={css('color:#A0A7B2')}><path d="M3 12h17M14 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"></path></svg>
                <div><span style={css('font-size:12.5px;color:#5B6472;font-weight:600')}>최근 회차</span><b style={css('display:block;font-size:16px;font-variant-numeric:tabular-nums')}>{cp.tDate}</b></div>
              </div>
            </div>
            {cp.modelChanged ? (
              <div style={css('background:#FAF1DF;border-radius:12px;padding:14px 18px;font-size:14.5px;line-height:1.5;color:#7A5410;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap')}><span>{cp.modelMsg}</span></div>
            ) : null}
            <div style={css('display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:16px;align-items:start')}>
              <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:4px 22px')}>
                {cp.rows.map((r, i) => (
                  <div key={i} style={css(`display:flex;align-items:center;gap:12px;padding:14px 0;border-top:${r.bt}`)}>
                    <div style={css('flex:1;min-width:0')}><div style={css('display:flex;align-items:center;gap:8px;flex-wrap:wrap')}><span style={css('font-size:15.5px;font-weight:600')}>{r.n}</span><span style={css(`font-size:12.5px;font-weight:700;color:${r.lc}`)}>{r.limb}</span></div><div style={css('font-size:13.5px;color:#5B6472;margin-top:3px;font-variant-numeric:tabular-nums')}>{r.vals}</div></div>
                    <span style={css(`height:28px;padding:0 10px;border-radius:7px;background:${r.bg};color:${r.c};font-size:13px;font-weight:700;display:flex;align-items:center;white-space:nowrap;font-variant-numeric:tabular-nums;flex:none`)}>{r.j}</span>
                  </div>
                ))}
              </div>
              <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:22px 24px 18px;display:flex;flex-direction:column;gap:14px')}>
                <div style={css('display:flex;justify-content:space-between;align-items:center')}><b style={css('font-size:16px')}>회차별 추이</b>{cp.two ? <div style={css('display:flex;gap:12px;font-size:13px;font-weight:600;color:#5B6472')}><span style={css('display:flex;align-items:center;gap:6px')}><span style={css('width:10px;height:10px;border-radius:3px;background:#3B6FE0')}></span>왼쪽</span><span style={css('display:flex;align-items:center;gap:6px')}><span style={css('width:10px;height:10px;border-radius:3px;background:#E5604D')}></span>오른쪽</span></div> : null}</div>
                <div style={css('display:flex;gap:8px;flex-wrap:wrap')}>
                  {trend.map((c) => <a key={c.key} className="lk" href={link(`?cmp=${cmp}&tk=${c.key}`)} onClick={rel(`?cmp=${cmp}&tk=${c.key}`)} style={css(`height:36px;padding:0 14px;border-radius:18px;background:${c.on ? '#1B2433' : '#fff'};color:${c.on ? '#fff' : '#3A4250'};border:1px solid ${c.on ? '#1B2433' : '#ECE8E2'};display:flex;align-items:center;font-size:14px;font-weight:600`)}>{c.label}</a>)}
                </div>
                <svg viewBox="0 0 320 150" style={css('width:100%;display:block')}>
                  <g stroke="#ECE8E2" strokeDasharray="3 4"><line x1="20" y1="20" x2="300" y2="20"></line><line x1="20" y1="75" x2="300" y2="75"></line><line x1="20" y1="130" x2="300" y2="130"></line></g>
                  <polyline points={cp.tl} fill="none" stroke="#3B6FE0" strokeWidth="2.2" strokeLinejoin="round"></polyline>
                  <polyline points={cp.tr} fill="none" stroke="#E5604D" strokeWidth="2.2" strokeDasharray="5 4" strokeLinejoin="round"></polyline>
                  {cp.dl.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r="3.6" fill="#fff" stroke={p.c} strokeWidth="2"></circle>)}
                </svg>
                <div style={css('display:flex;justify-content:space-between;padding:0 2px;margin-top:-6px;font-size:12.5px;color:#A0A7B2;font-variant-numeric:tabular-nums')}>{cp.xl.map((x, i) => <span key={i}>{x}</span>)}</div>
                <span style={css('font-size:13px;color:#5B6472')}>{cp.focusNote}</span>
              </div>
            </div>
            {/* 기준 회차 대비일 때: 관절별 변화 막대 + 오차 범위 띠 + 작은 추이선(QA 2절) */}
            {cmp === 'base' && valid(acct, d.id)[0] ? (
              <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:22px 24px')}>
                <ChangeProfile acct={acct} r={valid(acct, d.id)[0]} gait={mainGait(valid(acct, d.id)[0])} fromServer={remoteDog} />
              </div>
            ) : null}
          </>
        )}
      </main>
    </Base>
  )
}
