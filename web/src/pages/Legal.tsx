// 약관·개인정보 처리방침·사업자 정보·고객센터. 본문은 legal/content.ts (로그인 전후 모두 열 수 있다)
import { Base } from '../app/Base'
import { css } from '../app/css'
import { usePage, useTitle } from '../app/page'
import { LEGAL, LEGAL_PATH, type LegalKind } from '../legal/content'
import { link } from '../config'
import AuthBar from './parts/AuthBar'

export default function Legal({ kind }: { kind: LegalKind }) {
  const doc = LEGAL[kind]
  useTitle(`${doc.title} · Paw oh Paw`)
  const { acct, me, toast } = usePage()
  const others = (Object.keys(LEGAL) as LegalKind[]).filter((k) => k !== kind)
  return (
    <Base acct={acct} me={me} toast={toast} topbar={acct ? undefined : <AuthBar />}>
      <main style={css('max-width:760px;margin:5vh auto 96px;padding:0 24px')}>
        <article style={css('background:#fff;border:1px solid #ECE8E2;border-radius:24px;padding:48px 44px;display:flex;flex-direction:column;gap:28px')}>
          <header style={css('display:flex;flex-direction:column;gap:8px')}>
            <h1 style={css('margin:0;font-size:28px;font-weight:800;letter-spacing:-0.6px')}>{doc.title}</h1>
            <p style={css('margin:0;font-size:15px;color:#5B6472')}>{doc.sub} · 시행 {doc.updated}</p>
          </header>
          {doc.notice && <div style={css('background:#FAF1DF;border-radius:12px;padding:14px 18px;font-size:14.5px;line-height:1.5;color:#7A5410')}>{doc.notice}</div>}
          {doc.sections.map((s) => (
            <section key={s.h} style={css('display:flex;flex-direction:column;gap:10px')}>
              <h2 style={css('margin:0;font-size:17px;font-weight:700')}>{s.h}</h2>
              {s.p.map((t, i) => <p key={i} style={css('margin:0;font-size:15.5px;line-height:1.7;color:#3A4250')}>{t}</p>)}
            </section>
          ))}
          <nav style={css('display:flex;flex-wrap:wrap;gap:12px;padding-top:12px;border-top:1px solid #ECE8E2;font-size:14px;font-weight:600;color:#5B6472')}>
            {others.map((k) => <a key={k} className="lk" href={link(LEGAL_PATH[k])}>{LEGAL[k].title}</a>)}
          </nav>
        </article>
      </main>
    </Base>
  )
}
