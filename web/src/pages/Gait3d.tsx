// gait3d.html(+ <script type="module">) + main.py gait_3d(): 보호자 설명용 3D 보기.
// 돌려 보고, 걷는 모습을 재생하고(측정 걸음 · 일반 걸음), 덜 쓰는 다리를 색으로 표시하고, 다리에 마우스를 올리면 수치를 띄운다
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { mergeVertices } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import { Base } from '../app/Base'
import { css } from '../app/css'
import { staticUrl, usePage, useTitle } from '../app/page'
import { redirect, setToast, type Go } from '../app/session'
import { dogOf, resultOf } from '../store/db'
import type { Account, Result } from '../store/types'
import { session, source_name } from '../views/real'
import { best_view, body_map, MEDIAN_SPEED, result_view, ROM_REF } from '../views/views'

/** 서버의 RedirectResponse: 지금 주소를 바꿔 치운다 */
function useRedirect(g: Go | null) {
  const navigate = useNavigate()
  useEffect(() => {
    if (!g) return
    if (g.toast) setToast(g.toast)
    navigate(g.to, { replace: true })
  })
}

type Leg = { label: string; weak: boolean; c: string; dot: string; mets: { n: string; v: string; other: string; lower: boolean }[] }
type Ctx = {
  model_url: string
  legs: Record<string, Leg>
  roms: Record<string, Record<string, number>>
  stance: Record<string, number | null>
  speed: number
  rom_ref: Record<string, number>
  overall: { sym: number; front: string; hind: string }
  gait_url: string
  gait_src: string
  view_main: string
}

/** main.py gait_3d() 의 화면 준비 */
function prepare(acct: Account, r: Result) {
  const d = dogOf(acct, r.dog)
  const bm = body_map(acct, r)
  const legs: Record<string, Leg> = {}
  for (const [k, v] of Object.entries(bm.legs)) if (k.length === 2) legs[k] = v as unknown as Leg // LF·RF·LH·RH (front·hind 는 한 쌍 요약)
  const overall = { sym: bm.sym, front: bm.legs.front.say, hind: bm.legs.hind.say }
  const model = 'assets/dog3d/' + (d && d.size === 'L' ? 'husky.glb' : 'shiba.glb')
  // 이 회차에서 잰 다리별 관절 가동 범위: 3D 측정 걸음의 다리 뼈 배율(좌우 중 큰 쪽 대비)에 쓴다
  const codes: Record<string, string> = { 어깨: 'rom_shoulder', 팔꿈치: 'rom_elbow', 앞발목: 'rom_carpus', 고관절: 'rom_hip', 무릎: 'rom_stifle', 뒷발목: 'rom_tarsus' }
  const hasM = !!r.m && Object.keys(r.m).length > 0
  const roms: Record<string, Record<string, number>> = {}
  const stance: Record<string, number | null> = {}
  if (hasM) {
    for (const leg of ['LF', 'RF', 'LH', 'RH']) {
      const m = r.m[leg] || {}
      roms[leg] = {}
      for (const [j, c] of Object.entries(codes)) if (m[c]) roms[leg][j] = m[c]
      stance[leg] = m.stance_ratio ?? null
    }
  }
  const s = session(r.src)
  const speed = s && s.walk_speed ? Math.min(1.3, Math.max(0.7, s.walk_speed / MEDIAN_SPEED)) : 1 // 재생 빠르기(시연 회차 중앙값 대비)
  const view = best_view(bm)
  const ctx: Ctx = {
    model_url: staticUrl(model), legs, roms, stance, speed, rom_ref: ROM_REF, overall,
    gait_src: s
      ? `${source_name(s)} 회차 · 관절 가동 범위는 AI-Hub 71878 라벨 관절점, 입각기 비율은 공개 논문(PLOS ONE 2018) 실측 분포, 보행 속도는 합성`
      : '시연용 합성 수치(실제 개의 값이 아님)',
    // 측정 걸음: 시연용 한 걸음 곡선(tools/build_demo_clip.py, 공개 논문 + 합성). 회사 데이터는 쓰지 않는다
    gait_url: staticUrl('assets/dog3d/gait_demo.json'),
    view_main: view.main,
  }
  return { rd: result_view(acct, r).rd, bm, view, ctx }
}

const VIEWS: [string, string][] = [['left', '왼쪽 옆'], ['right', '오른쪽 옆'], ['back', '뒤'], ['front', '앞'], ['top', '위']]

export default function Gait3d() {
  const { rid = '' } = useParams()
  const { acct, me, toast } = usePage({ login: true })
  const r = acct ? resultOf(acct, rid) : undefined
  let go: Go | null = null
  if (acct && (!r || r.st === 'fail')) go = redirect(r ? `/results/${rid}` : '/results', '3D 로 볼 수 없는 회차예요')
  useRedirect(go)
  const [pv] = useState(() => (acct && r && !go ? prepare(acct, r) : null))
  useTitle(`${pv ? pv.rd.name : ''} 3D 보기 · Paw oh Paw`)
  const [loading, setLoading] = useState<string | null>('3D 모델을 불러오는 중…')
  const [gaitSrc, setGaitSrc] = useState('-')
  const viewRef = useRef<HTMLDivElement>(null)
  const tipRef = useRef<HTMLDivElement>(null)
  const realRef = useRef<HTMLButtonElement>(null)
  const genRef = useRef<HTMLButtonElement>(null)
  const walkRef = useRef<HTMLButtonElement>(null)
  const stopRef = useRef<HTMLButtonElement>(null)
  const api = useRef<{ setView: (k: string) => void; setMode: (m: string) => void; setWalking: (on: boolean) => void } | null>(null)

  useEffect(() => {
    if (!pv) return
    return mount(pv.ctx, {
      box: viewRef.current!, tip: tipRef.current!, real: realRef.current!, gen: genRef.current!, walk: walkRef.current!, stop: stopRef.current!,
      setLoading, setGaitSrc, api,
    })
  }, [pv])

  if (!acct || !r || go || !pv) return null
  const { rd, bm, view } = pv
  const setView = (k: string) => api.current?.setView(k)

  return (
    <Base acct={acct} me={me} nav="results" toast={toast}>
      <main style={css('max-width:1280px;margin:0 auto;padding:20px 32px 64px;display:flex;flex-direction:column;gap:16px')}>
        <div style={css('display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap')}>
          <a className="lk" href={`/results/${rd.id}`} style={css('display:flex;align-items:center;gap:4px;font-size:14px;font-weight:600;color:#5B6472')}><svg width="16" height="16" viewBox="0 0 24 24"><use href="#w-back"></use></svg>분석 결과</a>
          <span style={css('font-size:14px;color:#5B6472')}>{rd.when}</span>
        </div>
        <div style={css('display:flex;gap:18px;align-items:stretch;flex-wrap:wrap')}>
          <div style={css('flex:1 1 640px;min-width:0;position:relative;border-radius:18px;overflow:hidden;background:radial-gradient(ellipse at 50% 42%,#FFFFFF 0%,#FBF8F4 45%,#EFE8DE 100%);border:1px solid #ECE8E2;height:560px')}>
            <div id="view" ref={viewRef} style={css('position:absolute;inset:0')}></div>
            {loading !== null ? <div id="loading" style={css('position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:15px;color:#7A808A')}>{loading}</div> : null}
            <div style={css('position:absolute;left:14px;top:14px;display:flex;align-items:center;gap:4px;padding:4px;border-radius:12px;background:rgba(255,255,255,.9);border:1px solid #ECE8E2;box-shadow:0 4px 14px rgba(27,36,51,.08)')}>
              <button className="bt seg-mode" id="mode-real" ref={realRef} type="button" onClick={() => api.current?.setMode('real')} style={css('height:36px;padding:0 14px;border-radius:9px;border:1px solid #E2DCD3;background:#fff;font-size:14px;font-weight:700')}>측정 걸음</button>
              <button className="bt seg-mode" id="mode-gen" ref={genRef} type="button" onClick={() => api.current?.setMode('gen')} style={css('height:36px;padding:0 14px;border-radius:9px;border:1px solid #E2DCD3;background:#fff;font-size:14px;font-weight:700')}>일반 걸음</button>
              <span style={css('width:1px;height:22px;background:#E2DCD3;margin:0 4px')}></span>
              <button className="bt" id="walk" ref={walkRef} type="button" onClick={() => api.current?.setWalking(true)} style={css('height:36px;padding:0 18px;border-radius:9px;border:1px solid #E2DCD3;background:#fff;font-size:14px;font-weight:700')}>걷기</button>
              <button className="bt" id="stop" ref={stopRef} type="button" onClick={() => api.current?.setWalking(false)} style={css('height:36px;padding:0 18px;border-radius:9px;border:1px solid #D2601A;background:#D2601A;color:#fff;font-size:14px;font-weight:700')}>멈춤</button>
            </div>
            {/* 보는 각도: 추천 각도에 표시, 누르면 그 방향으로 카메라를 옮긴다 */}
            <div style={css('position:absolute;right:14px;top:14px;display:flex;align-items:center;gap:4px;padding:4px;border-radius:12px;background:rgba(255,255,255,.9);border:1px solid #ECE8E2;box-shadow:0 4px 14px rgba(27,36,51,.08)')}>
              {VIEWS.map(([k, label]) => (
                <button key={k} className="bt view-btn" type="button" data-view={k} onClick={() => setView(k)} style={css(`height:34px;padding:0 11px;border-radius:9px;border:1px solid ${k === view.main ? '#D2601A' : '#E2DCD3'};background:#fff;color:${k === view.main ? '#B4501A' : '#1B2433'};font-size:13px;font-weight:700`)}>{label}{k === view.main ? ' ★' : k === view.sub ? ' ☆' : ''}</button>
              ))}
            </div>
            <span style={css('position:absolute;left:14px;bottom:12px;font-size:12.5px;color:#8E949C')}>끌어서 돌리기 · 휠로 확대 · 다리에 마우스를 올리면 수치</span>
            <div id="tip" ref={tipRef} style={css('position:absolute;display:none;pointer-events:none;min-width:200px;padding:10px 12px;border-radius:12px;background:rgba(27,36,51,.94);color:#fff;font-size:13px;line-height:1.55;box-shadow:0 8px 24px rgba(27,36,51,.25)')}></div>
          </div>
          <aside style={css('flex:0 1 340px;display:flex;flex-direction:column;gap:14px')}>
            <div style={css('padding:18px;border-radius:16px;background:#fff;border:1px solid #ECE8E2;display:flex;flex-direction:column;gap:6px')}>
              <b style={css('font-size:22px')}>{rd.name}</b>
              <span style={css('font-size:14px;color:#5B6472')}>{rd.desc}</span>
              <span style={css('font-size:14px')}>좌우 대칭 지수 <b>{bm.sym}%</b></span>
            </div>
            <div style={css('padding:18px;border-radius:16px;background:#fff;border:1px solid #ECE8E2;display:flex;flex-direction:column;gap:10px')}>
              <div style={css('display:flex;flex-direction:column;gap:6px;padding:12px 14px;border-radius:12px;background:#FFF6EE;border:1px solid #F3DCC8')}>
                <b style={css('font-size:14px;color:#B4501A')}>★ {view.label}에서 보세요 <span style={css('font-weight:600;color:#8E949C')}>· 함께 보기 ☆ {view.sub_label}</span></b>
                <span style={css('font-size:13.5px;line-height:1.55;color:#3A4250')}>{view.why}</span>
                <span style={css('display:flex;gap:6px')}><button className="bt view-btn" type="button" data-view={view.main} onClick={() => setView(view.main)} style={css('height:32px;padding:0 12px;border-radius:8px;background:#D2601A;color:#fff;font-size:13px;font-weight:700')}>{view.label}으로 보기</button><button className="bt view-btn" type="button" data-view={view.sub} onClick={() => setView(view.sub)} style={css('height:32px;padding:0 12px;border-radius:8px;border:1px solid #E2DCD3;background:#fff;font-size:13px;font-weight:700')}>{view.sub_label}에서 보기</button></span>
              </div>
              {([['front', '앞다리'], ['hind', '뒷다리']] as const).map(([part, label]) => {
                const p = bm.legs[part]
                return <div key={part} style={css('display:flex;flex-direction:column;gap:3px')}><span style={css('display:flex;justify-content:space-between;font-size:13px;font-weight:700')}><span>{label}</span><span style={css(`color:${p.c}`)}>{p.level}</span></span><span style={css('font-size:14.5px;line-height:1.5')}>{p.say}</span></div>
              })}
              <span id="gait-note" style={css('font-size:12px;color:#8E949C;line-height:1.5')}>측정 걸음은 이 회차에서 잰 수치로 움직여요. 다리마다 관절 가동 범위만큼 굽히고(작을수록 덜 움직임), 입각기 비율만큼 땅을 딛고, 보행 속도에 맞춰 빠르기를 바꿔요. 일반 걸음은 모델에 들어 있는 기본 걷기 동작이에요.</span>
              <span style={css('font-size:12px;color:#8E949C;line-height:1.5')}>수치 출처: <span id="gait-src">{gaitSrc}</span></span>
            </div>
          </aside>
        </div>
      </main>
    </Base>
  )
}

// ── 3D (gait3d.html 의 <script type="module"> 그대로) ──

interface Els {
  box: HTMLDivElement
  tip: HTMLDivElement
  real: HTMLButtonElement
  gen: HTMLButtonElement
  walk: HTMLButtonElement
  stop: HTMLButtonElement
  setLoading: (s: string | null) => void
  setGaitSrc: (s: string) => void
  api: { current: { setView: (k: string) => void; setMode: (m: string) => void; setWalking: (on: boolean) => void } | null }
}
type GaitClip = { legs: Record<string, { joint: Record<string, number[]> }> }
type GB = { b: THREE.Object3D; joint: string; q0: THREE.Quaternion; dqs: THREE.Quaternion[]; scale: number }

/** 장면을 만들고 정리 함수를 돌려준다 */
function mount(ctx: Ctx, el: Els): () => void {
  const MODEL = ctx.model_url
  const LEGS = ctx.legs
  const ROMS = ctx.roms
  const STANCE = ctx.stance // 이 회차 다리별 입각기 비율(%). 디딤 구간 길이를 다리마다 바꾼다
  const SPEED = ctx.speed // 재생 빠르기(시연 회차 보행 속도 중앙값 대비, 0.7~1.3)
  const ROM_REF_ = ctx.rom_ref // 관절별 기준 가동 범위(°). 두 다리 모두 이보다 작으면 둘 다 덜 움직인다
  const MODEL_STANCE = 0.6 // 모델 걷기 동작의 디딤 비율 가정
  const OVERALL = ctx.overall
  const GAIT_URL = ctx.gait_url
  // 측정 걸음: 모양은 모델 걷기 동작, 다리 뼈마다 움직임 폭을 실측 관절 굽힘 폭(좌우 평균 대비)에 맞춘다.
  // 이 모델 뼈대는 실제 개 다리 마디와 1:1 이 아니라 실측 각도로 뼈를 직접 돌리면 발이 꺾이거나 끌린다(10-29 확인)
  // [뼈 이름, 폭을 가져올 관절(engine/angles.py 이름)]
  const GAIT_BONES: Record<string, [string, string][]> = {
    LF: [['FrontShoulder.L', '어깨'], ['FrontUpperLeg.L', '팔꿈치'], ['FrontLowerLeg.L', '앞발목']],
    RF: [['FrontShoulder.R', '어깨'], ['FrontUpperLeg.R', '팔꿈치'], ['FrontLowerLeg.R', '앞발목']],
    LH: [['BackShoulder.L', '고관절'], ['BackLeg.L', '고관절'], ['BackUpperLeg.L', '무릎'], ['BackLowerLeg.L', '뒷발목']],
    RH: [['BackShoulder.R', '고관절'], ['BackLeg.R', '고관절'], ['BackUpperLeg.R', '무릎'], ['BackLowerLeg.R', '뒷발목']],
  }
  const N_WALK = 48 // 걷기 동작을 미리 뽑아 두는 칸 수
  // 다리마다 움직이는 뼈(Quaternius 동물 뼈대). three.js 는 이름의 '.' 을 지운다
  const LEG_BONES: Record<string, string[]> = {
    LF: ['FrontShoulder.L', 'FrontUpperLeg.L', 'FrontLowerLeg.L'], RF: ['FrontShoulder.R', 'FrontUpperLeg.R', 'FrontLowerLeg.R'],
    LH: ['BackShoulder.L', 'BackLeg.L', 'BackUpperLeg.L', 'BackLowerLeg.L'], RH: ['BackShoulder.R', 'BackLeg.R', 'BackUpperLeg.R', 'BackLowerLeg.R'],
  }
  const CODES = ['', 'LF', 'RF', 'LH', 'RH']
  const HOVER = new THREE.Color('#FFD27A')
  const clean = (s: string) => s.replace(/[.[\]:/]/g, '')
  // 칠한 꼭짓점(흰색이 아닌 곳)은 털 색과 곱하지 않고 표시 색으로 덮는다
  const COLOR_GLSL = [
    '#ifdef USE_COLOR',
    '  if (vColor.r + vColor.g + vColor.b < 2.99) diffuseColor.rgb = mix(diffuseColor.rgb, vColor, 0.9);',
    '#endif',
  ].join('\n')

  let dead = false
  const box = el.box, tip = el.tip
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }) // 배경은 CSS 그라데이션
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.setSize(box.clientWidth, box.clientHeight)
  renderer.setClearColor(0x000000, 0)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  box.appendChild(renderer.domElement)
  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(35, box.clientWidth / box.clientHeight, 0.01, 100)
  scene.add(new THREE.HemisphereLight(0xffffff, 0xd8cfc2, 2.2))
  const sun = new THREE.DirectionalLight(0xffffff, 1.6)
  sun.position.set(1.5, 4, 2)
  sun.castShadow = true
  sun.shadow.mapSize.set(1024, 1024)
  sun.shadow.radius = 6
  Object.assign(sun.shadow.camera, { left: -1.5, right: 1.5, top: 1.5, bottom: -1.5 })
  scene.add(sun)
  // 바닥판 대신 발밑 그림자만 보이는 투명 면
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(6, 6), new THREE.ShadowMaterial({ opacity: 0.16 }))
  ground.receiveShadow = true
  ground.rotation.x = -Math.PI / 2
  scene.add(ground)
  const controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  camera.position.set(-1.9, 1.1, 2.3)
  controls.target.set(0, 0.42, 0)
  controls.update()

  let mixer: THREE.AnimationMixer | undefined
  let walkAction: THREE.AnimationAction | undefined
  const meshes: { o: THREE.SkinnedMesh; leg: Uint8Array }[] = []
  let hovered = ''
  let VIEW_DIR: Record<string, THREE.Vector3> | null = null
  // 보는 각도: 정한 방향에서 몸 높이 조금 위로. 위 = 바로 위에서 내려다봄
  function setView(k: string) {
    const t = new THREE.Vector3(0, 0.42, 0)
    if (k === 'top') camera.position.set(0.001, 3.2, 0.001)
    else if (VIEW_DIR && VIEW_DIR[k]) camera.position.copy(t).addScaledVector(VIEW_DIR[k], 2.9).setY(0.75)
    controls.target.copy(t)
    controls.update()
  }
  let gait: GaitClip | null = null, mode = 'gen', phase = 0
  const gaitBones: Record<string, (GB | null)[]> = {}
  const side = new THREE.Vector3(1, 0, 0), dq = new THREE.Quaternion()
  new GLTFLoader().load(MODEL, (gltf) => {
    if (dead) return
    const model = gltf.scene
    // 크기·위치 맞추기: 몸 길이 1.4, 바닥에 붙이기. 뼈대 모델은 뼈 변형까지 넣어 재야(precise) 실제 크기가 나온다
    model.updateMatrixWorld(true)
    const b = new THREE.Box3().setFromObject(model, true), size = b.getSize(new THREE.Vector3())
    model.scale.multiplyScalar(1.4 / Math.max(size.x, size.z))
    model.updateMatrixWorld(true)
    const b2 = new THREE.Box3().setFromObject(model, true), c = b2.getCenter(new THREE.Vector3())
    model.position.sub(new THREE.Vector3(c.x, b2.min.y, c.z))
    scene.add(model)
    // 몸 방향 재기: 앞다리 - 뒷다리 = 앞, 오른 다리 - 왼 다리 = 오른쪽 → 보기 버튼의 카메라 위치
    const at = (nm: string) => { const o = model.getObjectByName(clean(nm)); return o ? o.getWorldPosition(new THREE.Vector3()) : null }
    const avg = (names: string[]) => { const ps = names.map(at).filter((p): p is THREE.Vector3 => !!p); return ps.reduce((s, p) => s.add(p), new THREE.Vector3()).multiplyScalar(1 / Math.max(1, ps.length)) }
    const fwd = avg(['FrontShoulder.L', 'FrontShoulder.R']).sub(avg(['BackShoulder.L', 'BackShoulder.R'])).setY(0).normalize()
    const right = avg(['FrontShoulder.R', 'BackShoulder.R']).sub(avg(['FrontShoulder.L', 'BackShoulder.L'])).setY(0).normalize()
    if (fwd.lengthSq() > 0.5 && right.lengthSq() > 0.5) VIEW_DIR = { left: right.clone().negate(), right, back: fwd.clone().negate(), front: fwd }
    setView(ctx.view_main)

    // 꼭짓점마다 어느 다리에 붙었는지(뼈 가중치 합 0.5 넘는 다리) 미리 정해 둔다 → 색칠·마우스 판별에 쓴다
    model.traverse((obj) => {
      const o = obj as THREE.SkinnedMesh
      if (!o.isSkinnedMesh) return
      o.castShadow = true
      const bones = o.skeleton.bones.map((x) => clean(x.name))
      const legOf: Record<number, number> = {}
      for (const [code, names] of Object.entries(LEG_BONES)) names.forEach((nm) => { const i = bones.indexOf(clean(nm)); if (i >= 0) legOf[i] = CODES.indexOf(code) })
      o.geometry = mergeVertices(o.geometry.deleteAttribute('normal'), 1e-4)
      o.geometry.computeVertexNormals()
      const g = o.geometry, si = g.attributes.skinIndex as THREE.BufferAttribute, sw = g.attributes.skinWeight as THREE.BufferAttribute, n = si.count
      const leg = new Uint8Array(n)
      for (let v = 0; v < n; v++) {
        const w = [0, 0, 0, 0, 0]
        for (let k = 0; k < 4; k++) { const l = legOf[si.getComponent(v, k)]; if (l) w[l] += sw.getComponent(v, k) }
        const best = w.indexOf(Math.max(...w))
        if (w[best] > 0.5) leg[v] = best
      }
      g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(n * 3).fill(1), 3))
      meshes.push({ o, leg })
      // 보고서 그림처럼 크림색 한 가지, 매끈한 면으로 다시 칠한다(눈만 어둡게)
      const mats = (Array.isArray(o.material) ? o.material : [o.material]).map((m) => {
        const dark = /eye|pupil/i.test(m.name || '') // 눈만 어둡게(털 무늬 재질은 이름으로만 가른다)
        const nm = new THREE.MeshStandardMaterial({ color: dark ? 0x3A3A3A : 0xE9E4DC, roughness: 0.85, metalness: 0, vertexColors: true })
        nm.onBeforeCompile = (sh) => { sh.fragmentShader = sh.fragmentShader.replace('#include <color_fragment>', COLOR_GLSL) }
        return nm
      })
      o.material = Array.isArray(o.material) ? mats : mats[0]
    })
    paint()

    model.updateMatrixWorld(true)
    const head = model.getObjectByName('Head'), tail = model.getObjectByName('Tail1')
    if (head && tail) {
      const fwd = head.getWorldPosition(new THREE.Vector3()).sub(tail.getWorldPosition(new THREE.Vector3()))
      fwd.y = 0
      side.crossVectors(fwd.normalize(), new THREE.Vector3(0, 1, 0)).normalize() // 앞 × 위 = 이 축으로 + 돌리면 앞이 위로
    }

    mixer = new THREE.AnimationMixer(model)
    const walk = gltf.animations.find((a) => a.name.split('|').pop() === 'Walk')
    if (walk) { walkAction = mixer.clipAction(walk); walkAction.play() }
    // 다리 뼈마다 걷기 한 주기의 회전을 N_WALK 칸 뽑고 평균 회전(q0)을 구한다. 측정 걸음은 평균에서 벗어난 만큼을 늘이거나 줄인다
    if (walk) {
      const acc: Record<string, { b: THREE.Object3D; joint: string; qs: THREE.Quaternion[]; sum: THREE.Vector4 }> = {}
      for (let k = 0; k < N_WALK; k++) {
        mixer.setTime((k / N_WALK) * walk.duration)
        for (const [code, bones] of Object.entries(GAIT_BONES)) bones.forEach(([nm, joint], i) => {
          const b = model.getObjectByName(clean(nm))
          if (!b) return
          const a = (acc[code + i] ||= { b, joint, qs: [], sum: new THREE.Vector4() })
          const q = b.quaternion, s = a.sum.x * q.x + a.sum.y * q.y + a.sum.z * q.z + a.sum.w * q.w < 0 ? -1 : 1 // 같은 반구로 맞춰 더한다
          a.sum.x += s * q.x; a.sum.y += s * q.y; a.sum.z += s * q.z; a.sum.w += s * q.w
          a.qs.push(q.clone())
        })
      }
      for (const [code, bones] of Object.entries(GAIT_BONES)) {
        gaitBones[code] = bones.map((_, i) => {
          const a = acc[code + i]
          if (!a) return null
          const q0 = new THREE.Quaternion(a.sum.x, a.sum.y, a.sum.z, a.sum.w).normalize(), inv = q0.clone().invert()
          return { b: a.b, joint: a.joint, q0, dqs: a.qs.map((q) => q.clone().multiply(inv)), scale: 1 } // q = dq · q0
        })
      }
    }
    fetch(GAIT_URL).then((r) => (r.ok ? r.json() : null)).then((g: GaitClip | null) => {
      if (dead) return
      if (g) {
        gait = g
        // 다리별 관절 가동 범위 ÷ max(기준 가동 범위, 같은 관절 좌우 중 큰 쪽) = 그 다리 뼈의 움직임 배율.
        // 수치가 기준 이상이면 1(모델 걷기 동작 그대로), 작을수록 줄인다. 1 을 넘기면 회전을 늘려 그려 발이 꺾여 보인다(11-02)
        const amp = (code: string, j: string): number | null => {
          if (ROMS[code] && ROMS[code][j]) return ROMS[code][j] // 이 회차 실측 가동 범위
          const c = g.legs[code] && g.legs[code].joint[j]; return c ? Math.max(...c) - Math.min(...c) : null // 없으면 시연 곡선
        }
        for (const [code, bones] of Object.entries(gaitBones)) bones.forEach((x) => {
          if (!x) return
          const mine = amp(code, x.joint), pair = [amp('L' + code[1], x.joint), amp('R' + code[1], x.joint)].filter((v): v is number => !!v)
          if (mine && pair.length) x.scale = Math.min(1, Math.max(0.12, mine / Math.max(ROM_REF_[x.joint] || 0, ...pair)))
        })
        el.setGaitSrc(ctx.gait_src)
      }
      setMode(gait ? 'real' : 'gen')
    }).catch(() => { if (!dead) setMode('gen') })
    setWalking(false)
    el.setLoading(null)
  }, undefined, () => { if (!dead) el.setLoading('3D 모델을 불러오지 못했어요 (인터넷 연결 확인)') })

  // 덜 쓰는 다리는 표시 색, 마우스를 올린 다리는 노란색
  function paint() {
    meshes.forEach(({ o, leg }) => {
      const attr = o.geometry.attributes.color as THREE.BufferAttribute
      const arr = attr.array as Float32Array
      for (let v = 0; v < leg.length; v++) {
        const code = CODES[leg[v]]
        let col: THREE.Color | null = null
        if (code && code === hovered) col = HOVER
        else if (code && LEGS[code] && LEGS[code].weak) col = new THREE.Color(LEGS[code].dot)
        arr[v * 3] = col ? col.r : 1; arr[v * 3 + 1] = col ? col.g : 1; arr[v * 3 + 2] = col ? col.b : 1
      }
      attr.needsUpdate = true
    })
  }

  // 마우스 아래 표면이 어느 다리인지 보고 그 다리 수치를 띄운다. 몸통·머리면 전체 대칭 지수
  const ray = new THREE.Raycaster(), mouse = new THREE.Vector2()
  function legTip(code: string) {
    const L = LEGS[code]
    const rows = L.mets.map((m) => '<div style="display:flex;justify-content:space-between;gap:14px"><span style="color:#C9CFD8">' + m.n
      + '</span><span><b style="color:' + (m.lower && L.weak ? '#FFB199' : '#fff') + '">' + m.v + '</b> <span style="color:#8E949C">/ 반대 '
      + m.other + '</span></span></div>').join('')
    return '<b style="font-size:14px">' + L.label + (L.weak ? ' · 덜 써요' : '') + '</b>' + rows
  }
  function bodyTip() {
    return '<b style="font-size:14px">몸 전체</b><div>좌우 대칭 지수 <b>' + OVERALL.sym + '%</b></div><div style="color:#C9CFD8">'
      + OVERALL.front + '</div><div style="color:#C9CFD8">' + OVERALL.hind + '</div>'
  }
  const onMove = (e: PointerEvent) => {
    const r = renderer.domElement.getBoundingClientRect()
    mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
    ray.setFromCamera(mouse, camera)
    let code = '', hit: THREE.Intersection | null = null
    for (const { o, leg } of meshes) {
      const h = ray.intersectObject(o, false)[0]
      if (h && (!hit || h.distance < hit.distance)) { hit = h; code = CODES[leg[h.face!.a]] || CODES[leg[h.face!.b]] || '' }
    }
    if (code !== hovered) { hovered = code; paint() }
    if (!hit) { tip.style.display = 'none'; return }
    tip.innerHTML = code ? legTip(code) : bodyTip()
    tip.style.display = 'block'
    tip.style.left = Math.min(e.clientX - r.left + 16, r.width - 230) + 'px'
    tip.style.top = Math.max(e.clientY - r.top - 10, 8) + 'px'
  }
  const onLeave = () => { tip.style.display = 'none'; if (hovered) { hovered = ''; paint() } }
  renderer.domElement.addEventListener('pointermove', onMove)
  renderer.domElement.addEventListener('pointerleave', onLeave)

  function mark(b: HTMLElement, act: boolean) {
    b.style.background = act ? '#D2601A' : '#fff'; b.style.color = act ? '#fff' : '#1B2433'; b.style.borderColor = act ? '#D2601A' : '#E2DCD3'
  }
  // 처음엔 멈춤(첫 자세에 서 있음)
  function setWalking(on: boolean) {
    walking = on
    if (mixer) mixer.timeScale = on ? 1 : 0
    mark(el.walk, on); mark(el.stop, !on)
  }
  let walking = false
  // 측정 걸음 = 실제 영상에서 잰 한 걸음 곡선으로 다리 뼈를 돌림, 일반 걸음 = 모델에 든 Walk 동작
  function setMode(m: string) {
    mode = m
    if (m === 'real') syncBody()
    mark(el.real, m === 'real'); mark(el.gen, m === 'gen')
    el.real.disabled = !gait
  }
  el.api.current = { setView, setMode, setWalking }

  // 측정 걸음: 몸·다리 모두 걷기 동작을 실제 한 걸음 박자로 재생하고, 다리 뼈는 평균에서 벗어나는 폭만 실측 배율로 바꾼다
  function syncBody() {
    if (walkAction && mixer) { walkAction.time = (((phase % 1) + 1) % 1) * walkAction.getClip().duration; mixer.update(0) }
    applyGait()
  }
  const ID = new THREE.Quaternion(), qa = new THREE.Quaternion()
  function applyGait() {
    if (!gait) return
    const p = ((phase % 1) + 1) % 1
    for (const [code, bones] of Object.entries(gaitBones)) bones.forEach((x) => {
      if (!x) return
      // 이 다리의 입각기 비율만큼 디딤 구간을 늘리거나 줄여 모델 동작의 걸음 위치로 바꾼다
      const st = STANCE[code]
      const b = st ? Math.min(0.8, Math.max(0.35, st / 100)) : MODEL_STANCE
      const q = p < b ? p / b * MODEL_STANCE : MODEL_STANCE + (p - b) / (1 - b) * (1 - MODEL_STANCE)
      const x0 = q * N_WALK, k = Math.floor(x0) % N_WALK, f = x0 - Math.floor(x0)
      qa.slerpQuaternions(x.dqs[k], x.dqs[(k + 1) % N_WALK], f) // 이 순간 걷기 동작의 평균 대비 회전
      dq.slerpQuaternions(ID, qa, x.scale) // 실측 배율만큼 줄임(0~1, 늘리지는 않는다)
      x.b.quaternion.copy(dq).multiply(x.q0)
    })
  }

  const clock = new THREE.Clock()
  renderer.setAnimationLoop(() => {
    const dt = clock.getDelta()
    if (mode === 'gen') { if (mixer) mixer.update(dt) }
    else if (gait) {
      if (walking) phase += dt * SPEED / (walkAction ? walkAction.getClip().duration : 1) // 일반 걸음 속도 × 이 회차 빠르기(실측 속도 그대로는 너무 빨라 차이가 안 보인다)
      syncBody()
    }
    controls.update(); renderer.render(scene, camera)
  })
  const onResize = () => { renderer.setSize(box.clientWidth, box.clientHeight); camera.aspect = box.clientWidth / box.clientHeight; camera.updateProjectionMatrix() }
  window.addEventListener('resize', onResize)

  // 화면을 떠나면 정리(시제품은 페이지가 통째로 바뀌어 필요 없었다)
  return () => {
    dead = true
    el.api.current = null
    window.removeEventListener('resize', onResize)
    renderer.domElement.removeEventListener('pointermove', onMove)
    renderer.domElement.removeEventListener('pointerleave', onLeave)
    renderer.setAnimationLoop(null)
    controls.dispose()
    renderer.dispose()
    renderer.domElement.remove()
  }
}
