// 약관·개인정보 처리방침·사업자 정보·고객센터. 본문은 legal/content.ts (로그인 전후 모두 열 수 있다)
import { Base } from '../app/Base'
import { css } from '../app/css'
import { usePage, useTitle } from '../app/page'
import { LEGAL, LEGAL_PATH, type LegalKind } from '../legal/content'
import { link } from '../config'
import AuthBar from './parts/AuthBar'

export default function Legal({ kind }: { kind: LegalKind }) {
  const doc = LEGAL[kind]
  useTitle(`${doc.title}`)
  const { acct, me, toast } = usePage()
  const others = (Object.keys(LEGAL) as LegalKind[]).filter((k) => k !== kind)
  return (
    <Base acct={acct} me={me} toast={toast} topbar={acct ? undefined : <AuthBar />}>
      <main style={css('max-width:760px;margin:5vh auto 96px;padding:0 24px')}>
        <article style={css('background:#fff;border:1px solid #ECE8E2;border-radius:24px;padding:48px 44px;display:flex;flex-direction:column;gap:28px')}>
          <header style={css('display:flex;flex-direction:column;gap:8px')}>
            <h1 style={css('margin:0;font-size:28px;font-weight:800;letter-spacing:-0.6px')}>{doc.title}</h1>
            <p style={css('margin:0;font-size:15px;color:#5B6472')}>{doc.sub}, 시행 {doc.updated}</p>
          </header>
          {doc.notice && <div style={css('background:#FAF1DF;border-radius:12px;padding:14px 18px;font-size:15px;line-height:1.5;color:#7A5410')}>{doc.notice}</div>}
          {doc.sections.map((s) => (
            <section key={s.h} style={css('display:flex;flex-direction:column;gap:10px')}>
              <h2 style={css('margin:0;font-size:18px;font-weight:700')}>{s.h}</h2>
              {s.h === '자주 묻는 질문'
                ? s.p.map((t, i) => {
                    // "질문 — 답변" 한 줄을 질문 카드(펼치면 답변)로
                    const k = t.indexOf(' — ')
                    const q = k > 0 ? t.slice(0, k) : t, a = k > 0 ? t.slice(k + 3) : ''
                    return (
                      <details key={i} style={css('border:1px solid #ECE8E2;border-radius:14px;background:#FAF9F6;padding:0 18px')}>
                        <summary style={css('list-style:none;cursor:pointer;display:flex;align-items:center;gap:12px;padding:15px 0;font-size:15px;font-weight:700;color:#1B2433')}>
                          <span style={css('flex:none;width:26px;height:26px;border-radius:8px;background:#D2601A;color:#fff;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800')}>Q</span>
                          <span style={css('flex:1')}>{q}</span>
                          <svg width="18" height="18" viewBox="0 0 24 24" style={css('color:#5B6472;flex:none')}><path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
                        </summary>
                        {a ? <p style={css('margin:0;padding:0 0 16px 38px;font-size:15px;line-height:1.7;color:#3A4250')}>{a}</p> : null}
                      </details>
                    )
                  })
                : s.p.map((t, i) => <p key={i} style={css('margin:0;font-size:15px;line-height:1.7;color:#3A4250')}>{t}</p>)}
            </section>
          ))}
          <nav style={css('display:flex;flex-wrap:wrap;gap:12px;padding-top:12px;border-top:1px solid #ECE8E2;font-size:14px;font-weight:600;color:#5B6472')}>
            {others.map((k) => <a key={k} className="lk tap" href={link(LEGAL_PATH[k])}>{LEGAL[k].title}</a>)}
          </nav>
        </article>
      </main>
    </Base>
  )
}
