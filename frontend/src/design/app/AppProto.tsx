/* eslint-disable */
/**
 * Paw oh Paw 앱 v5 로직. 디자인 프로토타입 로직 원본을 바탕으로 목업 대신 API 데이터(props.data)를 쓰고,
 * 화면 이동은 주소(props.screen·nav·back)로 한다. 문구·색·배치 값은 원본 그대로.
 * 촬영: 디자인의 촬영 화면에서 촬영 버튼을 누르면 기기 카메라(파일 입력 capture)가 열린다.
 */
import * as camera from '../../app/camera'
import { ApiError } from '../../api/client'
import { BREEDS } from '../../api/labels'
import { DCLogic } from '../DCLogic'
import { ST, STEPS, type DDog, type DGait, type DRes } from '../adapter'
import type { ProtoProps } from '../DesignRoot'
import { EMPTY_PET, LIMB, LINES, PREP, SEX, SIZE, autoSize, baseOf as baseOf_, chk, desc, errMsg, fmtD, knee, petBody, pickSt, resultVals, seg, sessNo as sessNo_, short, valid as valid_ } from '../shared'
import { AppView } from './AppView'
import './app-view.css'

/** 409 DOG_MODIFIED: 다른 담당자가 먼저 고쳤다. 목록은 다시 불러온 상태다(useDesignActions.updateDog) */
const DOG_MODIFIED_MSG = '다른 담당자가 먼저 수정했어요. 최신 내용을 다시 불러왔으니 확인한 뒤 다시 저장해 주세요'

type Props = ProtoProps & { rootStyle?: React.CSSProperties }

export class AppProto extends DCLogic<Props, any> {
  static View = AppView
  state: any = {
    splash: false, joint: false, line: 0, sheet: null, toast: '', viaTab: true,
    li: { id: '', pw: '' }, so: { org: '', loc: '', dev: '', id: '', pw: '', pw2: '' }, to: [false, false, false, false],
    af: { name: '', email: '' }, pf: { cur: '', nw: '', nw2: '' }, saving: false,
    pet: EMPTY_PET, petMode: 'new', petId: null, delId: null, q: '',
    capDog: '', sessW: '', busy: false, repType: 'g', gait: 'trot', page: 0, filt: 'all', notifOn: true, rotDone: false, rotAnim: false, repH: 0, camLive: false, recSec: -1, camLoading: false, pend: 0, loginBusy: false,
  }
  vids = new Set<HTMLVideoElement>()
  recTick: any; raf: any; t1: any; t2: any; tt: any; r1: any; r2: any; storyEl?: HTMLElement; lastMo = 0; moStart = 0
  componentDidMount() {
    // 로그인 전 첫 진입이면 스플래시(2.2초) 뒤 랜딩
    if (!this.props.data.loggedIn && (this.props.screen === 'landing' || this.props.screen === 'home')) this.startSplash()
    const loop = () => { this.frame(); this.raf = requestAnimationFrame(loop) }
    this.raf = requestAnimationFrame(loop)
    this.syncRoute()
  }
  componentDidUpdate(prev: Props) {
    if (prev.screen !== this.props.screen || prev.params !== this.props.params) {
      this.syncRoute()
      if (this.props.screen === 'capGuide') { this.startRot(); void camera.setNavBarHidden(true); if (camera.canRecordInApp()) { this.setState({ camLoading: !camera.isLive() }); void camera.warm() } }
      if (prev.screen === 'capGuide' && this.props.screen !== 'capGuide') { if (camera.isRecording()) void camera.stopRecording(); camera.stopLater(); void camera.setNavBarHidden(false); clearInterval(this.recTick); this.setState({ camLive: false, recSec: -1, camLoading: false }) }
      if (this.props.screen === 'story') this.setState({ page: 0 })
    }
    if (prev.data.dogs !== this.props.data.dogs) this.syncRoute()
    const s = this.props.session
    if (this.props.screen === 'analyzing' && s && (s.status === 'DONE' || s.status === 'FAILED') && s.id === this.props.params.sessionId) this.props.nav(`/sessions/${s.id}/result`, { replace: true })
  }
  componentWillUnmount() { camera.stopPreview(); void camera.setNavBarHidden(false); clearInterval(this.recTick); cancelAnimationFrame(this.raf); clearTimeout(this.t1); clearTimeout(this.t2); clearTimeout(this.tt); clearTimeout(this.r1); clearTimeout(this.r2) }
  syncRoute() {
    const { screen, params, data } = this.props
    if (screen === 'petNew') {
      const d = params.petEdit ? data.dogs.find((x) => x.id === params.petEdit) : undefined
      if (d && this.state.petId !== d.id) this.setState({ petMode: 'edit', petId: d.id, pet: { ...EMPTY_PET, ...d, size: d.sizeManual ? d.size : null } })
      else if (!params.petEdit && this.state.petMode !== 'new') this.setState({ petMode: 'new', petId: null, pet: EMPTY_PET })
    }
    if ((screen === 'capSelect' || screen === 'capReview' || screen === 'capGuide') && !this.state.capDog && data.dogs.length) this.setState({ capDog: data.dogs[0].id })
    if (this.props.session && this.state.capDog !== this.props.session.dog_id) this.setState({ capDog: this.props.session.dog_id })
  }
  startSplash() {
    clearTimeout(this.t1); clearTimeout(this.t2)
    this.setState({ splash: true, joint: false })
    this.t1 = setTimeout(() => this.setState({ joint: true }), 300)
    this.t2 = setTimeout(() => { this.setState({ splash: false }); if (this.props.screen === 'home' && !this.props.data.loggedIn) this.props.nav('/welcome', { replace: true }) }, 2200)
  }
  /** 마지막으로 올린 영상(이 기기에서 고른 파일). 영상 첨부 화면의 미리보기에 쓴다 */
  lastFileUrl: string | null = null
  vid = (el: HTMLVideoElement | null) => {
    if (!el || this.vids.has(el)) return
    this.vids.add(el)
    // 영상 첨부 화면: 디자인의 견본 영상 대신 방금 올린 영상을 보여 준다
    if (this.props.screen === 'capReview' && this.lastFileUrl) el.src = this.lastFileUrl
    // 촬영 화면: 견본 영상 대신 앱 안 카메라 미리보기(처음이면 권한 창). 못 쓰면 견본 영상 그대로 두고 촬영 버튼은 기기 카메라
    if (this.props.screen === 'capGuide' && camera.canRecordInApp()) {
      // 카메라가 실제로 그림을 내기 전까지는 영상 칸을 숨기고 '카메라를 켜는 중' 을 보인다(회색 빈 화면 대신)
      void camera.startPreview(el).then((ok) => {
        if (ok) camera.uprightInRotatedBox(el)
        this.setState({ camLive: ok })
        if (!ok) return this.setState({ camLoading: false })
        // 첫 프레임이 그려지면 로딩 표시를 걷는다(이벤트를 놓쳐도 1.5초 뒤에는 걷는다)
        const done = () => { if (this.state.camLoading) this.setState({ camLoading: false }) }
        const wait = () => (el.readyState >= 2 && el.videoWidth > 0 ? done() : requestAnimationFrame(wait))
        wait(); setTimeout(done, 1500)
      })
      return
    }
    // 첨부 화면: 아직 올린 영상이 없으면 견본 영상을 보이지 않는다
    if (this.props.screen === 'capReview' && !this.lastFileUrl) { el.removeAttribute('src'); el.removeAttribute('poster'); el.load(); return }
    el.muted = true; el.volume = 0; el.loop = true; el.playsInline = true
    const go = () => { el.muted = true; el.play().catch(() => {}) }
    go()
    el.addEventListener('canplay', go)
    el.addEventListener('pause', () => { if (el.isConnected) setTimeout(go, 60) })
  }
  storyRef = (el: HTMLElement | null) => { if (el) this.storyEl = el }
  repBox = (el: HTMLElement | null) => { if (!el) return; requestAnimationFrame(() => { const h = el.parentElement && el.parentElement.offsetHeight; if (h && h !== this.state.repH) this.setState({ repH: h }) }) }
  frame() {
    if (this.props.screen === 'story' && this.state.page === 2) { const n = performance.now(); if (!this.lastMo || n - this.lastMo > 33) { this.lastMo = n; this.forceUpdate() } }
    for (const v of this.vids) {
      if (!v.isConnected) { this.vids.delete(v); continue }
      if (v.duration && v.currentTime >= v.duration - 0.2) v.currentTime = 0
      if (v.dataset.lines && v.duration) {
        const segLen = (v.duration - 0.2) / 3
        const i = Math.min(2, Math.floor(v.currentTime / segLen))
        if (i !== this.state.line) this.setState({ line: i })
      }
    }
  }

  /* ---------- 이동 ---------- */
  PATH: Record<string, string> = { splash: '/welcome', landing: '/welcome', story: '/intro', login: '/login', signupOrg: '/signup', home: '/', results: '/results', my: '/my', account: '/account', notif: '/notifications', capSelect: '/capture', petNew: '/dogs/new' }
  nav = (screen: string, path?: string, replace?: boolean) => { this.setState({ sheet: null, viaTab: false }); this.props.nav(path || this.PATH[screen] || '/', { replace }) }
  back = () => { this.setState({ sheet: null }); this.props.back() }
  tab = (screen: string) => {
    if (!this.props.data.loggedIn && ['capSelect', 'results', 'my'].includes(screen)) return this.setState({ sheet: 'login' })
    if (screen === 'capSelect') return this.goCapture()
    this.setState({ sheet: null, viaTab: true })
    this.props.nav(this.PATH[screen] || '/')
  }
  toast = (m: string) => { clearTimeout(this.tt); this.setState({ toast: m }); this.tt = setTimeout(() => this.setState({ toast: '' }), 2200) }
  goCapture = (dogId?: string) => {
    const { dogs } = this.props.data
    if (!dogs.length) { this.toast('먼저 반려견을 등록해 주세요'); return this.goPetNew() }
    const cur = dogs.find((d) => d.id === (dogId || this.state.capDog)) || dogs[0]
    // 측정 중인 회차가 있으면 이어서
    if (cur.open) { this.setState({ capDog: cur.id }); return this.nav('capReview', `/sessions/${cur.open}`) }
    this.setState({ capDog: cur.id, sessW: '' })
    this.nav('capSelect')
  }
  /** 가로로 돌리라는 안내는 앱을 켠 뒤 처음 한 번만(16번 찍을 때마다 1.5초씩 기다리지 않게) */
  rotSeen = false
  startRot = () => { if (this.rotSeen) { this.setState({ rotDone: true, rotAnim: true }); return } this.rotSeen = true; clearTimeout(this.r1); clearTimeout(this.r2); this.setState({ rotDone: false, rotAnim: false }); this.r1 = setTimeout(() => this.setState({ rotAnim: true }), 350); this.r2 = setTimeout(() => this.setState({ rotDone: true }), 1500) }
  sessionId(): string | null { return ['capReview', 'capGuide', 'analyzing'].includes(this.props.screen) ? this.props.params.sessionId ?? null : null }
  /** 회차가 없으면 만든다(반려견·오늘 체중) */
  ensureSession = async (): Promise<string> => {
    const sid = this.sessionId()
    if (sid) return sid
    const d = this.props.data.dogs.find((x) => x.id === this.state.capDog)
    if (d && d.open) return d.open
    const w = this.state.sessW.trim() ? Number(this.state.sessW) : null
    const s = await this.props.actions.startSession(this.state.capDog, w != null && Number.isFinite(w) ? w : null)
    return s.id
  }
  shots(): number { const s = this.props.session; return s && this.sessionId() ? s.shots.length : 0 }
  /** 앱 안에서 찍은 영상은 촬영 화면에 머문 채 뒤에서 차례로 올린다(다음 영상을 바로 찍을 수 있게) */
  upQ: Promise<void> = Promise.resolve()
  queueUpload = (file: File | null) => {
    if (!file) return
    this.setState((st: any) => ({ pend: (st.pend || 0) + 1 }))
    this.upQ = this.upQ.then(async () => {
      try {
        const sid = await this.ensureSession()
        const out = await this.props.actions.uploadShot(sid, file)
        void camera.rememberFirstFrame(out.id, file).then(() => this.forceUpdate())
        if (this.lastFileUrl) URL.revokeObjectURL(this.lastFileUrl)
        this.lastFileUrl = URL.createObjectURL(file)
        this.toast(out.warnings?.length ? out.warnings[0].message : `${out.seq_no}번째 영상을 첨부했어요`)
      } catch (e) {
        this.toast(errMsg(e, '영상을 올리지 못했어요. 잠시 후 다시 시도해 주세요'))
      } finally {
        this.setState((st: any) => ({ pend: Math.max(0, (st.pend || 0) - 1) }))
      }
    })
  }
  addFile = async (file: File | null) => {
    if (!file || this.state.busy) return
    this.setState({ busy: true })
    try {
      const sid = await this.ensureSession()
      const out = await this.props.actions.uploadShot(sid, file)
      void camera.rememberFirstFrame(out.id, file).then(() => this.forceUpdate())
      if (this.lastFileUrl) URL.revokeObjectURL(this.lastFileUrl)
      this.lastFileUrl = URL.createObjectURL(file)
      for (const v of this.vids) if (v.isConnected && this.props.screen === 'capReview') v.src = this.lastFileUrl
      this.toast(out.warnings?.length ? out.warnings[0].message : `${out.seq_no}번째 영상을 첨부했어요`)
      if (this.props.params.sessionId !== sid || this.props.screen !== 'capReview') this.nav('capReview', `/sessions/${sid}`, this.props.screen === 'capGuide')
    } catch (e) {
      this.toast(errMsg(e, '영상을 올리지 못했어요. 잠시 후 다시 시도해 주세요'))
    } finally {
      this.setState({ busy: false })
    }
  }
  goCapGuide = async () => {
    if (this.shots() >= 16) return this.toast('영상 16개를 모두 첨부했어요')
    if (this.state.busy) return
    this.setState({ busy: true })
    try { const sid = await this.ensureSession(); this.nav('capGuide', `/sessions/${sid}/record`) }
    catch (e) { this.toast(errMsg(e, '회차를 시작하지 못했어요')) }
    finally { this.setState({ busy: false }) }
  }
  goPetNew = () => { this.setState({ petMode: 'new', pet: EMPTY_PET, petId: null }); this.nav('petNew') }
  openRes = (id: string) => { this.setState({ gait: 'trot' }); this.nav('detail', `/sessions/${id}/result`) }
  openDog = (id: string) => this.nav('dog', `/dogs/${id}`)

  renderVals() {
    const s = this.state, sc = s.splash ? 'splash' : this.props.screen, li = this.props.data.loggedIn
    const { dogs, results, ana, acct } = this.props.data
    const dogById = (id: string) => dogs.find((d) => d.id === id)
    const ctx = { results, dogById }
    const valid = (id: string) => valid_(ctx, id)
    const sessNo = (R: DRes) => sessNo_(ctx, R)
    const baseOf = (d: DDog) => baseOf_(ctx, d)

    const anaP = ana ? ana.p : 0, anaFloor = Math.min(4, Math.floor(anaP))
    const anaDog = ana ? dogById(ana.dog) : null

    const qq = (s.q || '').trim()
    const shown = dogs.filter((d) => !qq || d.name.includes(qq))
    const homeDogs = shown.map((d) => { const all = results.filter((r) => r.dog === d.id); return { init: d.name[0], name: d.name, desc: desc(d), live: !!d.open, meta: all.length ? `마지막 측정 ${all[0].date} · ${all.length}회차` : '아직 측정 기록이 없어요', open: () => this.openDog(d.id) } })

    const D = dogById(this.props.params.dogId || '') || dogs[0]
    let dd: any = { name: '', init: '', desc: '', tags: [], rows: [], hist: [], has: false, none: true, count: '', edit: () => {}, compare: () => {}, start: () => {} }
    if (D) {
      const all = results.filter((r) => r.dog === D.id), bId = baseOf(D), bR = results.find((r) => r.id === bId)
      dd = { name: D.name, init: D.name[0], desc: desc(D),
        tags: [SIZE[D.size] + (D.sizeManual ? ' · 직접 지정' : ' · 자동 분류'), SEX[D.sex || 'm']],
        rows: [{ k: '재활 시작일', v: D.rehab ? fmtD(D.rehab) : '미입력', sub: '' }, { k: '관심 다리', v: D.focus ? LIMB[D.focus] : '미선택', sub: '' },
          { k: '기준 회차', v: bR ? `${bR.date} · ${sessNo(bR)}회차` : '없음', sub: D.base ? '' : bR ? '가장 이른 회차로 자동 지정' : '' }, { k: '내부 메모', v: D.memo || '없음', sub: '보고서에는 넣지 않아요' }],
        hist: all.map((r, i) => { const stt = ST[r.st]; return { title: `${sessNo(r)}회차 · ${r.date}`, sub: r.st === 'fail' ? `체중 ${r.w}kg · 쓸 수 있는 통과 없음` : `체중 ${r.w}kg · 유효 통과 ${r.ps[1]} · 모델 ${r.model}`, base: r.id === bId, rep: !!r.rep, canBase: r.st !== 'fail' && r.id !== bId,
          setBase: async (e: any) => { e.stopPropagation(); try { await this.props.actions.updateDog(D.id, { baseline_session_id: r.id, version: D.raw.version }); this.toast(`${r.date} 회차를 기준으로 정했어요`) } catch (err) { this.toast(err instanceof ApiError && err.code === 'DOG_MODIFIED' ? DOG_MODIFIED_MSG : errMsg(err, '기준 회차를 바꾸지 못했어요')) } },
          st: stt[0], bg: stt[1], c: stt[2], bt: i ? '1px solid #F2EFEA' : 'none', open: () => this.openRes(r.id) } }),
        has: all.length > 0, none: !all.length, count: all.length + '회차',
        edit: () => this.nav('petNew', `/dogs/${D.id}/edit`),
        compare: () => valid(D.id).length < 2 ? this.toast('유효한 회차가 2개 이상 있어야 비교할 수 있어요') : (this.props.setUi({ cmp: 'base' }), this.nav('compare', `/dogs/${D.id}/compare`)),
        start: () => this.goCapture(D.id) }
    }

    const R = results.find((r) => r.id === this.props.params.sessionId)
    const G: DGait = s.gait || 'trot'
    const { rd, rp } = resultVals(ctx, R, G)

    // 경과 비교: API 값
    const CD = sc === 'compare' ? dogById(this.props.params.dogId || '') : D
    const cmpd = this.props.compare
    let cp: any = { has: false, none: true, rows: [], tl: '', tr: '', dl: [], xl: [], name: CD ? CD.name : '', baseLabel: '', baseDate: '', tDate: '', modelChanged: false, modelMsg: '', two: true, focusNote: '' }
    if (CD && cmpd && cmpd.cmp) {
      const c = cmpd.cmp, mode = this.props.ui.cmp
      const B = results.find((r) => r.id === c.base.session_id), T = results.find((r) => r.id === c.target.session_id)
      const when = (r: DRes | undefined, iso: string) => (r ? `${r.date} · ${sessNo(r)}회차` : short(iso))
      cp = { has: true, none: false, name: CD.name, baseLabel: mode === 'base' ? '기준 회차' : '직전 회차', baseDate: when(B, c.base.measured_on), tDate: when(T, c.target.measured_on),
        modelChanged: c.model_changed, modelMsg: `두 회차의 분석 모델이 달라요(${c.base.model_version ?? '-'} → ${c.target.model_version ?? '-'}). 분석 방식이 바뀌어 수치를 그대로 비교하기 어려워요.`,
        rows: cmpd.rows, ...cmpd.trend,
        focusNote: CD.focus ? `관심 다리(${LIMB[CD.focus]})를 맨 앞에 보여 드려요.` : '관심 다리를 정하면 그 다리를 맨 앞에 보여 드려요.' }
    }

    const reqOrg = [s.to[0], s.to[1], s.to[2]].every(Boolean)
    const orgOk = reqOrg && s.so.org && s.so.dev && s.so.id.length >= 4 && s.so.pw.length >= 4 && s.so.pw === s.so.pw2
    const setSo = (k: string) => (e: any) => { const v = e.target.value; this.setState((st: any) => ({ so: { ...st.so, [k]: v } })) }
    const setPet = (k: string) => (e: any) => { const v = e.target.value; this.setState((st: any) => ({ pet: { ...st.pet, [k]: v } })) }
    const setF = (g: string, k: string) => (e: any) => { const v = e.target.value; this.setState((st: any) => ({ [g]: { ...st[g], [k]: v } })) }
    const setLi = (k: string) => (e: any) => { const v = e.target.value; this.setState((st: any) => ({ li: { ...st.li, [k]: v } })) }
    const termRows = (key: string, labels: [string, boolean][]) => labels.map(([label, view], i) => ({ label, view, c: chk(s[key][i]), toggle: () => this.setState((st: any) => { const a = [...st[key]]; a[i] = !a[i]; return { [key]: a } }) }))

    const showTabs = li && ['home', 'results', 'my', 'story'].includes(sc)
    // 소개 장의 그림 높이: 4번째 장(보고서 견본) 높이에 맞추되, 짧은 폰에서는 아래 글이 잘리지 않게 화면의 절반 남짓으로 줄인다
    const storyH = Math.min(s.repH || 480, Math.max(380, Math.round(window.innerHeight * 0.5)))
    const tbOn = (k: string) => { const on = (k === 'home' && sc === 'home') || (k === 'story' && sc === 'story') || (k === 'results' && sc === 'results') || (k === 'my' && sc === 'my'); return { bg: on ? '#F1EEE9' : 'transparent', c: on ? '#B4501A' : '#8E949C', w: on ? 700 : 500 } }
    const dark = ['landing', 'capGuide'].includes(sc)
    const landscape = sc === 'capGuide' && s.rotDone
    const page = s.page
    const pagesCopy: [string, string, string, string, number][] = [
      ['', '반려견을 평소처럼 걷게 합니다.', '', 'transparent', 0],
      ['', '반려견이 걷는 모습을 옆에서 촬영합니다.', '', 'transparent', 1],
      ['', 'AI 모델이 관절점을 찾고,\n보행 패턴을 분석합니다.', '', 'transparent', 2],
      ['', '결과를 보고서로 받아\nPDF로 저장할 수 있습니다.', '', 'transparent', 3]]
    const filtDogs = results.filter((r) => dogById(r.dog) && (s.filt === 'all' || r.dog === s.filt))
    const isOrg = true
    const capD = dogById(s.capDog) || ({} as Partial<DDog>)
    const autoSz = autoSize(s.pet.breed, s.pet.kg)
    const shots = this.shots()
    const sess = this.props.session
    const anaSess = sc === 'analyzing' ? sess : null
    const anaPctNow = anaSess ? Math.round((this.props.sessionAna?.p ?? 0) / 5 * 100) : Math.round(anaP / 5 * 100)
    const anaStepNow = anaSess ? STEPS[Math.min(4, Math.floor(this.props.sessionAna?.p ?? 0))] : STEPS[anaFloor]
    const rep = this.props.reports?.reports.find((r) => r.edition === (s.repType === 'v' ? 'VET' : 'OWNER'))
    const bq = s.pet.breed.trim().replace(/\s/g, '')
    const bList = bq ? BREEDS.filter((b) => b.replace(/\s/g, '').includes(bq)).slice(0, 6) : []
    const bExact = BREEDS.includes(s.pet.breed)

    // 알림: 회차 상태에서 만든다(알림 API 없음)
    const notifs = [
      ...(ana && anaDog ? [{ title: `${anaDog.name} 분석이 진행 중이에요`, body: `영상 ${ana.n}개의 관절점을 찾고 있어요. 끝나면 알려 드릴게요.`, when: '진행 중', dot: '#D2601A', open: () => this.nav('analyzing', `/sessions/${ana.sessionId}/analyzing`) }] : []),
      ...results.slice(0, 6).map((r) => { const d = dogById(r.dog); return r.st === 'fail'
        ? { title: `${d?.name ?? ''} 분석에 실패했어요`, body: r.result?.fail_reason?.message || '쓸 수 있는 통과가 없었어요. 다시 촬영해 주세요.', when: r.date, dot: '#C9C4BC', open: () => this.openRes(r.id) }
        : { title: `${d?.name ?? ''} ${r.rep ? '보고서가 만들어졌어요' : '분석이 끝났어요'}`, body: r.rep ? '보호자용·수의사용 보고서를 확인해 보세요.' : '회차 결과를 확인해 보세요.', when: r.date, dot: r.rep ? '#D2601A' : '#C9C4BC', open: () => this.openRes(r.id) } }),
    ]
    if (!notifs.length) notifs.push({ title: '가입을 환영해요', body: '반려견을 등록하고 첫 보행 영상을 찍어 보세요.', when: '방금', dot: '#D2601A', open: this.goPetNew })

    return {
      rootStyle: this.props.rootStyle || {},
      isSplash: sc === 'splash', isLanding: sc === 'landing', isLogin: sc === 'login', isSignupOrg: sc === 'signupOrg',
      isHome: sc === 'home', isDog: sc === 'dog', isPetNew: sc === 'petNew', isNotif: sc === 'notif', isStory: sc === 'story', isCapSelect: sc === 'capSelect', isCapGuide: sc === 'capGuide',
      isCapReview: sc === 'capReview', isAnalyzing: sc === 'analyzing', isResults: sc === 'results', isDetail: sc === 'detail', isReport: sc === 'report', isCompare: sc === 'compare', isMy: sc === 'my', isAccount: sc === 'account',
      vid: this.vid, storyRef: this.storyRef, repBox: this.repBox, back: this.back,
      jointOp: s.joint ? 1 : 0, jointTr: s.joint ? 'opacity 0.5s ease-out' : 'none', replaySplash: () => this.startSplash(),
      lines: LINES.map((t, i) => ({ t, op: i === s.line ? 1 : 0, ty: i === s.line ? 0 : (i < s.line ? -14 : 14) })),
      goStory: () => this.nav('story'), openStart: () => this.nav('signupOrg'), goLogin: () => this.nav('login'),
      fLoginId: s.li.id, fLoginPw: s.li.pw, onLoginId: setLi('id'), onLoginPw: setLi('pw'),
      loginBg: s.li.id.length >= 1 && s.li.pw.length >= 1 ? '#D2601A' : '#C3C8CF',
      doLogin: async () => {
        if (!(s.li.id.length >= 1 && s.li.pw.length >= 1)) return this.toast('아이디·비밀번호를 입력해 주세요')
        // 로그인은 촬영·업로드의 busy 와 따로 막는다(업로드가 걸려 있으면 로그인 버튼이 말없이 무시되던 문제)
        if (s.loginBusy) return
        this.setState({ loginBusy: true })
        try { await this.props.auth.login({ login_id: s.li.id.trim(), password: s.li.pw }); this.setState({ li: { id: '', pw: '' }, q: '', viaTab: true }); this.props.nav(this.props.query.get('from') || '/', { replace: true }) }
        catch (e) { this.toast(errMsg(e, '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.')) }
        finally { this.setState({ loginBusy: false }) }
      },
      loginSub: '동물병원·재활센터 계정으로 로그인해요.', loginIdLabel: '아이디', loginIdPh: '가입할 때 만든 아이디',
      orgFields: [
        { label: '기관명', ph: '예) 한빛동물병원', type: 'text', val: s.so.org, on: setSo('org') },
        { label: '기관 주소', ph: '주소 검색', type: 'text', val: s.so.loc, on: setSo('loc') },
        { label: '디바이스 번호', ph: '예) PP-2410-0381', type: 'text', val: s.so.dev, on: setSo('dev'), hint: '측정 기기 뒷면 라벨에 적혀 있어요.', hc: '#5B6472' }],
      orgAcctFields: [
        { label: '아이디', ph: '영문·숫자 4~16자', type: 'text', val: s.so.id, on: setSo('id') },
        { label: '비밀번호', ph: '4자 이상', type: 'password', val: s.so.pw, on: setSo('pw') },
        { label: '비밀번호 확인', ph: '한 번 더 입력', type: 'password', val: s.so.pw2, on: setSo('pw2'), hint: s.so.pw2 && s.so.pw !== s.so.pw2 ? '비밀번호가 달라요' : false, hc: '#C2412D' }],
      allOrgC: chk(s.to.every(Boolean)), allOrgToggle: () => this.setState((st: any) => ({ to: st.to.map(() => !st.to.every(Boolean)) })),
      termsOrg: termRows('to', [['[필수] 서비스 이용약관', true], ['[필수] 개인정보 수집 및 이용', true], ['[필수] 측정 기기 연동 및 위치정보 이용', true], ['[선택] 마케팅 정보 수신', true]]),
      signOrgBg: orgOk ? '#D2601A' : '#C3C8CF',
      doSignupOrg: () => { if (!orgOk) return this.toast(!reqOrg ? '필수 약관에 동의해 주세요' : (s.so.pw2 && s.so.pw !== s.so.pw2) ? '비밀번호가 서로 달라요' : '입력하지 않은 항목이 있어요'); this.toast('회원가입은 준비 중이에요. 기관 관리자에게 계정을 요청해 주세요') },

      acctKind: '기관', acctName: acct.name,
      goNotif: () => this.nav('notif'), tabMy: () => this.tab('my'), tabHome: () => this.tab('home'), tabResults: () => this.tab('results'), tabStory: () => this.tab('story'), tabCapture: () => this.tab('capSelect'),
      hasDogs: dogs.length > 0, noDogs: !dogs.length, dogCount: dogs.length + '마리',
      q: s.q, onQ: (e: any) => { const v = e.target.value; this.setState({ q: v }) }, homeDogs, noMatch: !!qq && !shown.length,
      goPetNew: this.goPetNew, goCapture: () => this.goCapture(), dd,
      anaOn: !!ana && li && sc !== 'analyzing', goAnalyzing: () => ana && this.nav('analyzing', `/sessions/${ana.sessionId}/analyzing`), anaName: anaSess ? anaSess.dog.name : (anaDog ? anaDog.name : ''), anaPct: anaPctNow, anaN: anaFloor + 1, anaStep: anaStepNow,
      prints: (() => { const ph = Math.floor(Date.now() / 420) % 11; return Array.from({ length: 8 }, (_, i) => { const on = ph <= 8 ? i < ph : ph === 9; const jx = [0, 6, -8, 4, -4, 10, -2, 5][i], jr = -23 + [7, -4, 10, -8, 4, -10, 8, -5][i]; return { x: (i % 2 ? 236 : 118) + jx * 2 + Math.round(Math.sin(i * 0.9) * 22), y: 656 - i * 68 + (i % 2 ? 10 : 0), r: jr, op: on ? 1 : 0, s: on ? 1 : 0.7 } }) })(),

      petTitle: s.petMode === 'edit' ? '반려견 정보 수정' : '반려견 등록', petCta: s.petMode === 'edit' ? '저장하기' : '등록하기',
      petFields: [
        { label: '이름', ph: '예) 보리', val: s.pet.name, on: setPet('name') },
        { label: '견종', ph: '견종을 입력하면 목록이 떠요', val: s.pet.breed, on: setPet('breed'), showSug: !!bq && !bExact, noSug: !!bq && !bExact && !bList.length,
          sugs: bList.map((name, i) => ({ name, bt: i ? '1px solid #F2EFEA' : 'none', pick: () => this.setState((st: any) => ({ pet: { ...st.pet, breed: name } })) })) },
        { label: '체중 (kg)', ph: '예) 28.4', val: s.pet.kg, on: setPet('kg') },
        { label: '출생연도 (선택)', ph: '예) 2019', val: s.pet.birth, on: setPet('birth') }],
      sexes: Object.entries(SEX).map(([k, label]) => ({ label, ...pickSt(s.pet.sex === k), pick: () => this.setState((st: any) => ({ pet: { ...st.pet, sex: k } })) })),
      sizes: Object.entries(SIZE).map(([k, label]) => ({ label, ...pickSt((s.pet.size || autoSz) === k), pick: () => this.setState((st: any) => ({ pet: { ...st.pet, size: st.pet.size === k ? null : k } })) })),
      sizeNote: s.pet.size ? '직접 선택 · 다시 누르면 자동 분류' : '견종·체중으로 자동 분류돼요',
      limbs: Object.entries(LIMB).map(([k, label]) => ({ label, ...pickSt(s.pet.focus === k), pick: () => this.setState((st: any) => ({ pet: { ...st.pet, focus: st.pet.focus === k ? null : k } })) })),
      petRehab: s.pet.rehab, onRehab: setPet('rehab'), petMemo: s.pet.memo, onMemo: setPet('memo'),
      petBg: s.pet.name && s.pet.breed && s.pet.kg ? '#D2601A' : '#C3C8CF',
      doPetNew: async () => {
        if (!s.pet.name || !s.pet.breed || !s.pet.kg) return this.toast('이름·견종·체중을 입력해 주세요')
        if (s.busy) return
        const kg = Number(s.pet.kg)
        if (!Number.isFinite(kg) || kg <= 0) return this.toast('체중은 숫자로 입력해 주세요')
        this.setState({ busy: true })
        try {
          if (s.petMode === 'edit') { const cur = this.props.data.dogs.find((x) => x.id === s.petId); await this.props.actions.updateDog(s.petId, { ...petBody(s.pet), version: cur ? cur.raw.version : 0 }); this.back(); this.toast('저장했어요') }
          else { const d = await this.props.actions.createDog(petBody(s.pet)); this.nav('dog', `/dogs/${d.id}`, true); this.toast(`${s.pet.name} 등록을 마쳤어요`) }
        } catch (e) { this.toast(e instanceof ApiError && e.code === 'DOG_MODIFIED' ? DOG_MODIFIED_MSG : e instanceof ApiError && e.fields.length ? `${e.message} (${e.fields.map((f) => f.field).join(', ')})` : errMsg(e, '저장하지 못했어요')) }
        finally { this.setState({ busy: false }) }
      },

      notifs,

      storyBack: !li || !s.viaTab, storyTitlePad: !li || !s.viaTab ? 0 : 12, storyBottom: showTabs ? 96 : 0,
      onStory: (e: any) => { const p = Math.round(e.target.scrollLeft / e.target.clientWidth); if (p !== this.state.page) { if (p === 2) this.moStart = Date.now(); this.setState({ page: p }) } },
      pages: pagesCopy.map((c, i) => ({ num: String(i + 1).padStart(2, '0'), tag: c[0], title: c[1], body: c[2], vbg: c[3], vh: c[4] === 3 ? 'auto' : storyH + 'px', v0: c[4] === 0, v1: c[4] === 1, v2: c[4] === 2, v3: c[4] === 3 })),
      pageDots: pagesCopy.map((_, i) => ({ w: i === page ? 18 : 6, c: i === page ? '#1B2433' : 'rgba(27,36,51,.2)' })),
      storyBtn: page < 3 ? '다음' : li ? '촬영하기' : '시작하기', storyBtnBg: page < 3 ? '#1B2433' : '#D2601A',
      // 보고서 견본 카드(4번째 장) 확대 비율: 디자인은 1.38. 짧은 폰에서는 그림 높이(storyH)에 들어가게 줄인다(카드 원래 높이 약 380px)
      repZoom: String(Math.max(0.9, Math.min(1.38, Math.round(window.innerHeight * 0.5) / 380))),
      storyKneeL: knee(53), storyKneeR: knee(46),
      mo: (() => {
        const T = 6.4, t = ((Date.now() - (this.moStart || 0)) / 1000) % T
        const cl = (v: number) => Math.max(0, Math.min(1, v)), ez = (v: number) => v * v * (3 - 2 * v)
        const z = ez(cl((t - 0.4) / 1.4)), sk = ez(cl((t - 2.0) / 1.2)), m = ez(cl((t - 3.6) / 1.0)), out = ez(cl((t - 5.7) / 0.5))
        const k = 372 / 1254, SX = 2.069, SY = 2.036, TX = k * -701, OFF = (storyH - 372) / 2, TY = (OFF - 23) + k * -520 - OFF * SY
        return { t1: `translate(${(z * TX).toFixed(2)}px,${(z * TY).toFixed(2)}px) scale(${(1 + z * (SX - 1)).toFixed(4)},${(1 + z * (SY - 1)).toFixed(4)})`, o1: ((1 - m) * (1 - out)).toFixed(3), o3: (sk * (1 - m)).toFixed(3), o2: (m * (1 - out)).toFixed(3) }
      })(),
      prevOp: page > 0 ? 1 : 0.35, prevPe: page > 0 ? 'auto' : 'none',
      storyPrev: () => { const el = this.storyEl; if (page > 0 && el) el.scrollTo({ left: (page - 1) * el.clientWidth, behavior: 'smooth' }) },
      storyNext: () => { const el = this.storyEl; if (page < 3 && el) el.scrollTo({ left: (page + 1) * el.clientWidth, behavior: 'smooth' }); else if (page >= 3) { li ? this.goCapture() : this.nav('signupOrg') } },

      capDogs: dogs.map((d) => { const on = d.id === s.capDog; return { init: d.name[0], name: d.name, desc: desc(d), bd: on ? '#D2601A' : '#ECE8E2', dot: on ? '#D2601A' : 'transparent', pick: () => this.setState({ capDog: d.id }) } }),
      sessW: s.sessW, onSessW: (e: any) => { const v = e.target.value; this.setState({ sessW: v }) }, sessWPh: capD.kg ? `등록 체중 ${capD.kg}` : '예) 28.1',
      fromGallery: async () => { if (shots >= 16) return this.toast('영상 16개를 모두 첨부했어요'); const f = await this.props.pickFile(false); await this.addFile(f) },
      goCapGuide: this.goCapGuide,
      capDogName: capD.name || '',
      slots: Array.from({ length: 16 }, (_, i) => { const done = i < shots, next = i === shots; const sh = [...(this.props.session?.shots ?? [])].sort((a: any, b: any) => a.seq_no - b.seq_no)[i]; return { n: i + 1, done, next, thumb: done && sh ? camera.shotThumbs[sh.id] ?? '' : '', bg: done ? '#141B22' : next ? '#FCEEE3' : '#F4F1EC', bs: next ? 'dashed' : 'solid', bd: done ? '#141B22' : next ? '#D2601A' : '#ECE8E2', nc: done ? 'rgba(255,255,255,.75)' : next ? '#B4501A' : '#A0A7B2', cur: next ? 'pointer' : 'default', tap: next ? this.goCapGuide : () => {} } }),
      shotN: shots, shotPct: Math.round(shots / 16 * 100), moreOp: shots >= 16 ? 0.4 : 1,
      shotHint: s.busy ? '영상을 올리는 중이에요…' : shots >= 16 ? '16개를 모두 첨부했어요. 분석을 시작해 주세요.' : `${shots + 1}번째 영상을 이어서 찍어 주세요. 16개를 모두 채우면 결과가 더 정확해요.`,
      rotHint: !s.rotDone, rotDone: !!s.rotDone, rotDeg: s.rotAnim ? 90 : 0,
      // 촬영 화면 영상 칸: 앱 안 카메라를 쓰면 견본 영상 없이 카메라만
      capVidSrc: camera.canRecordInApp() ? undefined : '/assets/landing.mp4', capVidPoster: camera.canRecordInApp() ? undefined : '/assets/landing-poster.webp',
      camLoading: !!s.camLoading, camOp: s.camLoading ? 0 : 1,
      recTime: `영상 ${Math.min(16, shots + (s.pend || 0) + 1)}/16 · ${s.recSec >= 0 ? `00:${String(Math.min(99, s.recSec)).padStart(2, '0')} 녹화 중` : '00:00 / 00:04'}`, recPillBg: s.busy || s.recSec >= 0 ? '#C2412D' : 'rgba(14,18,23,.55)', recDot: s.busy || s.recSec >= 0 ? '#fff' : '#E5604D',
      recBtnS: s.busy || s.recSec >= 0 ? 30 : 62, recBtnR: s.busy || s.recSec >= 0 ? 8 : 31,
      capHint: s.busy ? '영상을 올리는 중이에요' : s.recSec < 0 && s.pend > 0 ? `앞 영상 ${s.pend}개를 올리는 중이에요. 바로 다음 영상을 찍어도 돼요` : s.recSec >= 0 ? '반려견이 화면을 다 지나가면 버튼을 다시 눌러 멈춰 주세요' : s.camLive ? '점선 안에 반려견 옆모습이 들어오게 맞추고 촬영 버튼을 눌러 주세요' : '촬영 버튼을 누르면 카메라가 열려요. 점선 안에 반려견 옆모습이 들어오게 맞춰 주세요',
      // 촬영 버튼: 기기 카메라(파일 입력 capture)
      toggleRec: async () => {
        if (s.busy) return
        if (camera.isRecording()) {
          clearInterval(this.recTick); this.setState({ recSec: -1 })
          const f = await camera.stopRecording(); this.queueUpload(f); return
        }
        if (shots + (s.pend || 0) >= 16) return this.toast('영상 16개를 모두 찍었어요. X 를 눌러 첨부 목록으로 가 주세요')
        // 앱 안 카메라가 켜져 있으면 바로 녹화, 아니면 기기 카메라 앱
        if (s.camLive && camera.startRecording()) {
          const t0 = Date.now(); this.setState({ recSec: 0 })
          this.recTick = setInterval(() => this.setState({ recSec: Math.floor((Date.now() - t0) / 1000) }), 250)
          return
        }
        const f = await this.props.pickFile(true); await this.addFile(f)
      },
      startAna: async () => {
        const sid = this.sessionId()
        if (!shots || !sid) return this.toast('영상을 1개 이상 첨부해 주세요')
        if (s.busy) return
        this.setState({ busy: true })
        try { await this.props.actions.completeSession(sid); this.nav('analyzing', `/sessions/${sid}/analyzing`, true) }
        catch (e) { this.toast(errMsg(e, '분석을 시작하지 못했어요')) }
        finally { this.setState({ busy: false }) }
      },

      filters: [{ id: 'all', label: '전체' }, ...dogs.map((d) => ({ id: d.id, label: d.name }))].map((f) => { const on = s.filt === f.id; return { label: f.label, bg: on ? '#1B2433' : '#fff', c: on ? '#fff' : '#3A4250', bd: on ? '#1B2433' : '#ECE8E2', pick: () => this.setState({ filt: f.id }) } }),
      resList: filtDogs.map((r, i) => ({ name: dogById(r.dog)!.name, when: `${r.date} · ${sessNo(r)}회차`, st: ST[r.st][0], bg: ST[r.st][1], c: ST[r.st][2], sym: r.st === 'fail' ? '다시 촬영 필요' : `유효 통과 ${r.ps[1]}`, bt: i ? '1px solid #F2EFEA' : 'none', open: () => this.openRes(r.id) })),
      hasRes: filtDogs.length > 0, noRes: !filtDogs.length,
      rd, retake: () => { if (R) this.goCapture(R.dog) },
      gaitSegs: seg([['walk', '평보'], ['trot', '속보']], G, (k) => this.setState({ gait: k })), gaitName: rd.gaitName,
      openRep: () => { if (!R) return; this.setState({ repType: 'g' }); this.nav('report', `/sessions/${R.id}/report`) },
      openCompare: () => { if (!R) return; if (valid(R.dog).length < 2) return this.toast('유효한 회차가 2개 이상 있어야 비교할 수 있어요'); this.props.setUi({ cmp: 'base' }); this.nav('compare', `/dogs/${R.dog}/compare`) },
      partMsg: R?.result?.notices?.[0]?.message || '일부 통과에서 다리가 가려지거나 뛰어서 해당 통과를 제외하고 계산했습니다.',
      rp, isRepG: s.repType === 'g', isRepV: s.repType === 'v', repKind: s.repType === 'v' ? '보행 분석 보고서 · 수의사용' : '보행 분석 보고서 · 보호자용',
      repStatus: R ? this.props.reportStatus(rep, R.model) : '',
      repSegs: seg([['g', '보호자용'], ['v', '수의사용']], s.repType, (k) => this.setState({ repType: k })),
      regenRep: async () => { if (!R || !rep) return this.toast('아직 보고서가 없어요'); try { await this.props.actions.regenerateReport(R.id, rep.id); this.toast('보고서를 다시 만들고 있어요') } catch (e) { this.toast(errMsg(e, '지금은 다시 만들 수 없어요')) } },
      saveRep: () => { if (!rep || rep.status !== 'DONE' || !rep.download_url) return this.toast(rep && rep.status === 'FAILED' ? '보고서를 만들지 못했어요. 다시 만들기를 눌러 주세요' : '보고서를 만드는 중이에요. 잠시 뒤 다시 눌러 주세요'); this.props.openFile(rep.download_url); this.toast('PDF를 내려받았어요') },

      cp, cmpSegs: seg([['base', '기준 회차 대비'], ['prev', '직전 회차 대비']], this.props.ui.cmp, (k) => this.props.setUi({ cmp: k as 'base' | 'prev' })),
      trendKs: [['rom', '무릎 가동 범위'], ['stride', '걸음 길이'], ['stance', '입각기 비율'], ['sym', '대칭 지수']].map(([k, label]) => { const on = this.props.ui.tk === k; return { label, bg: on ? '#1B2433' : '#fff', c: on ? '#fff' : '#3A4250', bd: on ? '#1B2433' : '#ECE8E2', pick: () => this.props.setUi({ tk: k }) } }),
      reanalyze: () => this.toast(PREP),

      isOrg, isUser: false, myName: acct.name, myDev: acct.dev || '-',
      goAccount: () => this.nav('account'), help: () => this.toast(PREP), settings: () => this.toast(PREP),
      myDogs: dogs.map((d) => ({ init: d.name[0], name: d.name, desc: desc(d) + ' · ' + SEX[d.sex || 'm'], edit: () => this.nav('petNew', `/dogs/${d.id}/edit`), del: () => this.setState({ sheet: 'del', delId: d.id }) })),
      myDogCount: dogs.length + '마리',
      tgBg: s.notifOn ? '#D2601A' : '#DDD7CE', tgX: s.notifOn ? 22 : 2, toggleNotif: () => this.setState((st: any) => ({ notifOn: !st.notifOn })),
      askLogout: () => this.setState({ sheet: 'logout' }),
      acctRows: [['계정 유형', '기관 회원'], ['기관명', acct.name], ['담당자', acct.staffName || '-'], ['이메일', acct.email || '-'], ['아이디', acct.id || '-'], ['기관 주소', acct.loc || '-'], ['디바이스 번호', acct.dev || '-']].map(([k, v], i) => ({ k, v, bt: i ? '1px solid #F2EFEA' : 'none' })),
      // 기본 정보 수정(이름·이메일)과 비밀번호 변경은 아래 시트에서. 서버 오류 문구는 그대로 보여 준다
      editAcct: () => this.setState({ sheet: 'acct', af: { name: acct.staffName, email: acct.email } }),
      openPw: () => this.setState({ sheet: 'pw', pf: { cur: '', nw: '', nw2: '' } }),
      fAcctName: s.af.name, fAcctEmail: s.af.email, onAcctName: setF('af', 'name'), onAcctEmail: setF('af', 'email'),
      fPwCur: s.pf.cur, fPwNew: s.pf.nw, fPwNew2: s.pf.nw2, onPwCur: setF('pf', 'cur'), onPwNew: setF('pf', 'nw'), onPwNew2: setF('pf', 'nw2'),
      pwHint: s.pf.nw && s.pf.nw.length < 8 ? '8자 이상으로 입력해 주세요' : s.pf.nw2 && s.pf.nw !== s.pf.nw2 ? '새 비밀번호가 서로 달라요' : '',
      saveOp: s.saving ? 0.55 : 1,
      saveAcct: async () => {
        const name = s.af.name.trim(), email = s.af.email.trim()
        if (!name) return this.toast('담당자 이름을 입력해 주세요')
        if (s.saving) return
        const body: { name?: string; email?: string } = {}
        if (name !== acct.staffName) body.name = name
        if (email && email !== acct.email) body.email = email
        if (!body.name && !body.email) return this.setState({ sheet: null })
        this.setState({ saving: true })
        try { await this.props.auth.updateMe(body); this.setState({ sheet: null }); this.toast('기본 정보를 저장했어요') }
        catch (e) { this.toast(e instanceof ApiError && e.code === 'CONTRACT_EXPIRED' ? '계약이 끝나 정보를 바꿀 수 없어요' : errMsg(e, '저장하지 못했어요')) }
        finally { this.setState({ saving: false }) }
      },
      savePw: async () => {
        const { cur, nw, nw2 } = s.pf
        if (!cur || !nw || !nw2) return this.toast('비밀번호를 모두 입력해 주세요')
        if (nw.length < 8) return this.toast('새 비밀번호는 8자 이상이어야 해요')
        if (nw !== nw2) return this.toast('새 비밀번호가 서로 달라요')
        if (nw === cur) return this.toast('지금 비밀번호와 다른 비밀번호를 입력해 주세요')
        if (s.saving) return
        this.setState({ saving: true })
        try { await this.props.auth.changePassword(cur, nw); this.setState({ sheet: null, pf: { cur: '', nw: '', nw2: '' } }); this.toast('비밀번호를 바꿨어요') }
        catch (e) { this.toast(e instanceof ApiError && e.code === 'PASSWORD_MISMATCH' ? '지금 비밀번호가 맞지 않아요' : errMsg(e, '비밀번호를 바꾸지 못했어요')) }
        finally { this.setState({ saving: false }) }
      },

      showTabs, tb: { home: tbOn('home'), story: tbOn('story'), results: tbOn('results'), my: tbOn('my') },
      sheetLogin: s.sheet === 'login', sheetDel: s.sheet === 'del', sheetLogout: s.sheet === 'logout', sheetAcct: s.sheet === 'acct', sheetPw: s.sheet === 'pw', anySheet: !!s.sheet,
      closeSheet: () => this.setState({ sheet: null }),
      goSignupOrg: () => this.nav('signupOrg'), sheetToLogin: () => this.nav('login'),
      delName: (dogById(s.delId) || ({} as Partial<DDog>)).name || '',
      confirmDel: () => { this.setState({ sheet: null }); this.toast('반려견 삭제는 준비 중이에요') },
      confirmLogout: () => { this.props.auth.logout(); this.setState({ sheet: null, li: { id: '', pw: '' } }); this.props.nav('/welcome', { replace: true }) },
      toastOn: !!s.toast, toastMsg: s.toast,
      statusC: landscape ? 'transparent' : dark ? '#fff' : '#1B2433', indC: dark ? '#fff' : '#1B2433', indOp: landscape ? 0 : dark ? 0.8 : 0.25,
    }
  }
}
