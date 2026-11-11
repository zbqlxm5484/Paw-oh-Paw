// _dogpanel.html: 메모 = 환자에 붙는 짧은 특이사항. 차트 위 고정 줄과 분석 결과 오른쪽 칸에서 같은 모양으로 바로 쓴다(인쇄에서는 빠짐).
import { css } from '../../app/css'
import { PostForm } from '../../app/page'
import { VV } from './Vital'
import { link } from '../../config'

/** views.memos 한 줄 */
export interface MemoX {
  id: string
  cat: string
  bg: string
  c: string
  text: string
  imp: boolean
  at: string
  author: string
  revs: { at: string; author: string; text: string }[]
}

const tone: Record<string, [string, string]> = { surg: ['#FCEEE3', '#A8481A'], diag: ['#EEF1F6', '#4A5A78'], warn: ['#FAF1DF', '#9A6A12'] }

/** 메모 한 장: 분류 색 태그, 2줄까지, 아래에 날짜·작성자. edit_url 이 있으면 눌러서 고친다 */
export function MemoCard({ x, edit_url = '' }: { x: MemoX; edit_url?: string }) {
  return (
    <a className="lk memo-card" href={link(edit_url && x.id ? `${edit_url}${x.id}` : undefined)} title={x.text}>
      <span className="memo-text">{x.imp ? <><b style={css('color:#C2412D')}>●</b>{' '}</> : null}{x.text}</span>
      <span className="memo-foot"><b style={css(`padding:1px 7px;border-radius:6px;background:${x.bg};color:${x.c}`)}>{x.cat}</b>{x.at ? <span>{x.at}{x.author ? ` · ${x.author.split(' ')[0]}` : ''}</span> : null}</span>
    </a>
  )
}

/** 메모 쓰기·고치기. edit 이 메모면 그 내용으로 열린다 */
export function MemoForm({ dog_id, next_url, memo_cat, edit = null, open = false }: {
  dog_id: string
  next_url: string
  memo_cat: Record<string, [string, string]>
  edit?: MemoX | null
  open?: boolean
}) {
  return (
    <details className="memo-add" open={!!(edit || open)}>
      <summary>{edit ? '메모 고치기' : '+ 메모'}</summary>
      <PostForm action={`/dogs/${dog_id}/notes`} style={css('display:flex;flex-direction:column;gap:8px;margin:0')}>
        <input type="hidden" name="next_url" value={next_url} />
        <input type="hidden" className="author-inp" name="author" defaultValue="" />
        {edit ? <input type="hidden" name="note_id" value={edit.id} /> : null}
        {!edit ? (
          <div style={css('display:flex;gap:6px;flex-wrap:wrap')}>
            {Object.entries(memo_cat).map(([k, [bg, c]], i) => <label key={k} className="memo-chip" style={css(`--bg:${bg};--c:${c}`)}><input type="radio" name="cat" value={k} defaultChecked={i === 0} />{k}</label>)}
          </div>
        ) : null}
        <textarea className="inp" name="text" rows={2} placeholder="예) 입질 있음, 입마개 착용 후 촬영" style={css('border-radius:10px;border:1px solid #E2DCD3;padding:9px 11px;font-size:14px;line-height:1.5;font-family:inherit;outline:none;resize:vertical;width:100%')} defaultValue={edit ? edit.text : ''}></textarea>
        <div style={css('display:flex;align-items:center;justify-content:space-between;gap:10px')}>
          {!edit ? <label style={css('display:flex;align-items:center;gap:6px;font-size:13px;color:#3A4250;cursor:pointer')}><input type="checkbox" name="important" value="1" /> 중요 (홈 목록에 표시)</label> : <a className="lk" href={link(next_url)} style={css('font-size:13px;color:#7A808A')}>취소</a>}
          <button className="bt" type="submit" style={css('height:34px;padding:0 14px;border-radius:9px;background:#1B2433;color:#fff;font-size:13.5px;font-weight:700')}>{edit ? '저장' : '남기기'}</button>
        </div>
        {edit && edit.revs && edit.revs.length ? <details style={css('font-size:12.5px;color:#7A808A')}><summary style={css('cursor:pointer')}>고친 이력 {edit.revs.length}건</summary>{[...edit.revs].reverse().map((r, i) => <div key={i} style={css('padding:4px 0 0 10px;border-left:2px solid #ECE8E2;margin-top:4px')}>{r.at} · {r.author}<div style={css('text-decoration:line-through')}>{r.text}</div></div>)}</details> : null}
      </PostForm>
      {edit ? (
        <PostForm action={`/dogs/${dog_id}/notes`} style={css('display:flex;justify-content:flex-end;margin:6px 0 0')} onBefore={() => window.confirm('이 메모를 지울까요? 고친 이력도 함께 지워지고 되돌릴 수 없습니다.')}>
          <input type="hidden" name="note_id" value={edit.id} />
          <input type="hidden" name="delete" value="1" />
          <input type="hidden" name="next_url" value={next_url} />
          <button className="bt" type="submit" style={css('background:none;font-size:13px;font-weight:600;color:#B4501A;padding:0')}>메모 지우기</button>
        </PostForm>
      ) : null}
    </details>
  )
}

/** 분석 결과 화면 오른쪽 칸(views.memo_panel): 누구인지, 메모(바로 쓰기), 이 회차 진료 기록 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function DogPanel({ panel, next_url }: { panel: any; next_url: string }) {
  const memos: MemoX[] = panel.memos || []
  const badges: { t: string; full?: string; kind: string }[] = panel.badges || []
  const run_soap: { at: string; author: string; parts: { cat: string; text: string }[] }[] = panel.run_soap || []
  return (
    <aside className="no-print" style={css('width:340px;flex:none;position:sticky;top:96px;border-radius:18px;background:#fff;border:1px solid #ECE8E2;padding:18px;display:flex;flex-direction:column;gap:14px;max-height:calc(100vh - 120px);overflow-y:auto')}>
      <div style={css('display:flex;flex-direction:column;gap:2px')}>
        <span style={css('font-size:12.5px;color:#8E949C')}>{panel.no}</span>
        <b style={css('font-size:20px')}>{panel.name} <span style={css(`padding:2px 8px;border-radius:7px;background:${panel.st_bg};color:${panel.st_c};font-size:12px;vertical-align:3px`)}>{panel.stage}</span></b>
        <span style={css('font-size:13.5px;color:#3A4250')}>{panel.breed} · {panel.size} · {panel.age} · {panel.sex}</span>
      </div>
      <div style={css('display:grid;grid-template-columns:repeat(4,auto);justify-content:space-between;row-gap:2px;font-variant-numeric:tabular-nums')}>
        {['체중', '체온', '심박', '혈압'].map((k) => <span key={k} style={css('font-size:11.5px;color:#8E949C')}>{k}</span>)}
        {['kg', 'temp', 'hr', 'bp'].map((key) => <VV key={key} value={panel.v[key]} f={panel.v.f[key]} size={15} />)}
      </div>
      {badges.length ? <div style={css('display:flex;flex-wrap:wrap;gap:5px')}>{badges.map((b, i) => <span key={i} style={css(`padding:4px 9px;border-radius:8px;background:${tone[b.kind][0]};color:${tone[b.kind][1]};font-size:12.5px;font-weight:700`)}>{b.full || b.t}</span>)}</div> : null}

      <div className="memo-col" style={css('display:flex;flex-direction:column;gap:8px;padding-top:12px;border-top:1px solid #F2EFEA')}>
        <b style={css('font-size:14px')}>메모 <span style={css('color:#8E949C;font-weight:600')}>{memos.length}</span></b>
        <MemoForm dog_id={panel.id} next_url={next_url} memo_cat={panel.memo_cat} />
        {memos.map((x, i) => <MemoCard key={x.id || `m${i}`} x={x} />)}
        {!memos.length ? <span style={css('font-size:13.5px;color:#A0A7B2')}>메모가 없습니다.</span> : null}
      </div>
      {panel.rid ? (
        <div style={css('display:flex;flex-direction:column;gap:8px;padding-top:12px;border-top:1px solid #F2EFEA')}>
          <b style={css('font-size:14px')}>이 회차 진료 기록</b>
          {run_soap.map((g, i) => (
            <div key={i} style={css('display:flex;flex-direction:column;gap:4px;padding:10px 12px;border-radius:12px;background:#FAF8F5')}>
              <span style={css('font-size:12px;color:#8E949C')}>{g.at}{g.author ? ` · ${g.author}` : ''}</span>
              {g.parts.map((n, j) => <span key={j} style={css('display:grid;grid-template-columns:18px 1fr;gap:6px;font-size:13.5px;line-height:1.5')}><b style={css('color:#8E949C')}>{n.cat}</b><span style={css('white-space:pre-line')}>{n.text}</span></span>)}
            </div>
          ))}
          {!run_soap.length ? <span style={css('font-size:13.5px;color:#A0A7B2')}>이 회차에 남긴 진료 기록이 없습니다.</span> : null}
        </div>
      ) : null}
      <a className="lk" href={link(`/dogs/${panel.id}`)} style={css('height:42px;border-radius:10px;border:1px solid #E2DCD3;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700')}>반려견 차트 (분석 {panel.n_res})</a>
    </aside>
  )
}
