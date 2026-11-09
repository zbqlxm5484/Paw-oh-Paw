// 앱 3D 보행 보기(/sessions/:id/3d). 웹 3D 보기(web/src/pages/Gait3d.tsx)와 같은 장면을 폰 화면에 맞춘 것:
// 위에 3D(손가락으로 돌리기·두 손가락으로 확대·다리를 누르면 수치), 아래에 걸음 방식·재생·보는 각도 버튼과 앞·뒷다리 요약.
// 웹에 있는 기준 회차 겹치기는 앱에서 뺐다(11-09 사용자 결정).
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import type { SessionResultOut } from '../../api/types'
import { legCards } from './AppReport'
import { mount, type Ctx, type Els } from './Gait3dMount'

const INK = '#1B2433', SUB = '#5B6472', LINE = '#ECE8E2', ORANGE = '#D2601A'
/** 시연 회차들의 관절별 가동 범위 중앙값(°). 웹 views.ts ROM_REF 값(11-09 계산) */
const ROM_REF: Record<string, number> = { 어깨: 33.2, 팔꿈치: 46.6, 앞발목: 49.5, 고관절: 28, 무릎: 46.1, 뒷발목: 40.3 }
const JOINT_CODES: Record<string, string> = { 어깨: 'rom_shoulder', 팔꿈치: 'rom_elbow', 앞발목: 'rom_carpus', 고관절: 'rom_hip', 무릎: 'rom_stifle', 뒷발목: 'rom_tarsus' }
const VIEWS: [string, string][] = [['left', '왼쪽'], ['right', '오른쪽'], ['back', '뒤'], ['front', '앞'], ['top', '위']]

/** 회차의 다리별 관절 가동 범위(°)·입각기 비율(%). 속보(TROT) 우선 */
function legNums(result: SessionResultOut | null | undefined) {
  const roms: Record<string, Record<string, number>> = {}
  const stance: Record<string, number | null> = {}
  const g = result?.gaits.find((x) => x.gait_type === 'TROT' && x.metrics.length) ?? result?.gaits.find((x) => x.metrics.length)
  if (!g) return { roms, stance }
  const val = (code: string, leg: string) => g.metrics.find((m) => m.metric_code === code && m.limb === leg && m.measurable)?.value ?? null
  for (const leg of ['LF', 'RF', 'LH', 'RH']) {
    roms[leg] = {}
    for (const [j, c] of Object.entries(JOINT_CODES)) { const v = val(c, leg); if (v) roms[leg][j] = v }
    stance[leg] = val('stance_ratio', leg)
  }
  return { roms, stance }
}

export interface Gait3dProps {
  result: SessionResultOut | null | undefined
  name: string
  when: string
  size: string
  sym: number | null
  back: () => void
}

export function Gait3dBody(p: Gait3dProps) {
  const lc = useMemo(() => legCards(p.result), [p.result])
  // 앱 화면은 자주 다시 그려지므로(타이머·알림) 원시 값에만 기대야 3D 장면을 다시 만들지 않는다
  const ctx = useMemo<Ctx | null>(() => {
    if (!p.result) return null
    const { roms, stance } = legNums(p.result)
    // 추천 보는 각도: 덜 쓰는 다리가 있는 쪽 옆(뒷다리 우선)
    const weakPart = lc.hind.si >= 5 ? lc.hind : lc.front.si >= 5 ? lc.front : null
    return {
      model_url: `/assets/dog3d/${p.size === 'L' ? 'husky' : 'shiba'}.glb`, legs: lc.cards, roms, stance, speed: 1, rom_ref: ROM_REF,
      overall: { sym: p.sym ?? 0, front: lc.front.say, hind: lc.hind.say },
      gait_url: '/assets/dog3d/gait_demo.json', gait_src: '', view_main: weakPart ? (weakPart.weak === 'l' ? 'left' : 'right') : 'left',
      ghost: null,
    }
  }, [p.result, p.size, p.sym, lc])

  const [loading, setLoading] = useState<string | null>('3D 모델을 불러오는 중…')
  const boxRef = useRef<HTMLDivElement>(null), tipRef = useRef<HTMLDivElement>(null)
  const realRef = useRef<HTMLButtonElement>(null), genRef = useRef<HTMLButtonElement>(null), walkRef = useRef<HTMLButtonElement>(null), stopRef = useRef<HTMLButtonElement>(null)
  const api: Els['api'] = useRef(null) as Els['api']
  useEffect(() => {
    if (!ctx || !boxRef.current) return
    return mount(ctx, { box: boxRef.current, tip: tipRef.current!, real: realRef.current!, gen: genRef.current!, walk: walkRef.current!, stop: stopRef.current!, setLoading, api })
  }, [ctx, api])

  const btn: CSSProperties = { height: 38, padding: '0 12px', borderRadius: 10, border: '1px solid #E2DCD3', background: '#fff', fontSize: 13.5, fontWeight: 700, color: INK, fontFamily: 'inherit', whiteSpace: 'nowrap' }
  const group: CSSProperties = { display: 'flex', gap: 6, padding: 4, borderRadius: 12, background: '#F1ECE5' }
  return (
    <div style={{ position: 'absolute', inset: 0, paddingTop: 36, display: 'flex', flexDirection: 'column' }}>
      <div style={{ flex: 'none', height: 56, display: 'flex', alignItems: 'center', gap: 4, padding: '0 8px' }}>
        <div onClick={p.back} style={{ width: 44, height: 44, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}><svg width="24" height="24" viewBox="0 0 24 24"><use href="#i-back"></use></svg></div>
        <b style={{ fontSize: 18 }}>3D 보기</b>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '0 16px 24px', display: 'flex', flexDirection: 'column', gap: 12 }} className="pp-s aw-col">
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8, padding: '0 4px' }}>
          <b style={{ fontSize: 20, letterSpacing: '-0.4px' }}>{p.name}</b><span style={{ fontSize: 13, color: SUB }}>{p.when}</span>
        </div>
        <div style={{ position: 'relative', height: 'min(56vh, 440px)', borderRadius: 18, overflow: 'hidden', border: `1px solid ${LINE}`, background: 'radial-gradient(ellipse at 50% 42%,#FFFFFF 0%,#FBF8F4 45%,#EFE8DE 100%)', touchAction: 'none' }}>
          <div ref={boxRef} style={{ position: 'absolute', inset: 0 }} />
          {loading !== null ? <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, color: '#7A808A', textAlign: 'center', padding: 20 }}>{!ctx ? '이 회차는 3D 로 볼 수치가 없습니다' : loading}</div> : null}
          <span style={{ position: 'absolute', left: 12, bottom: 10, fontSize: 11.5, color: '#8E949C', pointerEvents: 'none' }}>끌어서 돌리기 · 두 손가락으로 확대 · 다리를 누르면 수치</span>
          <div ref={tipRef} style={{ position: 'absolute', display: 'none', pointerEvents: 'none', minWidth: 190, padding: '10px 12px', borderRadius: 12, background: 'rgba(27,36,51,.94)', color: '#fff', fontSize: 12.5, lineHeight: 1.55, boxShadow: '0 8px 24px rgba(27,36,51,.25)' }} />
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <div style={group}>
            <button ref={realRef} type="button" onClick={() => api.current?.setMode('real')} style={btn}>측정 걸음</button>
            <button ref={genRef} type="button" onClick={() => api.current?.setMode('gen')} style={btn}>일반 걸음</button>
          </div>
          <div style={group}>
            <button ref={walkRef} type="button" onClick={() => api.current?.setWalking(true)} style={btn}>걷기</button>
            <button ref={stopRef} type="button" onClick={() => api.current?.setWalking(false)} style={btn}>멈춤</button>
          </div>
        </div>
        <div style={{ ...group, justifyContent: 'space-between' }}>
          {VIEWS.map(([k, label]) => <button key={k} type="button" onClick={() => api.current?.setView(k)} style={{ ...btn, flex: 1, padding: 0, border: `1px solid ${k === ctx?.view_main ? ORANGE : '#E2DCD3'}`, color: k === ctx?.view_main ? '#B4501A' : INK }}>{label}{k === ctx?.view_main ? ' ★' : ''}</button>)}
        </div>
        <div style={{ background: '#fff', border: `1px solid ${LINE}`, borderRadius: 16, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <span style={{ fontSize: 14 }}>좌우 대칭 지수 <b>{p.sym ?? '—'}%</b></span>
          {([['앞다리', lc.front], ['뒷다리', lc.hind]] as const).map(([label, P]) => (
            <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <span style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, fontWeight: 700 }}><span>{label}</span><span style={{ color: P.lv[3] }}>{P.lv[1]}</span></span>
              <span style={{ fontSize: 14, lineHeight: 1.5 }}>{P.say}</span>
            </div>
          ))}
          <span style={{ fontSize: 11.5, color: '#A0A7B2', lineHeight: 1.5 }}>측정 걸음은 이 회차의 관절 가동 범위·입각기 비율로 모델의 걷기 동작 폭을 맞춘 것입니다. 실제 영상의 움직임을 그대로 옮긴 것은 아닙니다.</span>
        </div>
      </div>
    </div>
  )
}
