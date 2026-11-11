// results.html + main.py results(): 분석 결과 목록(반려견 칩으로 거르기)
// 11-09 QA: 반려견이 백 마리를 넘으면 칩만으로는 못 고른다 → 이름·견종·동물번호 검색으로 칩과 목록을 좁힌다. 칩은 분석이 있는 반려견만
import { Base } from '../app/Base'
import { css } from '../app/css'
import { usePage, useTitle } from '../app/page'
import { dogOf } from '../store/db'
import { avatar, sess_no, st_chip, wkg } from '../views/views'
import { link } from '../config'
import { useState } from 'react'

/** 한 번에 그리는 줄 수. 회차가 수백 건 쌓이면 한 번에 다 그리지 않는다 */
const PAGE = 50

export default function Results() {
  const { acct, me, toast, query } = usePage({ login: true })
  useTitle('분석 결과 · Paw oh Paw')
  // 훅은 return 앞에서 부른다(로그인 상태가 바뀌어도 훅 순서가 같게)
  const [shown, setShown] = useState(PAGE)
  const [dq, setDq] = useState('')
  if (!acct) return null
  const dog = query.get('dog') ?? 'all'
  const filt = dogOf(acct, dog) ? dog : 'all'
  const kw = dq.trim()
  const hit = (id: string) => { const d = dogOf(acct, id); return !!d && (!kw || `${d.name} ${d.breed} ${d.no}`.includes(kw)) }
  const hasRes = new Set(acct.results.map((r) => r.dog))
  const chips = [{ id: 'all', init: '전체', name: '전체', breed: '', ...avatar(filt === 'all') }]
  chips.push(...acct.dogs.filter((d) => hasRes.has(d.id) && (hit(d.id) || d.id === filt)).map((d) => ({ id: d.id, init: d.name.slice(0, 1), name: d.name, breed: d.breed || '견종 미입력', ...avatar(filt === d.id) })))
  const all = acct.results.filter((r) => dogOf(acct, r.dog) && (filt === 'all' ? hit(r.dog) : r.dog === filt))
  const rows = all
    .slice(0, shown)
    .map((r, i) => ({
      id: r.id, name: dogOf(acct, r.dog)!.name, when: `${r.date} · ${sess_no(acct, r)}회차`,
      ...st_chip(r.st), pass: r.st === 'fail' ? '—' : `${r.ps[1]} / ${r.ps[0]}`,
      sym: r.st === 'fail' ? '—' : `${r.sym}점`, w: wkg(r.w), bt: i ? '1px solid #F2EFEA' : 'none',
    }))

  return (
    <Base acct={acct} me={me} nav="results" toast={toast}>
      <main style={css('max-width:none;margin:0;padding:32px 80px 96px;display:flex;flex-direction:column;gap:20px')}>
        <div style={css('display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap')}>
          <h1 style={css('margin:0;font-size:28px;font-weight:800;letter-spacing:-0.9px')}>분석 결과</h1>
          <label style={css('width:360px;max-width:100%;height:44px;border-radius:22px;border:1px solid #E2DCD3;background:#fff;display:flex;align-items:center;gap:8px;padding:0 16px;color:#5B6472')}>
            <svg width="18" height="18" viewBox="0 0 24 24" style={{ flex: 'none' }}><circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.8"></circle><path d="M16 16l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"></path></svg>
            <input value={dq} onChange={(e) => { setDq(e.target.value); setShown(PAGE) }} placeholder="반려견 이름 · 견종 · 동물번호로 찾기" style={css('flex:1;min-width:0;border:none;outline:none;font-size:15px;background:transparent;color:#1B2433;font-family:inherit')} />
          </label>
        </div>
        <div style={css('display:flex;gap:28px;overflow-x:auto;padding:8px 6px 6px;align-items:flex-start')}>
          {chips.map((d) => (
            <a key={d.id} className="lk" href={link(`/results?dog=${d.id}`)} style={css('flex:none;width:96px;display:flex;flex-direction:column;align-items:center;gap:10px;text-align:center')}>
              <div style={css(`width:80px;height:80px;border-radius:50%;background:${d.av};color:${d.avc};display:flex;align-items:center;justify-content:center;font-size:${d.id === 'all' ? 18 : 28}px;font-weight:800;box-shadow:${d.ring};transition:box-shadow .2s`)}>{d.init}</div>
              <div style={css('display:flex;flex-direction:column;gap:2px')}><span style={css(`font-size:15px;color:${d.nc};font-weight:${d.nw}`)}>{d.name}</span>{d.breed ? <span style={css('font-size:13px;color:#5B6472')}>({d.breed})</span> : null}</div>
            </a>
          ))}
        </div>
        <div style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;overflow-x:auto')}>
          <div className="tbl" style={css('--tw:720px;--tw-n:560px')}>
            <div className="tbl-r" style={css('--tc:1.1fr 1.4fr 1fr 1fr 1fr 1fr 40px;--tc-n:1.1fr 1.4fr 1fr 1fr 1fr 32px;display:grid;gap:12px;padding:14px 24px;border-bottom:1px solid #ECE8E2;font-size:13px;font-weight:700;color:#5B6472')}><span>반려견</span><span>측정일 · 회차</span><span>상태</span><span>유효 통과</span><span>대칭 점수</span><span className="tbl-opt">체중</span><span></span></div>
            {rows.map((r) => (
              <a key={r.id} className="lk hv-row tbl-r" href={link(`/results/${r.id}`)} style={css(`--tc:1.1fr 1.4fr 1fr 1fr 1fr 1fr 40px;--tc-n:1.1fr 1.4fr 1fr 1fr 1fr 32px;display:grid;gap:12px;align-items:center;padding:16px 24px;border-top:${r.bt};font-size:15px;font-variant-numeric:tabular-nums`)}>
                <b>{r.name}</b><span style={css('color:#5B6472')}>{r.when}</span><span><span style={css(`height:26px;padding:0 10px;border-radius:8px;font-size:13px;font-weight:700;background:${r.bg};color:${r.c};display:inline-flex;align-items:center`)}>{r.st}</span></span><span>{r.pass}</span><span>{r.sym}</span><span className="tbl-opt">{r.w}</span><svg width="18" height="18" viewBox="0 0 24 24" style={css('color:#5B6472')}><use href="#w-chev"></use></svg>
              </a>
            ))}
            {all.length > shown ? <div style={css('padding:14px;display:flex;justify-content:center;border-top:1px solid #F2EFEA')}><button type="button" className="bt" onClick={() => setShown(shown + PAGE)} style={css('height:44px;padding:0 20px;border-radius:12px;border:1px solid #E2DCD3;background:#fff;font-size:15px;font-weight:700;cursor:pointer')}>{`더 보기 (${all.length - shown}건 남음)`}</button></div> : null}
            {!rows.length ? <div style={css('padding:48px 24px;text-align:center;display:flex;flex-direction:column;align-items:center;gap:12px')}><b style={css('font-size:18px')}>아직 분석 결과가 없습니다</b><a className="lk" href={link('/upload')} style={css('height:46px;padding:0 18px;border-radius:12px;background:#D2601A;color:#fff;display:flex;align-items:center;font-size:15px;font-weight:700')}>보행 영상 분석하기</a></div> : null}
          </div>
        </div>
      </main>
    </Base>
  )
}
