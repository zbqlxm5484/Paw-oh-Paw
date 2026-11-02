// admin.html: 크림오프 관리 (ADMIN 은 전부, STAFF 는 보기만). ?demo=1 은 관리자 계정(s_admin)으로 들어간다
import { useEffect, useRef } from 'react'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { PostForm, useTitle } from '../app/page'
import { currentStaff, redirect, setLogin } from '../app/session'
import { activeCount, codesOf, contractStatus, db, show_code, staffOf } from '../store/db'
import type { Staff } from '../store/types'
import AuthBar, { usePublicPage } from './parts/AuthBar'

const BTN = 'height:40px;padding:0 14px;border-radius:10px;border:1px solid #E2DCD3;background:#fff;font-size:14px;font-weight:600;cursor:pointer'
const INP = 'height:40px;border-radius:10px;border:1px solid #ECE8E2;background:#fff;padding:0 12px;font-size:14px;color:#1B2433'

interface CodeRow { id: string; code: string; max: number; used: number; revoked: boolean; note: string }
interface StaffRow { id: string; login_id: string; name: string; email: string; active: boolean; joined: string }
interface InstRow { id: string; code: string; name: string; ends: string; status: string; codes: CodeRow[]; staff: StaffRow[] }

/** main.py admin_staff: 크림오프 계정(ADMIN·STAFF)만 */
function admin_staff(demo: string): Staff | undefined {
  const s = demo ? db.staff['s_admin'] : currentStaff()
  return s && (s.role === 'ADMIN' || s.role === 'STAFF') ? s : undefined
}

/** main.py admin_rows: 크림오프를 뺀 기관을 이름순(파이썬 문자열 비교)으로 */
function admin_rows(): InstRow[] {
  return Object.values(db.accounts)
    .filter((x) => x.id !== 'creamoff')
    .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))
    .map((a) => ({
      id: a.id, code: a.code || '-', name: a.name, ends: a.contract_ends || '', status: contractStatus(a),
      codes: codesOf(a.id).map((c) => ({ id: c.id, code: show_code(c.code), max: c.max_accounts, used: activeCount(c.id), revoked: c.revoked, note: c.note })),
      staff: staffOf(a.id).map((s) => ({ id: s.id, login_id: s.login_id, name: s.name, email: s.email, active: s.active, joined: s.joined })),
    }))
}

// 코드 한 줄: 상한·회수 버튼이 같은 폼이라 누른 버튼(revoke=1)을 폼 값에 넣는다(FormData 는 누른 버튼을 안 담는다)
function CodeLine({ c, can_write }: { c: CodeRow; can_write: boolean }) {
  const revoke = useRef(false)
  return (
    <div style={css(`display:flex;align-items:center;gap:10px;border-top:1px solid #F2EFEA;padding-top:8px;opacity:${c.revoked ? '.5' : '1'}`)}>
      <code style={css('font-size:14px;letter-spacing:.5px')}>{c.code}</code><span style={css('font-size:13px;color:#5B6472')}>{c.note}</span>
      <span style={css('margin-left:auto;font-size:13px;color:#5B6472')}>{c.revoked ? '회수됨' : `계정 ${c.used} / ${c.max}`}</span>
      {can_write && !c.revoked && (
        <PostForm action={`/admin/codes/${c.id}`} style={css('display:flex;gap:6px')}
          onBefore={(fd) => {
            if (revoke.current && !fd.has('revoke')) fd.set('revoke', '1')
            revoke.current = false
          }}><input type="number" name="max_accounts" min="1" max="10" defaultValue={c.max} style={css(`${INP};width:64px`)} /><button type="submit" onClick={() => { revoke.current = false }} style={css(BTN)}>상한</button><button type="submit" name="revoke" value="1" onClick={() => { revoke.current = true }} style={css(`${BTN};color:#C2412D`)}>회수</button></PostForm>
      )}
    </div>
  )
}

export default function Admin() {
  useTitle('크림오프 관리 · Paw oh Paw')
  const { toast, query, go } = usePublicPage()
  const demo = query.get('demo') || ''
  const s = admin_staff(demo)
  useEffect(() => {
    if (!s) go(redirect('/login', '크림오프 계정으로 로그인해 주세요'))
    else if (demo) {
      // 바로가기: 관리자 계정으로 들어간다(login_as)
      setLogin(s.id)
      go(redirect('/admin'))
    }
  })
  if (!s || demo) return null
  const me = s
  const can_write = s.role === 'ADMIN'
  const insts = admin_rows()

  return (
    <Base me={me} toast={toast} topbar={<AuthBar />}>
      <main style={css('max-width:1100px;margin:0 auto;padding:36px 32px 96px;display:flex;flex-direction:column;gap:24px')}>
        <div style={css('display:flex;align-items:flex-end;gap:16px')}>
          <div style={css('display:flex;flex-direction:column;gap:6px')}><span style={css('font-size:14px;color:#5B6472')}>크림오프 운영</span><h1 style={css('margin:0;font-size:32px;font-weight:800;letter-spacing:-0.8px')}>기관·디바이스 코드·계정</h1></div>
          <span style={css('margin-left:auto;font-size:14px;color:#5B6472')}>{me.name} · {can_write ? '관리자' : '임시 스태프 (보기만)'}</span>
          <PostForm action="/logout"><button type="submit" style={css(BTN)}>로그아웃</button></PostForm>
        </div>
        {can_write && (
          <PostForm action="/admin/institutions" style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:20px 24px;display:flex;gap:12px;align-items:center;flex-wrap:wrap')}>
            <b style={css('font-size:16px')}>기관 추가</b>
            <input name="name" placeholder="기관명" style={css(`${INP};flex:1;min-width:200px`)} />
            <label style={css('font-size:14px;color:#5B6472;display:flex;gap:8px;align-items:center')}>계약 종료일<input type="date" name="ends" style={css(INP)} /></label>
            <button type="submit" style={css(`${BTN};background:#1B2433;color:#fff;border:0`)}>만들기</button>
          </PostForm>
        )}
        {insts.map((i) => (
          <section key={i.id} style={css('background:#fff;border:1px solid #ECE8E2;border-radius:18px;padding:22px 24px;display:flex;flex-direction:column;gap:14px')}>
            <div style={css('display:flex;align-items:center;gap:12px;flex-wrap:wrap')}>
              <h2 style={css('margin:0;font-size:20px;font-weight:800')}>{i.name}</h2><span style={css('font-size:13px;color:#A0A7B2')}>{i.code}</span>
              <span style={css(`height:26px;padding:0 10px;border-radius:999px;font-size:13px;font-weight:700;display:flex;align-items:center;background:${i.status === 'ACTIVE' ? '#E6F4EC' : '#FBEAE6'};color:${i.status === 'ACTIVE' ? '#2E8B57' : '#C2412D'}`)}>{i.status === 'ACTIVE' ? '계약 중' : '계약 만료'}</span>
              <PostForm action={`/admin/institutions/${i.id}`} style={css('margin-left:auto;display:flex;gap:8px;align-items:center')}><span style={css('font-size:14px;color:#5B6472')}>계약 종료일</span><input type="date" name="ends" defaultValue={i.ends} disabled={!can_write} style={css(INP)} />{can_write && <button type="submit" style={css(BTN)}>저장</button>}</PostForm>
            </div>
            <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:18px')}>
              <div style={css('display:flex;flex-direction:column;gap:8px')}><b style={css('font-size:15px')}>디바이스 코드</b>
                {i.codes.map((c) => <CodeLine key={c.id} c={c} can_write={can_write} />)}
                {can_write && <PostForm action={`/admin/institutions/${i.id}/codes`} style={css('display:flex;gap:8px;margin-top:4px')}><input name="note" placeholder="메모 (예: 2호기)" style={css(`${INP};flex:1`)} /><input type="number" name="max_accounts" min="1" max="10" defaultValue="3" style={css(`${INP};width:64px`)} /><button type="submit" style={css(BTN)}>코드 발급</button></PostForm>}
              </div>
              <div style={css('display:flex;flex-direction:column;gap:8px')}><b style={css('font-size:15px')}>담당자 계정</b>
                {i.staff.map((st) => (
                  <div key={st.id} style={css(`display:flex;align-items:center;gap:10px;border-top:1px solid #F2EFEA;padding-top:8px;opacity:${st.active ? '1' : '.5'}`)}>
                    <b style={css('font-size:14px')}>{st.name}</b><span style={css('font-size:13px;color:#5B6472')}>{st.login_id} · {st.email}</span>
                    <span style={css('margin-left:auto;font-size:13px;color:#5B6472')}>{st.active ? '사용 중' : '중지됨'}</span>
                    {can_write && <PostForm action={`/admin/staff/${st.id}`}><button type="submit" style={css(BTN)}>{st.active ? '중지' : '재개'}</button></PostForm>}
                  </div>
                ))}
                {i.staff.length === 0 && <span style={css('font-size:14px;color:#A0A7B2')}>아직 가입한 담당자가 없어요</span>}
              </div>
            </div>
          </section>
        ))}
        <p style={css('margin:0;font-size:13px;color:#A0A7B2')}>크림오프 계정은 기관의 반려견·측정 자료를 열람하지 않아요(기관별 분리). 관리자·스태프 계정은 운영 스크립트로만 만들어요.</p>
      </main>
    </Base>
  )
}
