// 홈 "오늘" 탭의 날짜 고르기(11-09 QA: 지난주 왔던 반려견을 날짜로 찾기). ◀ 날짜 ▶ 와, 날짜를 누르면 여는 달력.
// 디자인은 서비스와 같게: Pretendard(상속), 주황 #D2601A, 크림 바탕, 둥근 모서리. 기록이 있는 날은 점, 오늘 이후는 고를 수 없다.
import { useEffect, useRef, useState } from 'react'
import { css } from '../../app/css'

const ORANGE = '#D2601A', INK = '#1B2433', SUB = '#5B6472', LINE = '#E2DCD3'
const WEEK = ['일', '월', '화', '수', '목', '금', '토']
const pad = (n: number) => String(n).padStart(2, '0')
const iso = (y: number, m: number, d: number) => `${y}-${pad(m + 1)}-${pad(d)}`
const addDays = (s: string, n: number) => { const d = new Date(`${s}T00:00:00`); d.setDate(d.getDate() + n); return iso(d.getFullYear(), d.getMonth(), d.getDate()) }
/** "11월 9일 (일)" */
export const dayLabel = (s: string) => { const d = new Date(`${s}T00:00:00`); return `${d.getMonth() + 1}월 ${d.getDate()}일 (${WEEK[d.getDay()]})` }

export function DayPicker({ day, today, marks, go }: { day: string; today: string; marks: Set<string>; go: (d: string) => void }) {
  const [open, setOpen] = useState(false)
  const [ym, setYm] = useState(() => [Number(day.slice(0, 4)), Number(day.slice(5, 7)) - 1] as [number, number])
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const off = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', off); document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', off); document.removeEventListener('keydown', esc) }
  }, [open])
  const [y, m] = ym
  const first = new Date(y, m, 1).getDay(), days = new Date(y, m + 1, 0).getDate()
  const cells: (number | null)[] = [...Array(first).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)]
  const nextMonthDisabled = iso(y, m, 1) >= iso(Number(today.slice(0, 4)), Number(today.slice(5, 7)) - 1, 1)
  const pick = (d: string) => { setOpen(false); go(d) }
  const arrow: React.CSSProperties = { width: 44, height: 44, borderRadius: 10, border: `1px solid ${LINE}`, background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: INK, fontFamily: 'inherit' }
  return (
    <div ref={box} style={css('position:relative;display:flex;align-items:center;gap:6px')}>
      <button type="button" aria-label="전날" onClick={() => go(addDays(day, -1))} style={arrow}><svg width="16" height="16" viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg></button>
      <button type="button" onClick={() => { setYm([Number(day.slice(0, 4)), Number(day.slice(5, 7)) - 1]); setOpen(!open) }}
        style={{ height: 44, padding: '0 14px', borderRadius: 10, border: `1px solid ${open ? ORANGE : LINE}`, background: '#fff', display: 'flex', alignItems: 'center', gap: 8, fontSize: 15, fontWeight: 700, color: INK, cursor: 'pointer', fontFamily: 'inherit', fontVariantNumeric: 'tabular-nums' }}>
        <svg width="17" height="17" viewBox="0 0 24 24" style={{ color: ORANGE }}><rect x="3.5" y="5" width="17" height="15" rx="3" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M3.5 10h17M8 3v4M16 3v4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
        {dayLabel(day)}
      </button>
      <button type="button" aria-label="다음날" disabled={day >= today} onClick={() => go(addDays(day, 1))} style={{ ...arrow, opacity: day >= today ? 0.35 : 1, cursor: day >= today ? 'default' : 'pointer' }}><svg width="16" height="16" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg></button>
      {day !== today ? <button type="button" onClick={() => go(today)} style={{ height: 44, padding: '0 12px', borderRadius: 10, border: 'none', background: '#FCEEE3', color: '#B4501A', fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>오늘로</button> : null}
      {open ? (
        <div role="dialog" aria-label="날짜 고르기" style={css('position:absolute;top:46px;left:0;z-index:30;width:308px;padding:14px;border-radius:16px;background:#fff;border:1px solid #ECE8E2;box-shadow:0 14px 34px rgba(27,36,51,.14)')}>
          <div style={css('display:flex;align-items:center;justify-content:space-between;margin-bottom:8px')}>
            <button type="button" aria-label="이전 달" onClick={() => setYm(m ? [y, m - 1] : [y - 1, 11])} style={{ ...arrow, width: 32, height: 44, border: 'none' }}><svg width="16" height="16" viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg></button>
            <b style={css('font-size:15px;letter-spacing:-0.3px')}>{y}년 {m + 1}월</b>
            <button type="button" aria-label="다음 달" disabled={nextMonthDisabled} onClick={() => setYm(m === 11 ? [y + 1, 0] : [y, m + 1])} style={{ ...arrow, width: 32, height: 44, border: 'none', opacity: nextMonthDisabled ? 0.3 : 1 }}><svg width="16" height="16" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg></button>
          </div>
          <div style={css('display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center')}>
            {WEEK.map((w, i) => <span key={w} style={css(`font-size:12px;font-weight:600;padding:4px 0;color:${i === 0 ? '#C2412D' : SUB}`)}>{w}</span>)}
            {cells.map((n, i) => {
              if (n == null) return <span key={`e${i}`} />
              const d = iso(y, m, n), sel = d === day, isToday = d === today, future = d > today
              return (
                <button key={d} type="button" disabled={future} onClick={() => pick(d)}
                  style={{ height: 44, borderRadius: 10, border: isToday && !sel ? `1.5px solid ${ORANGE}` : '1.5px solid transparent', background: sel ? ORANGE : 'transparent', color: sel ? '#fff' : future ? '#C9CDD3' : (i % 7 === 0 ? '#C2412D' : INK), fontSize: 14, fontWeight: sel || isToday ? 700 : 500, cursor: future ? 'default' : 'pointer', fontFamily: 'inherit', position: 'relative', fontVariantNumeric: 'tabular-nums' }}>
                  {n}
                  {marks.has(d) ? <span style={{ position: 'absolute', left: '50%', bottom: 4, width: 4, height: 4, marginLeft: -2, borderRadius: 2, background: sel ? '#fff' : ORANGE }} /> : null}
                </button>
              )
            })}
          </div>
          <div style={css('display:flex;align-items:center;gap:6px;margin-top:10px;font-size:12px;color:#5B6472')}><span style={css(`width:5px;height:5px;border-radius:3px;background:${ORANGE}`)} />진료·측정 기록이 있는 날</div>
        </div>
      ) : null}
    </div>
  )
}
