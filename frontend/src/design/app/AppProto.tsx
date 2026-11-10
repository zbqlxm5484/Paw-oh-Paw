/* eslint-disable */
/**
 * Paw oh Paw 앱 v5 로직. 디자인 프로토타입 로직 원본을 바탕으로 목업 대신 API 데이터(props.data)를 쓰고,
 * 화면 이동은 주소(props.screen·nav·back)로 한다. 문구·색·배치 값은 원본 그대로.
 * 촬영: 디자인의 촬영 화면에서 촬영 버튼을 누르면 기기 카메라(파일 입력 capture)가 열린다.
 */
import * as camera from '../../app/camera'
import { AppReport } from './AppReport'
import { SessionThumb } from './SessionThumb'
import { ApiError } from '../../api/client'
import { BREEDS } from '../../api/labels'
import { DCLogic } from '../DCLogic'
import { ST, STEPS, allShotsFailed, type DDog, type DGait, type DRes } from '../adapter'
import type { ProtoProps } from '../DesignRoot'
import { EMPTY_PET, LIMB, SEX, SIZE, autoSize, baseOf as baseOf_, chk, desc, errMsg, fmtD, knee, petBody, pickSt, resultVals, seg, sessNo as sessNo_, short, valid as valid_, wkg } from '../shared'
import { AppView } from './AppView'
import { IntroBody } from './AppIntro'
import { Gait3dBody } from './AppGait3d'
import { DogBody, HomeBody, ReportsBody, type HomeRow, type WebDog, type WebHome, type WebReports } from './AppWebScreens'
import { isDemo } from '../../app/demoMode'
import { badgesOfDog, emrSearchText } from '../../app/emr'
import { LEGAL, TERM_LINKS, type LegalKind } from '../../legal/content'
import { HELP_CARDS, HELP_CONTACT } from '../help'

// 기기에만 남는 설정(백엔드에 알림 설정 저장 API 가 생기면 PATCH /me 로 옮긴다)
const NOTIF_ON_KEY = 'pp.notif.on', NOTIF_READ_KEY = 'pp.notif.read'
const lsGet = (k: string) => { try { return localStorage.getItem(k) } catch { return null } }
const lsSet = (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* 저장 못 해도 화면은 돈다 */ } }
const readKeys = (): string[] => { try { const a = JSON.parse(lsGet(NOTIF_READ_KEY) || '[]'); return Array.isArray(a) ? a : [] } catch { return [] } }
import './app-view.css'

/** 409 DOG_MODIFIED: 다른 담당자가 먼저 고쳤다. 목록은 다시 불러온 상태다(useDesignActions.updateDog) */
const DOG_MODIFIED_MSG = '다른 담당자가 먼저 수정했습니다. 최신 내용을 다시 불러왔으니 확인한 뒤 다시 저장해 주세요'

type Props = ProtoProps & { rootStyle?: React.CSSProperties }

export class AppProto extends DCLogic<Props, any> {
  static View = AppView
  state: any = {
    splash: false, joint: false, line: 0, sheet: null, toast: '', viaTab: true,
    li: { id: '', pw: '' }, so: { dev: '', name: '', email: '', id: '', pw: '', pw2: '' }, devChk: null as null | { code: string; org?: string; left?: number; err?: string }, signupBusy: false, to: [false, false, false, false],
    af: { name: '', email: '' }, pf: { cur: '', nw: '', nw2: '' }, saving: false,
    pet: EMPTY_PET, petMode: 'new', petId: null, delId: null, q: '',
    capDog: '', sessW: '', busy: false, repType: 'g', gait: 'trot', page: 0, filt: 'all', hv: 'today', by: '', pd: 'all', pdFrom: '', pdTo: '', rq: '', resShown: 50, pdfBusy: false, notifOn: lsGet(NOTIF_ON_KEY) !== '0', wf: { pw: '' }, withdrawing: false, notifRead: readKeys(), rotDone: false, rotAnim: false, repH: 0, camLive: false, recSec: -1, camLoading: false, pend: 0, loginBusy: false,
  }
  vids = new Set<HTMLVideoElement>()
  recTick: any; raf: any; t1: any; t2: any; tt: any; r1: any; r2: any; storyEl?: HTMLElement; lastMo = 0; moStart = 0
  componentDidMount() {
    // 로그인 전 첫 진입이면 스플래시(2.2초) 뒤 랜딩
    if (!this.props.data.loggedIn && (this.props.screen === 'landing' || this.props.screen === 'home')) this.startSplash()
    const loop = () => { this.frame(); this.raf = requestAnimationFrame(loop) }
    this.raf = requestAnimationFrame(loop)
    this.syncRoute()
    // QR·앱 링크로 촬영 화면에 바로 들어온 경우(화면 전환이 없어 componentDidUpdate 가 안 불린다)
    if (this.props.screen === 'capGuide') this.enterCapGuide()
  }
  /** 촬영 화면에 들어올 때: 가로 안내 애니메이션, 하단바 숨김, 카메라 미리 켜기 */
  enterCapGuide() { this.startRot(); void camera.setNavBarHidden(true); if (camera.canRecordInApp()) { this.setState({ camLoading: !camera.isLive() }); void camera.warm() } }
  componentDidUpdate(prev: Props) {
    if (prev.screen !== this.props.screen || prev.params !== this.props.params) {
      this.syncRoute()
      if (this.props.screen === 'capGuide') this.enterCapGuide()
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
    // 영상 첨부 화면: 방금 올린 영상만 보인다. 첫 그림이 나오기 전엔 숨겨 검은 칸이 안 보이게(배경은 베이지)
    if (this.props.screen === 'capReview' && this.lastFileUrl) {
      el.addEventListener('loadeddata', () => { el.style.opacity = '1' }, { once: true })
      el.src = this.lastFileUrl
    }
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
  rotAt = 0
  frame() {
    // 안전장치: 어떤 경로로 촬영 화면에 들어오든(QR·앱 링크·첫 진입) 가로 안내가 2.5초 넘게 남아 있으면 걷고 촬영 화면 준비를 한다
    if (this.props.screen === 'capGuide' && !this.state.rotDone && !this.state.splash) {
      const n = performance.now()
      if (!this.rotAt) this.rotAt = n
      else if (n - this.rotAt > 2500) { console.info('[capture] rotation hint stuck, forcing'); this.rotAt = 0; this.rotSeen = true; this.setState({ rotDone: true, rotAnim: true }); void camera.setNavBarHidden(true) }
    } else this.rotAt = 0
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
  devTimer: ReturnType<typeof setTimeout> | null = null
  /** 기기 번호를 입력하면 잠깐 기다렸다 서버에 확인해 기관명·남은 계정 수를 보여 준다 */
  checkDev(v: string) {
    if (this.devTimer) clearTimeout(this.devTimer)
    const code = v.trim()
    if (!code) return this.setState({ devChk: null })
    this.devTimer = setTimeout(async () => {
      try { const r = await this.props.auth.verifyDeviceCode(code); if (this.state.so.dev.trim() === code) this.setState({ devChk: { code, org: r.institution.name, left: r.remaining_accounts } }) }
      catch (e) { if (this.state.so.dev.trim() === code) this.setState({ devChk: { code, err: errMsg(e, '기기 번호를 확인하지 못했습니다') } }) }
    }, 500)
  }
  PATH: Record<string, string> = { splash: '/welcome', landing: '/welcome', story: '/intro', login: '/login', signupOrg: '/signup', home: '/', results: '/reports', my: '/my', account: '/account', notif: '/notifications', settings: '/settings', help: '/help', capSelect: '/capture', petNew: '/dogs/new' }
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
    // 측정 중인 회차가 있어도 반려견 선택 화면부터 보인다(다른 개를 찍을 수 있게). 이어서 할지는 촬영 시작 때 묻는다(11-06)
    this.setState({ capDog: cur.id, sessW: '' })
    this.nav('capSelect')
  }
  /** 회차 결과 화면의 보호자용·수의사용 PDF 버튼(보고서 화면의 PDF 받기와 같은 흐름) */
  savePdfOf = async (R: DRes | undefined, edition: 'OWNER' | 'VET') => {
    const rep = this.props.reports?.reports.find((x) => x.edition === edition)
    if (!R || !rep || rep.status !== 'DONE' || !rep.download_url) return this.toast(rep && rep.status === 'FAILED' ? '보고서를 만들지 못했습니다. 보고서 화면에서 다시 만들기를 눌러 주세요' : '보고서를 만드는 중입니다. 잠시 뒤 다시 눌러 주세요')
    if (isDemo()) return this.toast('체험 모드에서는 PDF를 받을 수 없습니다. 로그인하면 받을 수 있습니다')
    if (this.state.pdfBusy) return
    this.setState({ pdfBusy: true }); this.toast('PDF를 준비하는 중입니다')
    const name = `${R.measured_on.replace(/-/g, '').slice(2)} ${this.props.data.dogs.find((d) => d.id === R.dog)?.name ?? ''} 분석 결과 (${edition === 'VET' ? '수의사용' : '보호자용'})`
    try { const how = await this.props.openFile(rep.download_url, name); this.toast(how === 'shared' ? 'PDF를 저장할 곳을 골라 주세요' : 'PDF를 내려받는 중입니다') }
    catch { this.toast('PDF를 받지 못했습니다. 잠시 후 다시 시도해 주세요') }
    finally { this.setState({ pdfBusy: false }) }
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
    if (d && d.open && !this.freshStart) return d.open
    this.freshStart = false
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
        this.toast(out.warnings?.length ? out.warnings[0].message : `${out.seq_no}번째 영상을 첨부했습니다`)
      } catch (e) {
        this.toast(errMsg(e, '영상을 올리지 못했습니다. 잠시 후 다시 시도해 주세요'))
      } finally {
        this.setState((st: any) => ({ pend: Math.max(0, (st.pend || 0) - 1) }))
      }
    })
  }
  /** 갤러리에서 고른 여러 개를 차례로 올린다. 남은 칸(limit)만큼만 */
  addFiles = async (files: File[], limit: number) => {
    const use = files.slice(0, Math.max(0, limit))
    if (files.length > use.length) this.toast(`영상은 16개까지라 ${use.length}개만 첨부합니다`)
    for (const f of use) await this.addFile(f)
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
      for (const v of this.vids) if (v.isConnected && this.props.screen === 'capReview') { v.addEventListener('loadeddata', () => { v.style.opacity = '1' }, { once: true }); v.src = this.lastFileUrl }
      this.toast(out.warnings?.length ? out.warnings[0].message : `${out.seq_no}번째 영상을 첨부했습니다`)
      if (this.props.params.sessionId !== sid || this.props.screen !== 'capReview') this.nav('capReview', `/sessions/${sid}`, this.props.screen === 'capGuide')
    } catch (e) {
      this.toast(errMsg(e, '영상을 올리지 못했습니다. 잠시 후 다시 시도해 주세요'))
    } finally {
      this.setState({ busy: false })
    }
  }
  /** 선택 화면에서 '새로 시작'을 눌렀으면 아직 data 에 남은 예전 open 회차를 다시 쓰지 않는다 */
  freshStart = false
  goCapGuide = async () => {
    if (this.shots() >= 16) return this.toast('영상 16개를 모두 첨부했습니다')
    if (this.state.busy) return
    const d0 = this.props.data.dogs.find((x) => x.id === this.state.capDog)
    if (this.props.screen === 'capSelect' && d0?.open && !this.freshStart) return this.setState({ sheet: 'resume' })
    this.setState({ busy: true })
    try { const sid = await this.ensureSession(); this.nav('capGuide', `/sessions/${sid}/record`) }
    catch (e) { this.toast(errMsg(e, '회차를 시작하지 못했습니다')) }
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
    const homeDogs = shown.map((d) => { const all = results.filter((r) => r.dog === d.id); return { init: d.name[0], name: d.name, desc: desc(d), live: !!d.open, meta: all.length ? `마지막 측정 ${all[0].date} · ${all.length}회차` : '아직 측정 기록이 없습니다', open: () => this.openDog(d.id) } })

    // 주소의 반려견 id 가 없으면(지웠거나 다른 기관) 다른 반려견을 대신 보여 주지 않는다(none 상태로 안내)
    const D = this.props.params.dogId ? dogById(this.props.params.dogId) : dogs[0]
    let dd: any = { name: '', init: '', desc: '', tags: [], rows: [], hist: [], has: false, none: true, count: '', edit: () => {}, compare: () => {}, start: () => {} }
    if (!D && this.props.params.dogId && dogs.length) dd = { ...dd, name: '반려견을 찾을 수 없습니다', init: '?', desc: '지웠거나 이 기관의 반려견이 아닙니다' }
    if (D) {
      const all = results.filter((r) => r.dog === D.id), bId = baseOf(D), bR = results.find((r) => r.id === bId)
      dd = { name: D.name, init: D.name[0], desc: desc(D),
        tags: [SIZE[D.size] + (D.sizeManual ? ' · 직접 지정' : ''), SEX[D.sex || 'm']],
        rows: [{ k: '재활 시작일', v: D.rehab ? fmtD(D.rehab) : '미입력', sub: '' }, { k: '관심 다리', v: D.focus ? LIMB[D.focus] : '미선택', sub: '' },
          { k: '기준 회차', v: bR ? `${bR.date} · ${sessNo(bR)}회차` : '없음', sub: D.base ? '' : bR ? '가장 이른 회차로 자동 지정' : '' }, { k: '내부 메모', v: D.memo || '없음', sub: '' }],
        hist: all.map((r, i) => { const stt = ST[r.st]; return { title: `${sessNo(r)}회차 · ${r.date}`, sub: r.st === 'fail' ? `${wkg(r.w)} · 쓸 수 있는 통과 없음` : `${wkg(r.w)} · 유효 통과 ${r.ps[1]} · 모델 ${r.model}`, base: r.id === bId, rep: !!r.rep, canBase: r.st !== 'fail' && r.id !== bId,
          setBase: async (e: any) => { e.stopPropagation(); try { await this.props.actions.updateDog(D.id, { baseline_session_id: r.id, version: D.raw.version }); this.toast(`${r.date} 회차를 기준으로 정했습니다`) } catch (err) { this.toast(err instanceof ApiError && err.code === 'DOG_MODIFIED' ? DOG_MODIFIED_MSG : errMsg(err, '기준 회차를 바꾸지 못했습니다')) } },
          st: stt[0], bg: stt[1], c: stt[2], bt: i ? '1px solid #F2EFEA' : 'none', open: () => this.openRes(r.id) } }),
        has: all.length > 0, none: !all.length, count: all.length + '회차',
        edit: () => this.nav('petNew', `/dogs/${D.id}/edit`),
        compare: () => valid(D.id).length < 2 ? this.toast('유효한 회차가 2개 이상 있어야 비교할 수 있습니다') : (this.props.setUi({ cmp: 'base' }), this.nav('compare', `/dogs/${D.id}/compare`)),
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
        modelChanged: c.model_changed, modelMsg: `두 회차의 분석 모델이 다릅니다(${c.base.model_version ?? '-'} → ${c.target.model_version ?? '-'}). 분석 방식이 바뀌어 수치를 그대로 비교하기 어렵습니다.`,
        rows: cmpd.rows, ...cmpd.trend,
        focusNote: CD.focus ? `관심 다리(${LIMB[CD.focus]})를 맨 앞에 보여 드립니다.` : '관심 다리를 정하면 그 다리를 맨 앞에 보여 드립니다.' }
    }

    const reqOrg = [s.to[0], s.to[1], s.to[2]].every(Boolean)
    // 백엔드 규칙(schemas/auth.py): 아이디 영문 소문자·숫자·._- 4~50자, 비밀번호 8자 이상, 이름·이메일 필수. 기관은 기기 번호가 정한다
    const idOk = /^[a-z0-9._-]{4,50}$/.test(s.so.id), emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s.so.email.trim())
    const devOk = !!s.devChk && s.devChk.code === s.so.dev.trim() && !s.devChk.err
    const orgOk = reqOrg && devOk && !!s.so.name.trim() && emailOk && idOk && s.so.pw.length >= 8 && s.so.pw === s.so.pw2
    const setSo = (k: string) => (e: any) => { const v = e.target.value; this.setState((st: any) => ({ so: { ...st.so, [k]: v } })); if (k === 'dev') this.checkDev(v) }
    const devHint = !s.so.dev.trim() ? '측정 기기 뒷면 라벨에 적혀 있습니다.'
      : !s.devChk || s.devChk.code !== s.so.dev.trim() ? '기기 번호를 확인하는 중…'
      : s.devChk.err ? s.devChk.err : typeof s.devChk.left === 'number' ? `${s.devChk.org} · 가입할 수 있는 계정 ${s.devChk.left}개` : `${s.devChk.org} · 확인됐습니다`
    const devHc = s.devChk && s.devChk.code === s.so.dev.trim() && s.devChk.err ? '#C2412D' : s.devChk && s.devChk.code === s.so.dev.trim() ? '#2E7D4F' : '#5B6472'
    const notifOn = acct.notifOn ?? s.notifOn
    const setPet = (k: string) => (e: any) => { const v = e.target.value; this.setState((st: any) => ({ pet: { ...st.pet, [k]: v } })) }
    const setF = (g: string, k: string) => (e: any) => { const v = e.target.value; this.setState((st: any) => ({ [g]: { ...st[g], [k]: v } })) }
    const setLi = (k: string) => (e: any) => { const v = e.target.value; this.setState((st: any) => ({ li: { ...st.li, [k]: v } })) }
    const termRows = (key: string, labels: [string, boolean][]) => labels.map(([label, view], i) => ({ label, view, c: chk(s[key][i]), open: (e: any) => { e.stopPropagation(); this.nav('legal', `/legal/${TERM_LINKS[i] ?? 'terms'}`) }, toggle: () => this.setState((st: any) => { const a = [...st[key]]; a[i] = !a[i]; return { [key]: a } }) }))

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
    const anaStepNow = anaSess ? (this.props.sessionAna?.label ?? STEPS[Math.min(4, Math.floor(this.props.sessionAna?.p ?? 0))]) : (ana?.label ?? STEPS[anaFloor])
    const rep = this.props.reports?.reports.find((r) => r.edition === (s.repType === 'v' ? 'VET' : 'OWNER'))
    const bq = s.pet.breed.trim().replace(/\s/g, '')
    const bList = bq ? BREEDS.filter((b) => b.replace(/\s/g, '').includes(bq)).slice(0, 6) : []
    const bExact = BREEDS.includes(s.pet.breed)

    // 알림: 회차 상태에서 만든다(알림 API 없음)
    // 알림은 백엔드 API 가 없어 회차 상태로 만든다. 읽음은 기기에 key 로 남긴다(전체 확인 버튼·홈 종 점)
    const rawNotifs: { key: string; title: string; body: string; when: string; dot: string; open: () => void }[] = [
      ...(ana && anaDog ? [ana.status === 'MEASURING'
        ? { key: `ana:${ana.sessionId}:m`, title: `${anaDog.name} 촬영을 끝내지 않았습니다`, body: `영상 ${ana.n}개를 첨부해 두고 측정 종료를 누르지 않았습니다. 이어서 찍거나 측정을 끝내 주세요.`, when: '촬영 중', dot: '#D2601A', open: () => this.nav('capReview', `/sessions/${ana.sessionId}`) }
        : { key: `ana:${ana.sessionId}`, title: `${anaDog.name} 분석이 진행 중입니다`, body: `영상 ${ana.n}개의 관절점을 찾고 있습니다. 끝나면 알려 드리겠습니다.`, when: '진행 중', dot: '#D2601A', open: () => this.nav('analyzing', `/sessions/${ana.sessionId}/analyzing`) }] : []),
      ...results.slice(0, 6).map((r) => { const d = dogById(r.dog); return r.st === 'fail'
        ? { key: `res:${r.id}:fail`, title: `${d?.name ?? ''} 분석에 실패했습니다`, body: r.result?.fail_reason?.message || (allShotsFailed(r.result) ? '분석 서버가 영상을 처리하지 못했습니다. 잠시 후 다시 분석해 주세요.' : '쓸 수 있는 통과가 없었습니다. 다시 촬영해 주세요.'), when: r.date, dot: '#C9C4BC', open: () => this.openRes(r.id) }
        : { key: `res:${r.id}:${r.rep ? 'rep' : 'done'}`, title: `${d?.name ?? ''} ${r.rep ? '보고서가 만들어졌습니다' : '분석이 끝났습니다'}`, body: r.rep ? '보호자용·수의사용 보고서를 확인해 보세요.' : '회차 결과를 확인해 보세요.', when: r.date, dot: r.rep ? '#D2601A' : '#C9C4BC', open: () => this.openRes(r.id) } }),
    ]
    if (!rawNotifs.length) rawNotifs.push({ key: 'welcome', title: '가입을 환영합니다', body: '반려견을 등록하고 첫 보행 영상을 찍어 보세요.', when: '방금', dot: '#D2601A', open: this.goPetNew })
    const readSet = new Set<string>(s.notifRead)
    const markRead = (keys: string[]) => { const next = Array.from(new Set([...s.notifRead, ...keys])).slice(-200); lsSet(NOTIF_READ_KEY, JSON.stringify(next)); this.setState({ notifRead: next }) }
    const notifs = rawNotifs.map((n) => { const read = readSet.has(n.key); return { ...n, dot: read ? '#E2DCD3' : n.dot, tc: read ? '#5B6472' : '#1B2433', open: () => { markRead([n.key]); n.open() } } })
    const hasUnread = rawNotifs.some((n) => !readSet.has(n.key))

    // ── 웹과 같은 홈·반려견 차트·분석 결과 (AppWebScreens). 문턱값은 웹 config 와 같다(변동 7일, 대칭 지수 3%p) ──
    const now = new Date()
    const todayIso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
    const daysAgo = (iso: string) => Math.round((Date.parse(todayIso) - Date.parse(iso.slice(0, 10))) / 86400000)
    const ageOf = (d: DDog) => (d.birth ? `${now.getFullYear() - Number(d.birth)}살` : '나이 미입력')
    const prevValid = (r: DRes) => { const vv = valid(r.dog); const i = vv.findIndex((x) => x.id === r.id); return i >= 0 ? vv[i + 1] : undefined }
    const symChip = (r: DRes) => {
      if (r.st === 'fail' || r.sym == null) return { t: '—', bg: '#F2EFEA', c: '#8E949C' }
      const sv = r.sym, [bg, c] = sv >= 90 ? ['#DCEFE2', '#2E7A4F'] : sv >= 80 ? ['#FBEBC8', '#8A6100'] : ['#FBE0D9', '#C2412D']
      const p = prevValid(r), dv = p && p.sym != null ? sv - p.sym : 0
      return { t: `${sv}%`, bg, c, d: dv ? (dv > 0 ? `▲${dv}` : `▼${-dv}`) : undefined, dc: dv > 0 ? '#2E8B57' : '#C2412D' }
    }
    const stChip = (r: DRes) => ({ t: ST[r.st][0], bg: ST[r.st][1], c: ST[r.st][2] })
    const byOf = (r: DRes) => r.result?.staff?.name || '—'
    const trendOf = (dogId: string): WebDog['trend'] => {
      const vs = valid(dogId).filter((x) => x.sym != null).slice().reverse().slice(-8)
      if (!vs.length) return { has: false, pts: [], line: '', label: '', c: '', sym: null }
      const syms = vs.map((x) => x.sym as number), lo = Math.min(...syms) - 3, hi = Math.max(...syms) + 3
      const pts = vs.map((x, i) => ({ x: Math.round(24 + i * (276 / Math.max(1, vs.length - 1))), y: Math.round(84 - (((x.sym as number) - lo) / (hi - lo)) * 64), v: x.sym as number, t: short(x.date), cur: i === vs.length - 1 }))
      const diff = syms.length > 1 ? syms[syms.length - 1] - syms[syms.length - 2] : 0
      const [label, c] = syms.length === 1 ? ['첫 측정', '#7A808A'] : diff >= 3 ? ['좋아짐', '#2E8B57'] : diff <= -3 ? ['나빠짐', '#C2412D'] : ['비슷함', '#7A808A']
      return { has: true, pts, line: pts.map((p) => `${p.x},${p.y}`).join(' '), label, c, sym: syms[syms.length - 1] }
    }
    // 실패 회차라도 영상이 전부 분석 서버에서 실패했으면 다시 찍을 일이 아니다(서버 장애) → '분석 실패'
    const failChip = (r: DRes) => (r.status === 'FAILED' || allShotsFailed(r.result) ? { t: '분석 실패', bg: '#F2EFEA', c: '#5B6472' } : { t: '재촬영 필요', bg: '#FBE0D9', c: '#C2412D' })
    const changesOf = (d: DDog) => {
      const out: { t: string; bg: string; c: string }[] = []
      const srv = d.raw?.changes
      if (srv) {
        // 서버 변동(271, 최근 7일). 대칭 점수 차는 서버 delta 그대로. 수술 추가는 수술 배지(D+일)와 겹쳐 따로 띄우지 않는다
        const latest = results.find((x) => x.dog === d.id && x.loaded)
        for (const c of srv) {
          if (c.code === 'RESHOOT_NEEDED') {
            if (!latest || latest.st === 'fail') out.push(latest ? failChip(latest) : { t: '재촬영 필요', bg: '#FBE0D9', c: '#C2412D' })
            else out.push({ t: '일부 유효 · 재촬영 권장', bg: '#FAF1DF', c: '#9A6A12' })
          } else if (c.code === 'GAIT_BETTER' && c.delta != null) out.push({ t: `보행 좋아짐 +${c.delta}%p`, bg: '#E8F3EC', c: '#2E8B57' })
          else if (c.code === 'GAIT_WORSE' && c.delta != null) out.push({ t: `보행 나빠짐 −${-c.delta}%p`, bg: '#F8E7E3', c: '#C2412D' })
          else if (c.code === 'IMPORTANT_NOTE') out.push({ t: '중요 메모', bg: '#EEF1F6', c: '#4A5A78' })
        }
        return out.filter((x, i) => out.findIndex((y) => y.t === x.t) === i)
      }
      for (const r of results.filter((x) => x.dog === d.id && daysAgo(x.measured_on) <= 7)) {
        if (r.st === 'fail') out.push(failChip(r))
        else {
          if (r.st === 'part') out.push({ t: '일부 유효 · 재촬영 권장', bg: '#FAF1DF', c: '#9A6A12' })
          const p = prevValid(r)
          if (p && r.sym != null && p.sym != null && r.sym - p.sym >= 3) out.push({ t: `보행 좋아짐 +${r.sym - p.sym}%p`, bg: '#E8F3EC', c: '#2E8B57' })
          else if (p && r.sym != null && p.sym != null && p.sym - r.sym >= 3) out.push({ t: `보행 나빠짐 −${p.sym - r.sym}%p`, bg: '#F8E7E3', c: '#C2412D' })
        }
      }
      return out.filter((x, i) => out.findIndex((y) => y.t === x.t) === i)
    }
    const emrTxt = (d: DDog) => emrSearchText(d.raw)
    const badgeChips = (d: DDog) => badgesOfDog(d.raw).map((b) => (b.kind === 'surg' ? { t: b.t, bg: '#FCEEE3', c: '#A8481A' } : { t: b.t, bg: '#EEF1F6', c: '#4A5A78' }))
    const hvDogs = dogs.filter((d) => !qq || `${d.name} ${d.breed} ${d.memo} ${emrTxt(d)}`.includes(qq))
    const keepIds = new Set(hvDogs.map((d) => d.id))
    const todayRows: HomeRow[] = hvDogs.flatMap((d) => {
      const res = results.filter((r) => r.dog === d.id && r.measured_on === todayIso), live = !!ana && ana.dog === d.id
      if (!res.length && !live) return []
      const chips = [...(live ? [{ t: ana!.status === 'MEASURING' ? '촬영 중' : '분석 중', bg: '#FCEEE3', c: '#A8481A' }] : []), ...res.map((r) => (r.st === 'fail' ? failChip(r) : { t: `보행 측정 · 대칭 지수 ${r.sym ?? '—'}%`, bg: '#F1ECE5', c: '#5B6472' }))]
      const times = res.map((r) => r.time).filter(Boolean).sort()
      return [{ key: d.id, when: times[0] || '', name: d.name, sub: d.breed || '견종 미입력', chips: [...chips, ...badgeChips(d)], right: res.map(byOf).find((b) => b !== '—') || '', live, open: () => this.openDog(d.id) }]
    })
    // 분석 기간: 전체·오늘·최근 7일·최근 30일·직접 선택(시작~끝, 한쪽만 적어도 된다)
    const inPeriod = (iso: string) => {
      const d = iso.slice(0, 10)
      if (s.pd === 'today') return d === todayIso
      if (s.pd === '7' || s.pd === '30') return daysAgo(d) >= 0 && daysAgo(d) < Number(s.pd)
      if (s.pd === 'custom') return (!s.pdFrom || d >= s.pdFrom) && (!s.pdTo || d <= s.pdTo)
      return true
    }
    const analysisRows: HomeRow[] = results.filter((r) => keepIds.has(r.dog) && (!s.by || byOf(r) === s.by) && inPeriod(r.measured_on)).map((r) => { const d = dogById(r.dog)!; return { key: r.id, when: `${short(r.date)} ${r.time}`.trim(), name: d.name, sub: `${d.breed || '견종 미입력'} · ${sessNo(r)}회차`, chips: [], sym: symChip(r), st: stChip(r), right: byOf(r), open: () => this.openRes(r.id) } })
    // 정렬: 측정 중인 반려견이 맨 위, 나머지는 서버 순서(마지막 측정일 최신순, 측정 전은 아래, 같으면 최근 등록순)
    const isLive = (d: DDog) => !!d.open || (!!ana && ana.dog === d.id)
    const dogRows: HomeRow[] = [...hvDogs.filter(isLive), ...hvDogs.filter((d) => !isLive(d))].map((d) => {
      const all = results.filter((r) => r.dog === d.id), last = all[0], tr = trendOf(d.id)
      return { key: d.id, when: last ? `마지막 측정 ${short(last.date)}` : '측정 전', name: d.name, sub: `${SEX[d.sex || 'm']} · ${ageOf(d)} · ${d.breed || '견종 미입력'} · ${SIZE[d.size]}`,
        // 셋째 줄: 수술·질병 이름, 그 뒤에 조치가 필요한 변화(재촬영 필요·보행 좋아짐/나빠짐)
        chips: [...badgeChips(d), ...changesOf(d)], right: `분석 ${all.length}건`,
        sym: tr.has ? { t: `${tr.sym}%`, bg: '#F2EFEA', c: '#1B2433', d: tr.label, dc: tr.c } : undefined, open: () => this.openDog(d.id) }
    })
    const staffRows: HomeRow[] = (() => {
      const m = new Map<string, DRes[]>()
      for (const r of results.filter((x) => keepIds.has(x.dog))) { const b = byOf(r); m.set(b, [...(m.get(b) || []), r]) }
      return [...m.entries()].sort((a, b) => b[1].length - a[1].length).map(([name, rs]) => {
        const fails = rs.filter((r) => r.st === 'fail').length, dogN = new Set(rs.map((r) => r.dog)).size
        return { key: `staff:${name}`, when: `마지막 촬영 ${short(rs[0].date)}`, name: name === '—' ? '담당자 미기록' : name, sub: `반려견 ${dogN}마리`, chips: fails ? [{ t: `분석 실패 ${fails}건`, bg: '#FBE0D9', c: '#C2412D' }] : [], right: `분석 ${rs.length}건`, open: () => this.setState({ hv: 'analyses', by: name }) }
      })
    })()
    const retakeN = dogs.filter((d) => changesOf(d).some((c) => c.t === '재촬영 필요')).length
    const todayN = dogs.filter((d) => results.some((r) => r.dog === d.id && r.measured_on === todayIso) || (!!ana && ana.dog === d.id)).length
    const setHv = (k: string) => this.setState({ hv: k, by: '' })
    const webHome: WebHome = {
      today: fmtD(todayIso), acctName: acct.name, acctInit: (acct.name || '?').slice(0, 1), hasUnread, goNotif: () => this.nav('notif'), goMy: () => this.tab('my'), goPetNew: this.goPetNew, goCapture: () => this.goCapture(),
      cards: [{ label: '전체 반려견', n: dogs.length, unit: '마리', on: s.hv === 'dogs', pick: () => setHv('dogs') }, { label: '오늘 진행', n: todayN, unit: '마리', on: s.hv === 'today', pick: () => setHv('today') }, { label: '재촬영 필요', n: retakeN, unit: '마리', warn: true, pick: () => setHv('dogs') }],
      views: [['analyses', '분석'], ['dogs', '반려견'], ['staff', '촬영 담당자']].map(([key, label]) => ({ key, label, on: s.hv === key, pick: () => setHv(key) })),
      period: s.hv === 'analyses' ? {
        opts: [['all', '전체'], ['today', '오늘'], ['7', '7일'], ['30', '30일'], ['custom', '직접 선택']].map(([k, label]) => ({ label, on: s.pd === k, pick: () => this.setState({ pd: k }) })),
        custom: s.pd === 'custom', from: s.pdFrom, to: s.pdTo, max: todayIso,
        onFrom: (e: any) => this.setState({ pdFrom: e.target.value }), onTo: (e: any) => this.setState({ pdTo: e.target.value }),
      } : null,
      by: s.hv === 'analyses' && s.by ? { t: s.by === '—' ? '담당자 미기록' : s.by, clear: () => this.setState({ hv: 'staff', by: '' }) } : null,
      view: s.hv, q: s.q, onQ: (e: any) => { const v = e.target.value; this.setState({ q: v }) },
      rows: s.hv === 'today' ? todayRows : s.hv === 'analyses' ? analysisRows : s.hv === 'staff' ? staffRows : dogRows,
      empty: !dogs.length ? '첫 반려견을 등록해 주세요. 이름·견종·체중만 있으면 바로 보행 측정을 시작할 수 있습니다.' : s.hv === 'today' ? '오늘 진행한 분석 및 측정이 없습니다.' : qq ? `‘${qq}’ 에 맞는 ${s.hv === 'analyses' ? '분석이' : s.hv === 'staff' ? '담당자가' : '반려견이'} 없습니다.` : s.hv === 'analyses' ? (s.pd !== 'all' ? '이 기간에 한 분석이 없습니다.' : '아직 분석 결과가 없습니다.') : s.hv === 'staff' ? '아직 촬영한 분석이 없습니다.' : '등록된 반려견이 없습니다.',
      ana: { on: !!ana && li, thumb: ana ? <SessionThumb sessionId={ana.sessionId} w={44} h={44} /> : null, name: anaDog ? anaDog.name : '', label: ana && ana.status === 'MEASURING' ? ' 촬영 중' : ' 분석 중', hint: ana && ana.status === 'MEASURING' ? `영상 ${ana.n}개 첨부 · 측정 종료를 누르지 않았습니다. 눌러서 이어가기` : '', pct: Math.round(anaP / 5 * 100), step: ana?.label ?? STEPS[anaFloor], n: anaFloor + 1, measuring: !!ana && ana.status === 'MEASURING',
        open: () => ana && (ana.status === 'MEASURING' ? this.nav('capReview', `/sessions/${ana.sessionId}`) : this.nav('analyzing', `/sessions/${ana.sessionId}/analyzing`)) },
    }
    const webDog: WebDog = (() => {
      const bId = D ? baseOf(D) : null, bR = results.find((r) => r.id === bId)
      const all = D ? results.filter((r) => r.dog === D.id) : []
      return {
        none: !D, missing: !D && !!this.props.params.dogId && dogs.length > 0,
        name: D ? D.name : '반려견을 찾을 수 없습니다', init: D ? D.name[0] : '?', desc: D ? desc(D) : '', live: !!D?.open,
        tags: D ? [SIZE[D.size] + (D.sizeManual ? ' · 직접 지정' : ''), SEX[D.sex || 'm'], ageOf(D), ...(D.focus ? [`관심 다리 ${LIMB[D.focus]}`] : [])] : [],
        cells: D ? [{ k: '재활 시작일', v: D.rehab ? fmtD(D.rehab) : '미입력' }, { k: '관심 다리', v: D.focus ? LIMB[D.focus] : '미선택' }, { k: '기준 회차', v: bR ? `${bR.date} · ${sessNo(bR)}회차` : '없음', sub: D.base ? '직접 지정' : bR ? '가장 이른 회차' : '' }, { k: '측정 횟수', v: `${all.length}회차`, sub: all[0] ? `마지막 ${short(all[0].date)}` : '' }] : [],
        emr: { dogId: D?.id ?? null, kg: D?.kg ?? '' },
        memo: D?.memo || '없음', trend: D ? trendOf(D.id) : { has: false, pts: [], line: '', label: '', c: '', sym: null },
        hist: all.map((r, i) => ({ id: r.id, no: `${sessNo(r)}회차`, date: r.date, w: r.w && r.w !== '-' ? `${r.w}kg` : '—', pass: r.st === 'fail' ? '—' : `${r.ps[1]} / ${r.ps[0]}`, model: r.model, rep: r.rep ? '있음' : '—', base: r.id === bId, canBase: r.st !== 'fail' && r.id !== bId, st: ST[r.st][0], bg: ST[r.st][1], c: ST[r.st][2], open: () => this.openRes(r.id), setBase: dd.hist[i] ? dd.hist[i].setBase : () => {} })),
        count: `${all.length}회차`, back: this.back, edit: dd.edit, compare: dd.compare, start: dd.start,
      }
    })()
    // ── 보고서 탭: 보고서가 만들어진 회차만. 위에서 반려견 검색·고르기(반려견이 수백 마리여도 검색으로 좁힌다) ──
    const repOf = (r: DRes) => r.raw?.reports ?? null
    const hasRep = (r: DRes) => repOf(r)?.OWNER === 'DONE' || repOf(r)?.VET === 'DONE'
    const repRes = results.filter((r) => dogById(r.dog) && hasRep(r))
    const rq = (s.rq || '').trim()
    const dogMatch = (d: DDog) => !rq || `${d.name} ${d.breed}`.includes(rq)
    const repDogIds = new Set(repRes.map((r) => r.dog))
    const repDogs = dogs.filter((d) => repDogIds.has(d.id) && (dogMatch(d) || d.id === s.filt))
    const repRows = repRes.filter((r) => (s.filt === 'all' ? dogMatch(dogById(r.dog)!) : r.dog === s.filt))
    const openRepOf = (id: string, t: 'g' | 'v') => { this.setState({ repType: t }); this.nav('report', `/sessions/${id}/report`) }
    const webReports: WebReports = {
      total: repRes.length,
      q: s.rq, onQ: (e: any) => this.setState({ rq: e.target.value, resShown: 50 }),
      chips: [{ id: 'all', init: '전체', name: '전체' }, ...repDogs.map((d) => ({ id: d.id, init: d.name.slice(0, 1), name: d.name }))].map((c) => ({ ...c, on: s.filt === c.id, pick: () => this.setState({ filt: c.id, resShown: 50 }) })),
      rows: repRows.slice(0, s.resShown).map((r) => {
        const d = dogById(r.dog)!, rp = repOf(r)
        return { id: r.id, thumb: <SessionThumb sessionId={r.id} w={52} h={44} />, name: d.name, when: `${r.date} · ${sessNo(r)}회차`, sub: `${d.breed || '견종 미입력'}${r.sym != null && r.st !== 'fail' ? ` · 대칭 지수 ${r.sym}%` : ''}`,
          owner: rp?.OWNER === 'DONE', vet: rp?.VET === 'DONE', openOwner: () => openRepOf(r.id, 'g'), openVet: () => openRepOf(r.id, 'v') }
      }),
      more: repRows.length > s.resShown ? `더 보기 (${repRows.length - s.resShown}건 남음)` : '', loadMore: () => this.setState({ resShown: s.resShown + 50 }),
      empty: !repRes.length ? '아직 만들어진 보고서가 없습니다. 분석이 끝나면 보고서가 자동으로 만들어집니다.' : rq ? `‘${rq}’ 에 맞는 반려견의 보고서가 없습니다.` : '이 반려견의 보고서가 없습니다.',
    }

    return {
      introBody: <IntroBody i={{ showBack: !li || !s.viaTab, back: this.back, titlePad: !li || !s.viaTab ? 0 : 12, bottom: showTabs ? 96 : 0,
        cta: li ? { label: '보행 분석 시작하기', go: () => this.goCapture() } : { label: '기관 계정 만들기', go: () => this.nav('signupOrg') }, login: li ? undefined : () => this.nav('login') }} />,
      gait3dBody: sc === 'gait3d' ? (() => {
        const RD3 = R ? dogById(R.dog) : undefined
        return <Gait3dBody result={R?.result} name={RD3?.name ?? ''} when={R ? `${R.date} · ${sessNo(R)}회차` : ''} size={RD3?.size ?? 'M'} sym={R?.sym ?? null} back={this.back} />
      })() : null,
      go3d: () => { if (R) this.nav('gait3d', `/sessions/${R.id}/3d`) }, go3dOn: !!R && R.st !== 'fail' && !!R.result,
      homeBody: <HomeBody h={webHome} />, dogBody: <DogBody d={webDog} />, resultsBody: <ReportsBody r={webReports} />,
      rootStyle: this.props.rootStyle || {},
      isSplash: sc === 'splash', isLanding: sc === 'landing', isLogin: sc === 'login', isSignupOrg: sc === 'signupOrg',
      isHome: sc === 'home', isDog: sc === 'dog', isPetNew: sc === 'petNew', isNotif: sc === 'notif', isStory: sc === 'story', isCapSelect: sc === 'capSelect', isCapGuide: sc === 'capGuide',
      isCapReview: sc === 'capReview', isAnalyzing: sc === 'analyzing', isResults: sc === 'results', isDetail: sc === 'detail', isGait3d: sc === 'gait3d', isReport: sc === 'report', isCompare: sc === 'compare', isMy: sc === 'my', isAccount: sc === 'account', isLegal: sc === 'legal', isSettings: sc === 'settings', isHelp: sc === 'help', legal: LEGAL[(this.props.params.legal as LegalKind) in LEGAL ? (this.props.params.legal as LegalKind) : 'support'],
      vid: this.vid, storyRef: this.storyRef, repBox: this.repBox, back: this.back,
      jointOp: s.joint ? 1 : 0, jointTr: s.joint ? 'opacity 0.5s ease-out' : 'none', replaySplash: () => this.startSplash(),
      lines: [], // 랜딩 영상 위 문구(반려견의 걸음을·더욱 정확하게·Paw oh Paw)는 띄우지 않는다
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
      loginSub: '동물병원·재활센터 계정으로 로그인합니다.', loginIdLabel: '아이디', loginIdPh: '아이디',
      orgFields: [
        { label: '디바이스 번호', ph: '예) PP-2410-0381', type: 'text', val: s.so.dev, on: setSo('dev'), hint: devHint, hc: devHc }],
      orgAcctFields: [
        { label: '담당자 이름', ph: '예) 김수의', type: 'text', val: s.so.name, on: setSo('name') },
        { label: '이메일', ph: '비밀번호를 잊었을 때 씁니다', type: 'email', val: s.so.email, on: setSo('email'), hint: s.so.email && !emailOk ? '이메일 형식이 아닙니다' : false, hc: '#C2412D' },
        { label: '아이디', ph: '영문 소문자·숫자 4자 이상', type: 'text', val: s.so.id, on: setSo('id'), hint: s.so.id && !idOk ? '영문 소문자·숫자·._- 로 4~50자' : false, hc: '#C2412D' },
        { label: '비밀번호', ph: '8자 이상', type: 'password', val: s.so.pw, on: setSo('pw'), hint: s.so.pw && s.so.pw.length < 8 ? '8자 이상이어야 합니다' : false, hc: '#C2412D' },
        { label: '비밀번호 확인', ph: '한 번 더 입력', type: 'password', val: s.so.pw2, on: setSo('pw2'), hint: s.so.pw2 && s.so.pw !== s.so.pw2 ? '비밀번호가 다릅니다' : false, hc: '#C2412D' }],
      allOrgC: chk(s.to.every(Boolean)), allOrgToggle: () => this.setState((st: any) => ({ to: st.to.map(() => !st.to.every(Boolean)) })),
      termsOrg: termRows('to', [['[필수] 서비스 이용약관', true], ['[필수] 개인정보 수집 및 이용', true], ['[필수] 측정 기기 연동 및 위치정보 이용', true], ['[선택] 마케팅 정보 수신', true]]),
      signOrgBg: orgOk ? '#D2601A' : '#C3C8CF',
      doSignupOrg: async () => {
        if (!orgOk) return this.toast(!reqOrg ? '필수 약관에 동의해 주세요' : !devOk ? (s.devChk && s.devChk.err ? s.devChk.err : '기기 번호를 확인해 주세요') : (s.so.pw2 && s.so.pw !== s.so.pw2) ? '비밀번호가 서로 다릅니다' : '입력하지 않았거나 형식이 맞지 않는 항목이 있습니다')
        if (s.signupBusy) return
        this.setState({ signupBusy: true })
        try {
          // 약관 동의(192): 필수 셋은 orgOk 에서 확인했고, 버전은 약관 본문의 갱신일
          const terms = { version: LEGAL.terms.updated, service: true, privacy: true, device_location: true, marketing: !!s.to[3] }
          await this.props.auth.signup({ code: s.so.dev.trim(), login_id: s.so.id.trim(), password: s.so.pw, name: s.so.name.trim(), email: s.so.email.trim(), terms })
          this.toast(`${s.devChk?.org ?? '기관'} 담당자로 가입했습니다`)
          this.setState({ so: { dev: '', name: '', email: '', id: '', pw: '', pw2: '' }, devChk: null, to: [false, false, false, false], viaTab: true })
          this.props.nav('/', { replace: true })
        } catch (e) { this.toast(errMsg(e, '가입하지 못했습니다. 잠시 후 다시 시도해 주세요.')) }
        finally { this.setState({ signupBusy: false }) }
      },

      acctKind: '기관', acctName: acct.name, acctInit: (acct.name || '?').slice(0, 1),
      goNotif: () => this.nav('notif'), tabMy: () => this.tab('my'), tabHome: () => this.tab('home'), tabResults: () => this.tab('results'), tabStory: () => this.tab('story'), tabCapture: () => this.tab('capSelect'),
      hasDogs: dogs.length > 0, noDogs: !dogs.length, dogCount: dogs.length + '마리',
      q: s.q, onQ: (e: any) => { const v = e.target.value; this.setState({ q: v }) }, homeDogs, noMatch: !!qq && !shown.length,
      goPetNew: this.goPetNew, goCapture: () => this.goCapture(), dd,
      anaOn: !!ana && li && sc !== 'analyzing', anaThumb: ana ? <SessionThumb sessionId={ana.sessionId} w={44} h={44} /> : null, goAnalyzing: () => ana && (ana.status === 'MEASURING' ? this.nav('capReview', `/sessions/${ana.sessionId}`) : this.nav('analyzing', `/sessions/${ana.sessionId}/analyzing`)), anaMeasuring: !!ana && ana.status === 'MEASURING', anaLabel: ana && ana.status === 'MEASURING' ? ' 촬영 중' : ' 분석 중', anaHint: ana && ana.status === 'MEASURING' ? `영상 ${ana.n}개 첨부 · 측정 종료를 누르지 않았습니다. 눌러서 이어가기` : '', anaName: anaSess ? anaSess.dog.name : (anaDog ? anaDog.name : ''), anaPct: anaPctNow, anaN: anaFloor + 1, anaStep: anaStepNow,
      // 발자국 각도: 홀수 번째는 오른쪽 위로 조금 더 틀어 한 방향으로만 향하지 않게 섞는다
      prints: (() => { const ph = Math.floor(Date.now() / 420) % 11; return Array.from({ length: 8 }, (_, i) => { const on = ph <= 8 ? i < ph : ph === 9; const jx = [0, 6, -8, 4, -4, 10, -2, 5][i], jr = -23 + [-6, 22, -10, 28, -4, 18, -12, 25][i]; return { x: (i % 2 ? 236 : 118) + jx * 2 + Math.round(Math.sin(i * 0.9) * 22), y: 656 - i * 68 + (i % 2 ? 10 : 0), r: jr, op: on ? 1 : 0, s: on ? 1 : 0.7 } }) })(),

      petTitle: s.petMode === 'edit' ? '반려견 정보 수정' : '반려견 등록', petCta: s.petMode === 'edit' ? '저장하기' : '등록하기',
      petFields: [
        { label: '이름', ph: '예) 보리', val: s.pet.name, on: setPet('name') },
        { label: '견종', ph: '견종을 입력하면 목록이 뜹니다', val: s.pet.breed, on: setPet('breed'), showSug: !!bq && !bExact, noSug: !!bq && !bExact && !bList.length,
          sugs: bList.map((name, i) => ({ name, bt: i ? '1px solid #F2EFEA' : 'none', pick: () => this.setState((st: any) => ({ pet: { ...st.pet, breed: name } })) })) },
        { label: '체중 (kg)', ph: '예) 28.4', val: s.pet.kg, on: setPet('kg') },
        { label: '출생연도 (선택)', ph: '예) 2019', val: s.pet.birth, on: setPet('birth') }],
      sexes: Object.entries(SEX).map(([k, label]) => ({ label, ...pickSt(s.pet.sex === k), pick: () => this.setState((st: any) => ({ pet: { ...st.pet, sex: k } })) })),
      sizes: Object.entries(SIZE).map(([k, label]) => ({ label, ...pickSt((s.pet.size || autoSz) === k), pick: () => this.setState((st: any) => ({ pet: { ...st.pet, size: st.pet.size === k ? null : k } })) })),
      sizeNote: s.pet.size ? '직접 선택 · 다시 누르면 자동 분류' : '견종·체중으로 자동 분류됩니다',
      limbs: Object.entries(LIMB).map(([k, label]) => ({ label, ...pickSt(s.pet.focus === k), pick: () => this.setState((st: any) => ({ pet: { ...st.pet, focus: st.pet.focus === k ? null : k } })) })),
      petRehab: s.pet.rehab, onRehab: setPet('rehab'), petMemo: s.pet.memo, onMemo: setPet('memo'),
      petBg: s.pet.name && s.pet.breed && s.pet.kg ? '#D2601A' : '#C3C8CF',
      doPetNew: async () => {
        if (!s.pet.name || !s.pet.breed || !s.pet.kg) return this.toast('이름·견종·체중을 입력해 주세요')
        if (s.busy) return
        const kg = Number(s.pet.kg)
        if (!/^\d+(\.\d+)?$/.test(s.pet.kg.trim()) || !(kg >= 0.5 && kg <= 100)) return this.toast('체중은 0.5~100kg 사이 숫자로 입력해 주세요')
        const by = s.pet.birth.trim(), yNow = new Date().getFullYear() // 11-09 QA: 미래 출생 연도가 등록됐다(웹 petInputError 와 같은 규칙)
        if (by && !(/^\d{4}$/.test(by) && +by >= 1990 && +by <= yNow)) return this.toast(`출생 연도는 1990~${yNow} 사이 네 자리로 입력해 주세요`)
        this.setState({ busy: true })
        try {
          if (s.petMode === 'edit') { const cur = this.props.data.dogs.find((x) => x.id === s.petId); await this.props.actions.updateDog(s.petId, { ...petBody(s.pet), version: cur ? cur.raw.version : 0 }); this.back(); this.toast('저장했습니다') }
          else { const d = await this.props.actions.createDog(petBody(s.pet)); this.nav('dog', `/dogs/${d.id}`, true); this.toast(`${s.pet.name} 등록을 마쳤습니다`) }
        } catch (e) { this.toast(e instanceof ApiError && e.code === 'DOG_MODIFIED' ? DOG_MODIFIED_MSG : e instanceof ApiError && e.fields.length ? `${e.message} (${e.fields.map((f) => f.field).join(', ')})` : errMsg(e, '저장하지 못했습니다')) }
        finally { this.setState({ busy: false }) }
      },

      notifs, hasUnread, readAll: () => { markRead(rawNotifs.map((n) => n.key)); this.toast('알림을 모두 확인했습니다') },

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
      fromGallery: async () => { if (shots >= 16) return this.toast('영상 16개를 모두 첨부했습니다'); const fs = await this.props.pickFile(false); await this.addFiles(fs, 16 - shots) },
      goCapGuide: this.goCapGuide,
      capDogName: capD.name || '',
      slots: Array.from({ length: 16 }, (_, i) => { const done = i < shots, next = i === shots; const sh = [...(this.props.session?.shots ?? [])].sort((a: any, b: any) => a.seq_no - b.seq_no)[i]; return { n: i + 1, done, next, shot: done ? sh : undefined, bg: done ? '#141B22' : next ? '#FCEEE3' : '#F4F1EC', bs: next ? 'dashed' : 'solid', bd: done ? '#141B22' : next ? '#D2601A' : '#ECE8E2', nc: done ? 'rgba(255,255,255,.75)' : next ? '#B4501A' : '#A0A7B2', cur: next ? 'pointer' : 'default', tap: next ? this.goCapGuide : () => {} } }),
      shotN: shots, shotPct: Math.round(shots / 16 * 100), moreOp: shots >= 16 ? 0.4 : 1,
      shotHint: s.busy ? '영상을 올리는 중이에요…' : shots >= 16 ? '16개를 모두 첨부했습니다. 분석을 시작해 주세요.' : `${shots + 1}번째 영상을 이어서 찍어 주세요. 16개를 모두 채우면 결과가 더 정확합니다.`,
      rotHint: !s.rotDone, rotDone: !!s.rotDone, rotDeg: s.rotAnim ? 90 : 0,
      // 촬영 화면 영상 칸: 앱 안 카메라를 쓰면 견본 영상 없이 카메라만
      capPrevOn: sc === 'capReview' && !!this.lastFileUrl, // 앱 안 녹화를 못 쓰는 기기에서는 샘플 영상을 틀지 않고 안내 문구만(11-06, 실기기에서 다른 개 썸네일이 보여 헷갈림)
      capVidSrc: undefined, capVidPoster: undefined, noInAppCam: !camera.canRecordInApp(),
      camLoading: !!s.camLoading, camOp: s.camLoading ? 0 : 1,
      recTime: `영상 ${Math.min(16, shots + (s.pend || 0) + 1)}/16 · ${s.recSec >= 0 ? `00:${String(Math.min(99, s.recSec)).padStart(2, '0')} 녹화 중` : '00:00 / 00:04'}`, recPillBg: s.busy || s.recSec >= 0 ? '#C2412D' : 'rgba(14,18,23,.55)', recDot: s.busy || s.recSec >= 0 ? '#fff' : '#E5604D',
      recBtnS: s.busy || s.recSec >= 0 ? 30 : 62, recBtnR: s.busy || s.recSec >= 0 ? 8 : 31,
      capHint: s.busy ? '영상을 올리는 중입니다' : s.recSec < 0 && s.pend > 0 ? `앞 영상 ${s.pend}개를 올리는 중입니다. 바로 다음 영상을 찍어도 됩니다` : s.recSec >= 0 ? '반려견이 화면을 다 지나가면 버튼을 다시 눌러 멈춰 주세요' : s.camLive ? '점선 안에 반려견 옆모습이 들어오게 맞추고 촬영 버튼을 눌러 주세요' : '촬영 버튼을 누르면 카메라가 열립니다. 점선 안에 반려견 옆모습이 들어오게 맞춰 주세요',
      // 촬영 버튼: 기기 카메라(파일 입력 capture)
      toggleRec: async () => {
        if (s.busy) return
        if (camera.isRecording()) {
          clearInterval(this.recTick); this.setState({ recSec: -1 })
          const f = await camera.stopRecording()
          const total = this.shots() + (this.state.pend || 0) + (f ? 1 : 0)
          this.queueUpload(f)
          // 16번째까지 찍었으면 촬영 화면을 닫는다(카메라도 꺼진다). 남은 영상은 첨부 목록 화면에서 계속 올라간다
          const sid = this.sessionId()
          if (total >= 16 && sid) { this.toast('영상 16개를 모두 찍었습니다'); this.nav('capReview', `/sessions/${sid}`, true); setTimeout(() => camera.stopPreview(), 0) }
          return
        }
        if (shots + (s.pend || 0) >= 16) return this.toast('영상 16개를 모두 찍었습니다. X 를 눌러 첨부 목록으로 가 주세요')
        // 앱 안 카메라가 켜져 있으면 바로 녹화, 아니면 기기 카메라 앱
        if (s.camLive && camera.startRecording()) {
          const t0 = Date.now(); this.setState({ recSec: 0 })
          this.recTick = setInterval(() => this.setState({ recSec: Math.floor((Date.now() - t0) / 1000) }), 250)
          return
        }
        const [f] = await this.props.pickFile(true); await this.addFile(f ?? null)
      },
      startAna: async () => {
        const sid = this.sessionId()
        if (!shots || !sid) return this.toast('영상을 1개 이상 첨부해 주세요')
        if (s.busy) return
        this.setState({ busy: true })
        try { await this.props.actions.completeSession(sid); this.nav('analyzing', `/sessions/${sid}/analyzing`, true) }
        catch (e) { this.toast(errMsg(e, '분석을 시작하지 못했습니다')) }
        finally { this.setState({ busy: false }) }
      },

      filters: [{ id: 'all', label: '전체' }, ...dogs.map((d) => ({ id: d.id, label: d.name }))].map((f) => { const on = s.filt === f.id; return { label: f.label, bg: on ? '#1B2433' : '#fff', c: on ? '#fff' : '#3A4250', bd: on ? '#1B2433' : '#ECE8E2', pick: () => this.setState({ filt: f.id }) } }),
      resList: filtDogs.map((r, i) => ({ name: dogById(r.dog)!.name, when: `${r.date} · ${sessNo(r)}회차`, st: ST[r.st][0], bg: ST[r.st][1], c: ST[r.st][2], sym: r.st === 'fail' ? (r.status === 'FAILED' || allShotsFailed(r.result) ? '분석 실패' : '다시 촬영 필요') : `유효 통과 ${r.ps[1]}`, bt: i ? '1px solid #F2EFEA' : 'none', thumb: <SessionThumb sessionId={r.id} w={52} h={44} />, open: () => this.openRes(r.id) })),
      hasRes: filtDogs.length > 0, noRes: !filtDogs.length,
      rd, retake: () => { if (R) this.goCapture(R.dog) },
      gaitSegs: seg([['walk', '평보'], ['trot', '속보']], G, (k) => this.setState({ gait: k })), gaitName: rd.gaitName,
      openRep: () => { if (!R) return; this.setState({ repType: 'g' }); this.nav('report', `/sessions/${R.id}/report`) },
      openCompare: () => { if (!R) return; if (valid(R.dog).length < 2) return this.toast('유효한 회차가 2개 이상 있어야 비교할 수 있습니다'); this.props.setUi({ cmp: 'base' }); this.nav('compare', `/dogs/${R.dog}/compare`) },
      partMsg: R?.result?.notices?.[0]?.message || '일부 통과에서 다리가 가려지거나 뛰어서 해당 통과를 제외하고 계산했습니다.',
      rp, isRepG: s.repType === 'g',
      // 보고서 본문: 웹 보고서와 같은 구성(보호자용·수의사용)
      repBody: R ? (() => {
        const RD = dogById(R.dog)
        const vs = valid(R.dog).slice().reverse(), at = vs.findIndex((x) => x.id === R.id)
        const symHist = vs.slice(0, at >= 0 ? at + 1 : vs.length).filter((x) => x.sym != null).map((x) => [x.measured_on.slice(5), x.sym as number] as [string, number])
        const bId = RD ? baseOf(RD) : null, bR = results.find((x) => x.id === bId)
        const vsBase = bR && bR.id !== R.id && bR.sym != null && R.sym != null ? { d: R.sym - bR.sym, date: bR.measured_on.slice(5) } : null
        return <AppReport kind={s.repType === 'v' ? 'v' : 'g'} result={R.result} dogName={RD?.name ?? ''} dogSize={RD?.size ?? 'M'} focus={RD?.focus ?? null}
          sym={R.sym} symHist={symHist} vsBase={vsBase} passes={R.ps} excluded={R.ex} vet={this.props.vetReport} />
      })() : null, isRepV: s.repType === 'v', repKind: s.repType === 'v' ? '보행 분석 보고서 · 수의사용' : '보행 분석 보고서 · 보호자용',
      repStatus: R ? this.props.reportStatus(rep, R.model) : '',
      repSegs: seg([['g', '보호자용'], ['v', '수의사용']], s.repType, (k) => this.setState({ repType: k })),
      regenRep: async () => { if (!R || !rep) return this.toast('아직 보고서가 없습니다'); try { await this.props.actions.regenerateReport(R.id, rep.id); this.toast('보고서를 다시 만들고 있습니다') } catch (e) { this.toast(errMsg(e, '지금은 다시 만들 수 없습니다')) } },
      // 회차 결과 화면에서 바로 PDF(11-06): 보고서 화면을 한 번 더 거치지 않게
      savePdfG: () => this.savePdfOf(R, 'OWNER'), savePdfV: () => this.savePdfOf(R, 'VET'),
      saveRep: async () => {
        if (!rep || rep.status !== 'DONE' || !rep.download_url) return this.toast(rep && rep.status === 'FAILED' ? '보고서를 만들지 못했습니다. 다시 만들기를 눌러 주세요' : '보고서를 만드는 중입니다. 잠시 뒤 다시 눌러 주세요')
        if (isDemo()) return this.toast('체험 모드에서는 PDF를 받을 수 없습니다. 로그인하면 받을 수 있습니다')
        if (s.pdfBusy) return
        this.setState({ pdfBusy: true }); this.toast('PDF를 준비하는 중입니다')
        // 파일명은 웹과 같게: "261108 보리 분석 결과 (보호자용)"
        const name = `${(R?.measured_on ?? '').replace(/-/g, '').slice(2)} ${R ? (dogById(R.dog)?.name ?? '') : ''} 분석 결과 (${s.repType === 'v' ? '수의사용' : '보호자용'})`
        try { const how = await this.props.openFile(rep.download_url, name); this.toast(how === 'shared' ? 'PDF를 저장할 곳을 골라 주세요' : 'PDF를 내려받는 중입니다') }
        catch { this.toast('PDF를 받지 못했습니다. 잠시 후 다시 시도해 주세요') }
        finally { this.setState({ pdfBusy: false }) }
      },

      cp, cmpSegs: seg([['base', '기준 회차 대비'], ['prev', '직전 회차 대비']], this.props.ui.cmp, (k) => this.props.setUi({ cmp: k as 'base' | 'prev' })),
      trendKs: [['rom', '무릎 가동 범위'], ['stride', '걸음 길이'], ['stance', '입각기 비율'], ['sym', '대칭 지수']].map(([k, label]) => { const on = this.props.ui.tk === k; return { label, bg: on ? '#1B2433' : '#fff', c: on ? '#fff' : '#3A4250', bd: on ? '#1B2433' : '#ECE8E2', pick: () => this.props.setUi({ tk: k }) } }),

      isOrg, isUser: false, myName: acct.name, myDev: acct.dev || '-',
      goAccount: () => this.nav('account'), help: () => this.nav('help'), settings: () => this.nav('settings'), goSupport: () => this.nav('legal', '/legal/support'),
      settingRows: [
        { label: '기본 정보', right: acct.name, on: () => this.nav('account') },
        { label: '비밀번호 변경', right: '', on: () => this.setState({ sheet: 'pw', pf: { cur: '', nw: '', nw2: '' } }) },
        { label: '이용약관', right: '', on: () => this.nav('legal', '/legal/terms') },
        { label: '개인정보 처리방침', right: '', on: () => this.nav('legal', '/legal/privacy') },
        { label: '서비스 소개', right: '', on: () => this.nav('story') },
      ],
      helpCards: HELP_CARDS, helpContact: HELP_CONTACT.map((c) => ({ ...c, open: () => { if (c.href) window.location.href = c.href } })),
      helpLinks: [{ label: '고객센터 안내 전체 보기', on: () => this.nav('legal', '/legal/support') }, { label: '서비스 소개', on: () => this.nav('story') }],
      myDogs: dogs.map((d) => ({ init: d.name[0], name: d.name, desc: desc(d) + ' · ' + SEX[d.sex || 'm'], edit: () => this.nav('petNew', `/dogs/${d.id}/edit`), del: () => this.setState({ sheet: 'del', delId: d.id }) })),
      myDogCount: dogs.length + '마리',
      // 알림 설정: 서버가 notif_on 을 주면(192) 그 값이 기준이고 PATCH 로 저장한다. 예전 서버면 이 기기에만 둔다
      tgBg: notifOn ? '#D2601A' : '#DDD7CE', tgX: notifOn ? 22 : 2, toggleNotif: () => {
        const next = !notifOn
        lsSet(NOTIF_ON_KEY, next ? '1' : '0'); this.setState({ notifOn: next })
        if (acct.notifOn !== undefined) this.props.auth.updateMe({ notif_on: next }).catch((e) => this.toast(errMsg(e, '알림 설정을 저장하지 못했습니다')))
      },
      // 회원 탈퇴(192): 비밀번호 확인 시트 → DELETE /auth/me → 로그아웃. 기관의 마지막 계정(409 LAST_ACCOUNT)·비밀번호 오류는 서버 문구 그대로
      askWithdraw: () => this.setState({ sheet: 'withdraw', wf: { pw: '' } }),
      fWdPw: s.wf.pw, onWdPw: setF('wf', 'pw'), withdrawOp: s.withdrawing ? 0.55 : 1,
      confirmWithdraw: async () => {
        if (!s.wf.pw) return this.toast('현재 비밀번호를 입력해 주세요')
        if (s.withdrawing) return
        this.setState({ withdrawing: true })
        try { await this.props.auth.withdraw(s.wf.pw); this.setState({ sheet: null, wf: { pw: '' }, li: { id: '', pw: '' } }); this.toast('탈퇴했습니다. 그동안 이용해 주셔서 감사합니다'); this.props.nav('/welcome', { replace: true }) }
        catch (e) { this.toast(errMsg(e, '탈퇴하지 못했습니다')) }
        finally { this.setState({ withdrawing: false }) }
      },
      askLogout: () => this.setState({ sheet: 'logout' }),
      acctRows: [['계정 유형', '기관 회원'], ['기관명', acct.name], ['담당자', acct.staffName || '-'], ['이메일', acct.email || '-'], ['아이디', acct.id || '-'], ['기관 주소', acct.loc || '-'], ['디바이스 번호', acct.dev || '-']].map(([k, v], i) => ({ k, v, bt: i ? '1px solid #F2EFEA' : 'none' })),
      // 기본 정보 수정(이름·이메일)과 비밀번호 변경은 아래 시트에서. 서버 오류 문구는 그대로 보여 준다
      editAcct: () => this.setState({ sheet: 'acct', af: { name: acct.staffName, email: acct.email } }),
      openPw: () => this.setState({ sheet: 'pw', pf: { cur: '', nw: '', nw2: '' } }),
      fAcctName: s.af.name, fAcctEmail: s.af.email, onAcctName: setF('af', 'name'), onAcctEmail: setF('af', 'email'),
      fPwCur: s.pf.cur, fPwNew: s.pf.nw, fPwNew2: s.pf.nw2, onPwCur: setF('pf', 'cur'), onPwNew: setF('pf', 'nw'), onPwNew2: setF('pf', 'nw2'),
      pwHint: s.pf.nw && s.pf.nw.length < 8 ? '8자 이상으로 입력해 주세요' : s.pf.nw2 && s.pf.nw !== s.pf.nw2 ? '새 비밀번호가 서로 다릅니다' : '',
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
        try { await this.props.auth.updateMe(body); this.setState({ sheet: null }); this.toast('기본 정보를 저장했습니다') }
        catch (e) { this.toast(e instanceof ApiError && e.code === 'CONTRACT_EXPIRED' ? '계약이 끝나 정보를 바꿀 수 없습니다' : errMsg(e, '저장하지 못했습니다')) }
        finally { this.setState({ saving: false }) }
      },
      savePw: async () => {
        const { cur, nw, nw2 } = s.pf
        if (!cur || !nw || !nw2) return this.toast('비밀번호를 모두 입력해 주세요')
        if (nw.length < 8) return this.toast('새 비밀번호는 8자 이상이어야 합니다')
        if (nw !== nw2) return this.toast('새 비밀번호가 서로 다릅니다')
        if (nw === cur) return this.toast('지금 비밀번호와 다른 비밀번호를 입력해 주세요')
        if (s.saving) return
        this.setState({ saving: true })
        try { await this.props.auth.changePassword(cur, nw); this.setState({ sheet: null, pf: { cur: '', nw: '', nw2: '' } }); this.toast('비밀번호를 바꿨습니다') }
        catch (e) { this.toast(e instanceof ApiError && e.code === 'PASSWORD_MISMATCH' ? '지금 비밀번호가 맞지 않습니다' : errMsg(e, '비밀번호를 바꾸지 못했습니다')) }
        finally { this.setState({ saving: false }) }
      },

      showTabs, tb: { home: tbOn('home'), story: tbOn('story'), results: tbOn('results'), my: tbOn('my') },
      sheetLogin: s.sheet === 'login', sheetDel: s.sheet === 'del', sheetLogout: s.sheet === 'logout', sheetAcct: s.sheet === 'acct', sheetPw: s.sheet === 'pw', sheetWithdraw: s.sheet === 'withdraw', sheetResume: s.sheet === 'resume', anySheet: !!s.sheet,
      // 중단한 촬영이 있는 반려견: 이어서 할지, 지우고 새로 할지(11-06)
      resumeName: capD.name || '', confirmResume: () => { this.setState({ sheet: null }); if (capD.open) this.nav('capReview', `/sessions/${capD.open}`) },
      startFresh: async () => {
        if (!capD.open || s.busy) return
        this.setState({ busy: true })
        try { await this.props.actions.cancelSession(capD.open); this.freshStart = true; this.setState({ sheet: null, busy: false }); await this.goCapGuide() }
        catch (e) { this.setState({ busy: false }); this.toast(errMsg(e, '이전 촬영을 지우지 못했습니다')) }
      },
      closeSheet: () => this.setState({ sheet: null }),
      goSignupOrg: () => this.nav('signupOrg'), sheetToLogin: () => this.nav('login'),
      delName: (dogById(s.delId) || ({} as Partial<DDog>)).name || '',
      confirmDel: () => { this.setState({ sheet: null }); this.toast('반려견 삭제는 준비 중입니다') },
      confirmLogout: () => { this.props.auth.logout(); this.setState({ sheet: null, li: { id: '', pw: '' } }); this.props.nav('/welcome', { replace: true }) },
      toastOn: !!s.toast, toastMsg: s.toast,
      statusC: landscape ? 'transparent' : dark ? '#fff' : '#1B2433', indC: dark ? '#fff' : '#1B2433', indOp: landscape ? 0 : dark ? 0.8 : 0.25,
    }
  }
}
