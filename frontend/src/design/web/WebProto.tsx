// @ts-nocheck
/* eslint-disable */
// 디자인 프로토타입 로직 원본(Paw oh Paw Web). 1단계: 그대로 옮긴 뒤 데이터만 API 로 바꾼다.
import { DCLogic } from "../DCLogic"
import { WebView } from "./WebView"
import "./web-view.css"

const DOGS = [
  { id: 'd1', name: '보리', breed: '골든 리트리버', birth: '2019', kg: '28.4', sex: 'fs', rehab: '2026-08-18', focus: 'RH', memo: 'TPLO 수술 후 재활 9주차. 오른뒤 체중 부하 관찰 중', base: null },
  { id: 'd2', name: '콩이', breed: '말티즈', birth: '2022', kg: '3.2', sex: 'f', rehab: '', focus: null, memo: '', base: null },
  { id: 'd3', name: '두부', breed: '비글', birth: '2021', kg: '11.2', sex: 'mn', rehab: '2026-10-01', focus: 'LF', memo: '', base: null },
  { id: 'd4', name: '탄이', breed: '진돗개', birth: '2017', kg: '19.8', sex: 'm', rehab: '', focus: null, memo: '', base: null }];
const J = (a, b, c) => [['무릎', a[0], a[1]], ['고관절', b[0], b[1]], ['팔꿈치', c[0], c[1]]];
const RES = [
  { id: 'r2', dog: 'd3', date: '10월 15일', time: '17:40', st: 'part', sym: 84, rom: 44, sL: 30, sR: 27, j: J([58, 49], [40, 36], [47, 45]), w: '11.0', ps: [14, 7], ex: [['다리가 가려짐', 4], ['뛰었음', 3]], model: 'v1', rep: true },
  { id: 'r3', dog: 'd4', date: '10월 15일', time: '11:05', st: 'fail', w: '19.6', model: 'v1' },
  { id: 'r1', dog: 'd1', date: '10월 14일', time: '14:20', st: 'ok', sym: 92, rom: 48, sL: 41, sR: 38, j: J([66, 58], [44, 41], [52, 50]), w: '28.1', ps: [18, 12], ex: [['뛰었음', 4], ['중간에 멈춤', 2]], model: 'v1', rep: true },
  { id: 'r4', dog: 'd1', date: '10월 1일', time: '10:12', st: 'ok', sym: 88, rom: 48, sL: 40, sR: 37, j: J([65, 56], [43, 40], [51, 49]), w: '28.3', ps: [17, 11], ex: [['뛰었음', 3], ['일직선이 아님', 3]], model: 'v1', rep: true },
  { id: 'r5', dog: 'd2', date: '9월 28일', time: '16:30', st: 'ok', sym: 95, rom: 52, sL: 18, sR: 18, j: J([55, 53], [38, 37], [44, 44]), w: '3.2', ps: [16, 13], ex: [['중간에 멈춤', 3]], model: 'v1', rep: true },
  { id: 'r6', dog: 'd1', date: '9월 18일', time: '15:02', st: 'part', sym: 87, rom: 47, sL: 40, sR: 36, j: J([64, 55], [43, 39], [51, 48]), w: '28.6', ps: [15, 8], ex: [['다리가 가려짐', 4], ['뛰었음', 3]], model: 'v1', rep: true },
  { id: 'r7', dog: 'd1', date: '9월 3일', time: '11:48', st: 'ok', sym: 86, rom: 46, sL: 39, sR: 35, j: J([63, 54], [42, 38], [50, 47]), w: '28.9', ps: [18, 12], ex: [['뛰었음', 6]], model: 'v1', rep: false },
  { id: 'r8', dog: 'd1', date: '8월 20일', time: '09:30', st: 'ok', sym: 85, rom: 45, sL: 39, sR: 34, j: J([62, 53], [42, 38], [50, 47]), w: '29.4', ps: [16, 10], ex: [['중간에 멈춤', 4], ['앉음', 2]], model: 'v0', rep: true }];
const ST = { ok: ['유효', '#E8F3EC', '#2E8B57'], part: ['일부 유효', '#FAF1DF', '#9A6A12'], fail: ['실패', '#F8E7E3', '#C2412D'] };
const DEMO = { type: 'org', name: '한빛동물병원', id: 'hanbit_vet', loc: '서울 마포구 월드컵북로', dev: 'PP-2410-0381' };
const STEPS = ['업로드 완료', '반려견 찾는 중', '관절점 찾는 중', '보행 수치 계산 중', '보고서 만드는 중'];
const LINES = ['반려견의 걸음을', '더욱 정확하게', 'Paw oh Paw'];
const BREEDS = ['말티즈', '푸들', '토이 푸들', '포메라니안', '시츄', '치와와', '비숑 프리제', '요크셔테리어', '닥스훈트', '미니어처 슈나우저', '웰시코기', '비글', '시바견', '진돗개', '풍산개', '골든 리트리버', '래브라도 리트리버', '보더콜리', '프렌치 불독', '퍼그', '사모예드', '시베리안 허스키', '저먼 셰퍼드', '스피츠', '이탈리안 그레이하운드', '잭 러셀 테리어', '말라뮤트', '믹스견'];
const SMALLB = ['말티즈', '푸들', '토이 푸들', '포메라니안', '시츄', '치와와', '비숑 프리제', '요크셔테리어', '닥스훈트', '미니어처 슈나우저', '퍼그', '이탈리안 그레이하운드', '잭 러셀 테리어'];
const LARGEB = ['골든 리트리버', '래브라도 리트리버', '사모예드', '시베리안 허스키', '저먼 셰퍼드', '말라뮤트', '풍산개'];
const autoSize = (breed, kg) => SMALLB.includes(breed) ? 'S' : LARGEB.includes(breed) ? 'L' : (BREEDS.includes(breed) && breed !== '믹스견') ? 'M' : (+kg ? (+kg < 10 ? 'S' : +kg < 25 ? 'M' : 'L') : 'M');
const SEX = { m: '수컷', f: '암컷', mn: '중성화 수컷', fs: '중성화 암컷' };
const SIZE = { S: '소형', M: '중형', L: '대형' };
const LIMB = { LF: '왼앞', RF: '오른앞', LH: '왼뒤', RH: '오른뒤' };
const EMPTY_PET = { name: '', breed: '', birth: '', kg: '', sex: 'm', size: null, rehab: '', focus: null, memo: '', base: null };
const fmtD = iso => { const p = (iso || '').split('-'); return p.length === 3 ? `${p[0]}년 ${+p[1]}월 ${+p[2]}일` : iso; };
const short = d => d.replace('월 ', '.').replace('일', '');
const mrows = (R, g) => {
  const f = g === 'walk' ? 0.86 : 1, v = x => Math.round(x * f);
  return [
    { sec: '뒷다리', n: '무릎 가동 범위', l: v(R.j[0][1]), r: v(R.j[0][2]), u: '°', leg: '뒷다리' },
    { n: '고관절 가동 범위', l: v(R.j[1][1]), r: v(R.j[1][2]), u: '°', leg: '뒷다리' },
    { n: '걸음 길이', l: v(R.sL * 1.5), r: v(R.sR * 1.5), u: '%', leg: '뒷다리' },
    { n: '입각기 비율', l: 61, r: 61 - Math.round((R.sL - R.sR) / 2), u: '%', leg: '뒷다리' },
    { sec: '앞다리', n: '팔꿈치 가동 범위', l: v(R.j[2][1]), r: v(R.j[2][2]), u: '°', leg: '앞다리' },
    { n: '발 높이', na: true, reason: '반대쪽 다리가 가려졌어요', leg: '앞다리' }];
};
const gs = (p, c, w) => Math.exp(-(((p - c) / w) ** 2));
const knee = (depth) => { const s = []; for (let i = 0; i <= 40; i++) { const p = i / 40; const a = 150 - 16 * gs(p, .12, .07) - depth * gs(p, .7, .11); s.push(`${(24 + p * 286).toFixed(1)},${(130 - (a - 90) / 60 * 110).toFixed(1)}`); } return s.join(' '); };

export class WebProto extends DCLogic {
  static View = WebView
  state = {
    screen: 'landing', loggedIn: false, acct: DEMO, dogs: DOGS, results: RES, dogIdx: 0, line: 0, modal: null, toast: '', acctMenu: false, jumpOpen: false,
    li: { id: '', pw: '' }, so: { org: '', loc: '', dev: '', id: '', pw: '', pw2: '' }, to: [false, false, false, false], pet: EMPTY_PET, petMode: 'new', petId: null, delId: null,
    q: '', upDog: 'd1', shots: 0, sessW: '', drag: false, ana: { dog: 'd2', p: 2.3, n: 16 }, resId: 'r1', repType: 'g', gait: 'trot', cmp: 'base', tk: 'rom', filt: 'all', notifOn: true, introW: 0
  };
  vids = new Set();
  componentDidMount() {
    this.iv = setInterval(() => this.tick(), 100);
    const loop = () => { this.frame(); this.raf = requestAnimationFrame(loop); };
    this.raf = requestAnimationFrame(loop);
    this.onResize = () => this.measure();
    window.addEventListener('resize', this.onResize);
  }
  componentWillUnmount() { clearInterval(this.iv); cancelAnimationFrame(this.raf); clearTimeout(this.tt); window.removeEventListener('resize', this.onResize); }
  vid = el => {
    if (!el || this.vids.has(el)) return;
    this.vids.add(el);
    el.muted = true; el.volume = 0; el.loop = true; el.playsInline = true;
    const go = () => { el.muted = true; el.play().catch(() => {}); };
    go(); el.addEventListener('canplay', go);
    el.addEventListener('pause', () => { if (el.isConnected) setTimeout(go, 60); });
  };
  introRef = el => { if (el) this.introEl = el; };
  scRef = el => { if (el) this.scEl = el; };
  scStageRef = el => { if (el) this.scStage = el; };
  scRepRef = el => { if (el) this.scRep = el; };
  scVals() {
    const P = this.sp || 0, cl = v => Math.max(0, Math.min(1, v)), sm = (a, b) => { const t = cl((P - a) / (b - a)); return t * t * (3 - 2 * t); }, L = (a, b, t) => a + (b - a) * t, f = n => +n.toFixed(3);
    const narrow = (this.scW || 1200) < 860, e = 1, N = 5;
    const end = [0, 0, 0, 0], st0 = narrow ? [36, 8, 12, 8] : [30, 18, 10, 18];
    const bd = i => i / N, inP = i => i === 0 ? 1 : sm(bd(i) - .05, bd(i) + .025);
    const ab = { ft: f(L(st0[0], end[0], e)), fr: f(L(st0[1], end[1], e)), fb: f(L(st0[2], end[2], e)), fl: f(L(st0[3], end[3], e)), rad: f(L(36, 0, e)), tt: narrow ? 16 : 17, tl: 5, tw: 90, sc: f(e) };
    for (let i = 0; i < N; i++) { const nx = i < N - 1 ? inP(i + 1) : 0; ab['c' + i] = f((1 - inP(i)) * 100); ab['s' + i] = f(1 - .05 * nx); ab['d' + i] = f(.35 * nx); }
    const u = cl((P - .44) / .12); ab.upOn = u > 0 ? 1 : 0; ab.upP = Math.round(u * 100); ab.upTxt = u <= 0 ? '영상을 끌어다 놓거나 눌러서 선택' : u < 1 ? `업로드 중 · ${Math.round(u * 100)}%` : '업로드 완료 · 00:12'; ab.upBd = u > 0 ? '#D2601A' : '#E2DCD3'; ab.upBg = u > 0 ? '#FFF7F0' : '#FAF9F6'; ab.upBtn = u >= 1 ? '#D2601A' : '#E2DCD3';
    const an = cl((P - .63) / .14), nP = 0, kx = cl((P - .62) / .1) * 100; ab.anPct = Math.round(an * 100); ab.kx = f(kx); ab.kc = f(100 - kx); ab.ko = kx > 0 && kx < 100 ? 1 : 0;
    const H = (window.innerHeight || 900) * .7; ab.rpY = f(Math.max(0, (this.scRepH || 700) - H + 60) * sm(.86, .98));
    ab.kL = Array.from({ length: 41 }, (_, i) => `${24 + i * 7.15},${(75 - 48 * Math.sin(i / 40 * Math.PI * 4)).toFixed(1)}`).join(' ');
    ab.kR = Array.from({ length: 41 }, (_, i) => `${24 + i * 7.15},${(75 - 40 * Math.sin(i / 40 * Math.PI * 4 - .5)).toFixed(1)}`).join(' ');
    const idx = Math.min(N - 1, Math.floor(P * N + .02));
    const S = [['모든 견종', '대형견부터 소형견까지, 모든 반려견의 걸음을 분석합니다.'], ['촬영', '반려견이 걷는 모습을 옆에서 촬영합니다.'], ['영상 첨부', '반려견은 원하는 만큼 등록하고, 골라서 영상을 올려 주세요.'], ['AI 분석', 'AI 모델이 관절점을 찾고, 보행 패턴을 분석합니다.'], ['리포트', '결과를 리포트로 받아 PDF로 저장할 수 있습니다.']];
    return { ab,
      abPaws: Array.from({ length: 8 }, (_, i) => { const on = i < nP, up = i % 2 === 0; return { x: 2 + i * 12, y: up ? 30 : 92, r: up ? 98 : 82, s: on ? 1 : .8, op: on ? 1 : 0 }; }),
      abAnSteps: ['영상 확인', '관절점 찾기', '각도 계산'].map((n, i) => { const done = an >= (i + 1) / 3 - .001, cur = !done && an >= i / 3; return { n: (done ? '✓ ' : '') + n, bg: done ? '#FCEEE3' : cur ? '#1B2433' : '#F1EDE6', c: done ? '#A8481A' : cur ? '#fff' : '#7A808A' }; }),
      abDots: S.map((_, i) => ({ w: i === idx ? 36 : 12, c: i === idx ? '#D2601A' : '#E2DCD3' })),
      abSteps: S.map(([tag, txt], i) => { const ws = txt.split(' '), a0 = bd(i) + (i ? .02 : .03), p = cl((P - a0) / .13); return { tag, op: i === idx ? 1 : 0, ty: i === idx ? 0 : (i < idx ? -32 : 32), words: ws.map((t, k) => ({ t, c: p * ws.length > k + .3 ? '#1B2433' : '#D6D0C7', op: i === idx ? 1 : 0, ty: i === idx ? 0 : (i < idx ? -28 : 36), dl: i === idx ? 120 + k * 55 : 0 })) }; }) };
  }


  stepRef = el => { if (el) { this.stepEl = el; requestAnimationFrame(() => this.measure()); } };
  measure() { const el = this.stepEl; if (!el || !el.isConnected) return; const w = el.offsetWidth; if (w && Math.abs(w - this.state.introW) > 1) this.setState({ introW: w }); }
  rvEls = [];
  rvRef0 = el => { if (el) this.rvEls[0] = el; }; rvRef1 = el => { if (el) this.rvEls[1] = el; }; rvRef2 = el => { if (el) this.rvEls[2] = el; }; rvRef3 = el => { if (el) this.rvEls[3] = el; }; rvRef4 = el => { if (el) this.rvEls[4] = el; };
  rvSeen = [false, false, false, false, false];
  checkReveal() {
    if (this.state.screen !== 'landing') return;
    let ch = false;
    this.rvEls.forEach((el, i) => { if (!el || !el.isConnected || this.rvSeen[i]) return; if (el.getBoundingClientRect().top < window.innerHeight * 0.82) { this.rvSeen[i] = true; ch = true; } });
    if (ch) this.forceUpdate();
  }
  frame() {
    this.checkReveal();
    for (const v of this.vids) {
      if (!v.isConnected) { this.vids.delete(v); continue; }
      if (v.duration && v.currentTime >= v.duration - 0.2) v.currentTime = 0;
      if (v.dataset.lines && v.duration) { const i = Math.min(2, Math.floor(v.currentTime / ((v.duration - 0.2) / 3))); if (i !== this.state.line) this.setState({ line: i }); }
    }
    const sc = this.state.screen;
    if (sc === 'about' && this.scEl && this.scEl.isConnected) { const r = this.scEl.getBoundingClientRect(), tot = r.height - window.innerHeight; this.sp = tot > 0 ? Math.max(0, Math.min(1, -r.top / tot)) : 0; this.scY = Math.max(0, Math.min(tot, -r.top)); if (this.scStage) this.scW = this.scStage.offsetWidth; if (this.scRep) this.scRepH = this.scRep.offsetHeight; }
    if (sc === 'about') { const w = this.scW, p = this.sp; if (p !== this.lastSp || w !== this.lastW) { this.lastSp = p; this.lastW = w; this.forceUpdate(); } }
  }
  tick() {
    const s = this.state;
    if (s.ana && s.loggedIn) { const p = s.ana.p + (s.screen === 'analyzing' ? 0.07 : 0.035); if (p >= 5) this.finishAna(); else this.setState({ ana: { ...s.ana, p } }); }
  }
  finishAna() {
    const s = this.state, dog = s.dogs.find(d => d.id === s.ana.dog);
    const prev = s.results.find(r => r.dog === s.ana.dog && r.st !== 'fail');
    const b = prev || { sym: 88, rom: 46, sL: 30, sR: 28, j: J([60, 55], [42, 39], [50, 48]) };
    const n = s.ana.n || 16, meas = Math.round(n * 1.1), used = Math.round(meas * 0.68), exc = meas - used;
    const now = new Date();
    const r = { id: 'n' + Date.now(), dog: s.ana.dog, date: '10월 19일', time: String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0'), st: 'ok', sym: Math.min(98, b.sym + 2), rom: b.rom + 1, sL: b.sL, sR: Math.min(b.sL, b.sR + 1), j: b.j.map(([nm, l, rr]) => [nm, l, Math.min(l, rr + 2)]),
      w: s.ana.w || (dog && dog.kg) || '-', ps: [meas, used], ex: [['뛰었음', Math.ceil(exc / 2)], ['중간에 멈춤', Math.floor(exc / 2)]].filter(x => x[1] > 0), model: 'v1', rep: true };
    const onScreen = s.screen === 'analyzing';
    this.setState({ ana: null, shots: 0, results: [r, ...s.results], resId: onScreen ? r.id : s.resId, ...(onScreen ? { screen: 'detail', gait: 'trot' } : {}) });
    if (!onScreen) this.toast(`${dog ? dog.name : ''} 분석이 끝났어요`);
  }
  go = (screen, extra) => { this.setState({ screen, modal: null, acctMenu: false, ...(extra || {}) }); try { (document.scrollingElement || document.documentElement).scrollTo(0, 0); } catch (e) {} };
  toast = (m) => { clearTimeout(this.tt); this.setState({ toast: m }); this.tt = setTimeout(() => this.setState({ toast: '' }), 2400); };
  recentIdx = (dogs, results) => { const r = results.find(x => dogs.some(d => d.id === x.dog)); return r ? Math.max(0, dogs.findIndex(d => d.id === r.dog)) : 0; };
  login = (acct, demo) => this.go('home', { loggedIn: true, acct, q: '', dogIdx: 0, ...(demo ? { dogs: DOGS, results: RES, ana: { dog: 'd2', p: 2.3, n: 16 } } : { dogs: [], results: [], ana: null }) });
  openRes = (id) => this.go('detail', { resId: id, gait: 'trot' });
  openPet = (d) => this.setState(d ? { modal: 'pet', petMode: 'edit', petId: d.id, pet: { ...EMPTY_PET, ...d, size: d.sizeManual ? d.size : null } } : { modal: 'pet', petMode: 'new', petId: null, pet: EMPTY_PET });
  goUpload = (dogId) => { const s = this.state; if (!s.dogs.length) { this.toast('먼저 반려견을 등록해 주세요'); return this.openPet(null); } this.go('upload', { upDog: dogId || (s.dogs[Math.min(s.dogIdx, s.dogs.length - 1)] || {}).id, shots: 0, sessW: '' }); };
  openCompare = (dogId) => { const s = this.state; if (s.results.filter(r => r.dog === dogId && r.st !== 'fail').length < 2) return this.toast('유효한 회차가 2개 이상 있어야 비교할 수 있어요'); this.go('compare', { dogIdx: Math.max(0, s.dogs.findIndex(d => d.id === dogId)), cmp: 'base' }); };
  addShot = () => { const n = Math.min(16, this.state.shots + 1); if (this.state.shots >= 16) return this.toast('영상 16개를 모두 첨부했어요'); this.setState({ shots: n, drag: false }); this.toast(`${n}번째 영상을 첨부했어요`); };
  jump = (j) => {
    const [, scr, needLi, extra] = j, s = this.state;
    const base = { modal: null, acctMenu: false, jumpOpen: false };
    if (needLi) { base.loggedIn = true; if (!s.loggedIn || !s.results.find(r => r.id === 'r1')) Object.assign(base, { acct: DEMO, dogs: DOGS, results: RES }); }
    else base.loggedIn = false;
    if (extra === 'pet') { base.modal = 'pet'; base.petMode = 'new'; base.pet = EMPTY_PET; }
    if (scr === 'detail' || scr === 'report') { base.resId = (extra && extra[0] === 'r') ? extra : 'r1'; base.gait = 'trot'; }
    if (scr === 'home' || scr === 'compare') base.dogIdx = 0;
    if (scr === 'compare') base.cmp = 'base';
    if (scr === 'analyzing') base.ana = s.ana || { dog: 'd2', p: 1, n: 16 };
    if (scr === 'upload') { base.upDog = 'd1'; base.shots = extra === 'file' ? 7 : 0; }
    this.go(scr, base);
  };

  renderVals() {
    const s = this.state, sc = s.screen, li = s.loggedIn, isOrg = true;
    const chk = on => on ? '#D2601A' : '#C9C4BC';
    const dogById = id => s.dogs.find(d => d.id === id);
    const desc = d => [d.breed || '견종 미입력', d.birth ? d.birth + '년생' : null, d.kg ? d.kg + 'kg' : null].filter(Boolean).join(' · ');
    const valid = id => s.results.filter(r => r.dog === id && r.st !== 'fail');
    const delta = (a, b, unit) => { if (b == null) return '첫 측정'; const d = a - b; return d > 0 ? `직전 대비 +${d}${unit}` : d < 0 ? `직전 대비 −${-d}${unit}` : '직전과 같음'; };
    const sessNo = R => { const all = s.results.filter(r => r.dog === R.dog); return all.length - all.findIndex(r => r.id === R.id); };
    const baseOf = d => (d.base && s.results.find(r => r.id === d.base && r.st !== 'fail')) ? d.base : ((valid(d.id).slice(-1)[0]) || {}).id;
    const seg = (list, cur, set) => list.map(([k, label]) => { const on = cur === k; return { label, bg: on ? '#fff' : 'transparent', c: on ? '#1B2433' : '#5B6472', sh: on ? '0 1px 3px rgba(27,36,51,.12)' : 'none', pick: () => this.setState({ [set]: k }) }; });
    const pickSt = on => ({ bd: on ? '#D2601A' : '#ECE8E2', bg: on ? '#FCEEE3' : '#fff', c: on ? '#A8481A' : '#3A4250' });
    const di = Math.min(s.dogIdx, Math.max(0, s.dogs.length - 1)), cur = s.dogs[di];
    const ana = s.ana, anaP = ana ? ana.p : 0, anaFloor = Math.min(4, Math.floor(anaP)), anaDog = ana ? dogById(ana.dog) : null;
    const qq = (s.q || '').trim();

    let dd = { name: '', desc: '', cells: [], memo: '', hist: [], has: false, none: true, count: '', compare: () => {} };
    if (cur) {
      const all = s.results.filter(r => r.dog === cur.id), bId = baseOf(cur), bR = s.results.find(r => r.id === bId);
      dd = { name: cur.name, desc: desc(cur) + ' · ' + SEX[cur.sex || 'm'],
        cells: [{ k: '체급', v: SIZE[cur.size || autoSize(cur.breed, cur.kg)], sub: cur.sizeManual ? '직접 지정' : '자동 분류' }, { k: '재활 시작일', v: cur.rehab ? fmtD(cur.rehab) : '미입력', sub: '' }, { k: '관심 다리', v: cur.focus ? LIMB[cur.focus] : '미선택', sub: '' }, { k: '기준 회차', v: bR ? `${bR.date} · ${sessNo(bR)}회차` : '없음', sub: cur.base ? '직접 지정' : bR ? '가장 이른 회차' : '' }],
        memo: cur.memo || '없음',
        hist: all.map((r, i) => { const stt = ST[r.st]; return { no: `${sessNo(r)}회차`, date: r.date, w: r.w + 'kg', pass: r.st === 'fail' ? '—' : `${r.ps[1]} / ${r.ps[0]}`, model: r.model, rep: r.rep ? '있음' : '—', base: r.id === bId, canBase: r.st !== 'fail' && r.id !== bId,
          setBase: e => { e.stopPropagation(); this.setState(st => ({ dogs: st.dogs.map(x => x.id === cur.id ? { ...x, base: r.id } : x) })); this.toast(`${r.date} 회차를 기준으로 정했어요`); },
          st: stt[0], bg: stt[1], c: stt[2], bt: i ? '1px solid #F2EFEA' : 'none', open: () => this.openRes(r.id) }; }),
        has: all.length > 0, none: !all.length, count: all.length + '회차', compare: () => this.openCompare(cur.id) };
    }

    const R = sc === 'home' ? (cur ? s.results.find(r => r.dog === cur.id) : null) : (s.results.find(r => r.id === s.resId) || s.results[0]);
    const G = s.gait || 'trot';
    let rd = { ok: false, fail: false, part: false, rows: [], rank: [], ex: [], name: '', when: '', st: '', bg: '', c: '', topTitle: '', topSub: '' };
    let rp = { title: '', when: '', summary: '', items: [], rows: [], cond: '' };
    if (R) {
      const d = dogById(R.dog) || { name: '-' }, stt = ST[R.st];
      rd = { ...rd, name: d.name, desc: desc(d), when: `${R.date} · ${sessNo(R)}회차 · 체중 ${R.w}kg`, st: stt[0], bg: stt[1], c: stt[2], fail: R.st === 'fail', ok: R.st !== 'fail', part: R.st === 'part' };
      if (R.st !== 'fail') {
        const vv = valid(R.dog), idx = vv.findIndex(x => x.id === R.id), P = vv[idx + 1];
        const rows = mrows(R, sc === 'home' ? 'trot' : G), rowsT = mrows(R, 'trot');
        const rank = rs => rs.filter(x => !x.na).map(x => { const df = Math.abs(x.l - x.r); return { ...x, df, si: df / ((x.l + x.r) / 2) * 100 }; }).sort((a, b) => b.si - a.si);
        const meas = rank(rows), top = meas[0], topT = rank(rowsT)[0];
        const sL = Math.round(R.sL * 1.5), sR = Math.round(R.sR * 1.5);
        Object.assign(rd, { sym: R.sym, symD: delta(R.sym, P && P.sym, '%p'), rom: R.rom, romD: delta(R.rom, P && P.rom, '°'), sL, sR, stD: sL === sR ? '좌우 같음' : `${sL > sR ? '오른쪽' : '왼쪽'}이 ${Math.abs(sL - sR)}%p 짧음`,
          topTitle: `${top.leg} ${top.n}에서 좌우 차이가 가장 커요`,
          topSub: `왼 ${top.l}${top.u} · 오 ${top.r}${top.u} · 차이 ${top.df}${top.u} · 대칭 지수 차이 ${top.si.toFixed(1)}%`,
          rank: [...meas.slice(1, 4).map(x => ({ n: `${x.leg} · ${x.n}`, v: `차이 ${x.df}${x.u}`, c: '#fff' })), ...rows.filter(x => x.na).map(x => ({ n: `${x.leg} · ${x.n}`, v: '비교 불가', c: 'rgba(255,255,255,.5)' }))],
          rows: rows.map(x => ({ sec: x.sec || false, ok: !x.na, na: !!x.na, n: x.n, reason: x.reason || '', lv: x.na ? '' : x.l + x.u, rv: x.na ? '' : x.r + x.u, dv: x.na ? '' : Math.abs(x.l - x.r) + x.u })),
          pm: R.ps[0], pu: R.ps[1], px: R.ps[0] - R.ps[1], ex: R.ex.map(([n, c]) => ({ n, c })), model: `pga-pose ${R.model}`,
          kL: knee(R.j[0][1] * 0.8), kR: knee(R.j[0][2] * 0.8) });
        rp = { title: `${d.name}의 걸음 보고서`, when: `${R.date} 측정 · ${sessNo(R)}회차 · ${desc(d)}`,
          summary: `${topT.leg} ${topT.n}에서 왼쪽과 오른쪽 차이가 가장 컸어요(${topT.df}${topT.u}). 수의사 선생님과 함께 확인해 보세요.`,
          items: [
            { k: '좌우 대칭 지수', v: R.sym + '%', d: P ? `직전 ${P.sym}%` : '첫 측정' },
            { k: '뒷무릎 움직임 범위', v: `왼 ${rowsT[0].l}° · 오 ${rowsT[0].r}°`, d: `차이 ${Math.abs(rowsT[0].l - rowsT[0].r)}°` },
            { k: '걸음 길이(몸통 대비)', v: `왼 ${sL}% · 오 ${sR}%`, d: `차이 ${Math.abs(sL - sR)}%p` }],
          rows: [...rowsT.map(x => ({ n: x.n, l: x.na ? '측정 불가' : x.l + x.u, r: x.na ? '—' : x.r + x.u, d: x.na ? '—' : Math.abs(x.l - x.r) + x.u })), { n: '대칭 지수', l: '—', r: '—', d: R.sym + '%' }].map((x, i) => ({ ...x, bg: i % 2 ? '#fff' : '#FAF8F5' })),
          cond: `측면 가로 촬영 · 영상 16개 · 통과 ${R.ps[0]}개 중 ${R.ps[1]}개 사용 · 분석 모델 pga-pose ${R.model}. 측정 불가 항목은 사유와 함께 표시했습니다.` };
      }
    }

    const CD = cur;
    let cp = { has: false, none: true, rows: [], tl: '', tr: '', dl: [], xl: [], name: CD ? CD.name : '', baseLabel: '', baseDate: '', tDate: '', modelChanged: false, modelMsg: '', two: true, focusNote: '' };
    if (CD) {
      const vs = valid(CD.id).slice().reverse();
      if (vs.length >= 2) {
        const T = vs[vs.length - 1], bId = baseOf(CD), mode = s.cmp || 'base';
        let B = mode === 'base' ? vs.find(r => r.id === bId) : vs[vs.length - 2];
        if (!B || B.id === T.id) B = vs[vs.length - 2];
        const M = [['무릎 가동 범위', 'LH', r => r.j[0][1], '°'], ['무릎 가동 범위', 'RH', r => r.j[0][2], '°'], ['고관절 가동 범위', 'LH', r => r.j[1][1], '°'], ['고관절 가동 범위', 'RH', r => r.j[1][2], '°'], ['걸음 길이', 'LH', r => Math.round(r.sL * 1.5), '%'], ['걸음 길이', 'RH', r => Math.round(r.sR * 1.5), '%'], ['팔꿈치 가동 범위', 'LF', r => r.j[2][1], '°'], ['팔꿈치 가동 범위', 'RF', r => r.j[2][2], '°'], ['대칭 지수', null, r => r.sym, '%'], ['발 높이', 'LF', null, '%']];
        const ord = M.map((m, i) => ({ m, i, f: CD.focus && m[1] === CD.focus ? 0 : m[2] ? 1 : 2 })).sort((a, b) => a.f - b.f || a.i - b.i);
        const rows = ord.map(({ m: [n, limb, fn, u] }, i) => {
          const focus = !!CD.focus && limb === CD.focus, bt = i ? '1px solid #F2EFEA' : 'none';
          if (!fn) return { n, limb: LIMB[limb], lc: '#8E949C', vals: '한쪽 회차에서 측정 불가', j: '비교 불가', bg: '#F4F2EE', c: '#8E949C', bt };
          const b = fn(B), t = fn(T), df = t - b, inR = Math.abs(df) <= 1;
          return { n, limb: limb ? LIMB[limb] + (focus ? ' · 관심 다리' : '') : '전체', lc: focus ? '#B4501A' : '#8E949C', vals: `${b}${u} → ${t}${u}`, j: inR ? '범위 안' : df > 0 ? `▲ 증가 ${df}${u}` : `▼ 감소 ${-df}${u}`, bg: inR ? '#F4F2EE' : '#EEE8DF', c: inR ? '#5B6472' : '#1B2433', bt };
        });
        const TK = { rom: [r => r.j[0][1], r => r.j[0][2]], stride: [r => Math.round(r.sL * 1.5), r => Math.round(r.sR * 1.5)], stance: [() => 61, r => 61 - Math.round((r.sL - r.sR) / 2)], sym: [r => r.sym, null] };
        const tk = TK[s.tk || 'rom'];
        const A = vs.map(tk[0]), Bv = tk[1] ? vs.map(tk[1]) : [];
        const allV = [...A, ...Bv], mn = Math.min(...allV) - 2, mx = Math.max(...allV) + 2;
        const X = i => Math.round(20 + i * (280 / (vs.length - 1))), Y = v => Math.round(130 - (v - mn) / (mx - mn) * 110);
        cp = { has: true, none: false, name: CD.name, baseLabel: mode === 'base' ? '기준 회차' : '직전 회차', baseDate: `${B.date} · ${sessNo(B)}회차`, tDate: `${T.date} · ${sessNo(T)}회차`,
          modelChanged: B.model !== T.model, modelMsg: `두 회차의 분석 모델이 달라요(${B.model} → ${T.model}). 분석 방식이 바뀌어 수치를 그대로 비교하기 어려워요.`,
          rows, tl: A.map((v, i) => `${X(i)},${Y(v)}`).join(' '), tr: Bv.map((v, i) => `${X(i)},${Y(v)}`).join(' '),
          dl: [...A.map((v, i) => ({ x: X(i), y: Y(v), c: '#3B6FE0' })), ...Bv.map((v, i) => ({ x: X(i), y: Y(v), c: '#E5604D' }))],
          xl: vs.map(r => short(r.date)), two: !!tk[1],
          focusNote: CD.focus ? `관심 다리(${LIMB[CD.focus]})를 맨 앞에 보여 드려요.` : '관심 다리를 정하면 그 다리를 맨 앞에 보여 드려요.' };
      }
    }

    const reqOrg = [s.to[0], s.to[1], s.to[2]].every(Boolean);
    const orgOk = reqOrg && s.so.org && s.so.dev && s.so.id.length >= 4 && s.so.pw.length >= 4 && s.so.pw === s.so.pw2;
    const setK = (grp, k) => e => { const v = e.target.value; this.setState(st => ({ [grp]: { ...st[grp], [k]: v } })); };
    const termRows = (key, labels) => labels.map(([label, view], i) => ({ label, view, c: chk(s[key][i]), toggle: () => this.setState(st => { const a = [...st[key]]; a[i] = !a[i]; return { [key]: a }; }) }));

    const showIntro = sc === 'about';
    const T = 6.4, t = (Date.now() / 1000) % T, cl = v => Math.max(0, Math.min(1, v)), ez = v => v * v * (3 - 2 * v);
    const z = ez(cl((t - 0.4) / 1.4)), sk = ez(cl((t - 2.0) / 1.2)), m = ez(cl((t - 3.6) / 1.0)), out = ez(cl((t - 5.7) / 0.5));
    const SX = 2.069, SY = 2.036, TXp = -701 / 1254 * 100, TYp = 100 * (0.125 * (1 - SY) + -520 / 1254 * 0.75);
    const mo = { t1: `translate(${(z * TXp).toFixed(3)}%,${(z * TYp).toFixed(3)}%) scale(${(1 + z * (SX - 1)).toFixed(4)},${(1 + z * (SY - 1)).toFixed(4)})`, o1: ((1 - m) * (1 - out)).toFixed(3), o3: (sk * (1 - m)).toFixed(3), o2: (m * (1 - out)).toFixed(3) };

    const navOn = key => { const on = (key === 'home' && ['home', 'compare'].includes(sc)) || (key === 'results' && ['results', 'detail', 'report'].includes(sc)) || (key === 'about' && sc === 'about') || (key === 'my' && ['my', 'account'].includes(sc)); return { bg: on ? '#F1EAE0' : 'transparent', c: on ? '#B4501A' : '#3A4250', w: on ? 700 : 500 }; };
    const filtList = s.results.filter(r => dogById(r.dog) && (s.filt === 'all' || r.dog === s.filt));
    const jumps = [['랜딩', 'landing', 0], ['서비스 소개 (로그인 전)', 'about', 0], ['로그인', 'login', 0], ['기관 회원가입', 'signupOrg', 0], ['홈 · 반려견 · 측정 이력', 'home', 1], ['반려견 등록', 'home', 1, 'pet'], ['영상 업로드', 'upload', 1], ['업로드 · 영상 첨부 중', 'upload', 1, 'file'], ['분석 중', 'analyzing', 1], ['분석 결과', 'results', 1], ['회차 결과', 'detail', 1, 'r1'], ['회차 결과 · 일부 유효', 'detail', 1, 'r2'], ['회차 결과 · 실패', 'detail', 1, 'r3'], ['보고서', 'report', 1, 'r1'], ['경과 비교', 'compare', 1], ['서비스 소개', 'about', 1], ['마이페이지', 'my', 1], ['기본 정보', 'account', 1]];
    const bq = s.pet.breed.trim().replace(/\s/g, ''), bList = bq ? BREEDS.filter(b => b.replace(/\s/g, '').includes(bq)).slice(0, 6) : [], bExact = BREEDS.includes(s.pet.breed);
    const upD = dogById(s.upDog) || {};
    const autoSz = autoSize(s.pet.breed, s.pet.kg);
    const avStyle = on => ({ ring: on ? '0 0 0 3px #FAF9F6,0 0 0 6px #D2601A' : 'none', av: on ? '#FCEEE3' : '#EEEAE4', avc: on ? '#A8481A' : '#7A808A', nc: on ? '#1B2433' : '#5B6472', nw: on ? 700 : 500 });

    return {
      isLanding: sc === 'landing', isLogin: sc === 'login', isSignupOrg: sc === 'signupOrg', isHome: sc === 'home', isUpload: sc === 'upload',
      isAnalyzing: sc === 'analyzing', isResults: sc === 'results', isDetail: sc === 'detail', isReport: sc === 'report', isCompare: sc === 'compare', isMy: sc === 'my', isAccount: sc === 'account',
      showAppNav: li && !['login', 'signupOrg', 'landing'].includes(sc), showAuthBar: ['login', 'signupOrg'].includes(sc), showIntro,
      vid: this.vid, introRef: this.introRef, scRef: this.scRef, rvRef0: this.rvRef0, rvRef1: this.rvRef1, rvRef2: this.rvRef2, rvRef3: this.rvRef3, rvRef4: this.rvRef4,
      rv: Object.fromEntries(this.rvSeen.flatMap((v, i) => [['o' + i, v ? 1 : 0], ['y' + i, v ? 0 : 72]])), scStageRef: this.scStageRef, scRepRef: this.scRepRef, ...this.scVals(),
      lines: LINES.map((tt, i) => ({ t: tt, op: i === s.line ? 1 : 0, ty: i === s.line ? 0 : (i < s.line ? -16 : 16) })),
      scrollIntro: () => this.go('about'), showPubBar: sc === 'about' && !li,
      openStart: () => this.go('signupOrg'), goLogin: () => this.go('login'), goLanding: () => this.go(li ? 'home' : 'landing'),
      steps: [
        { num: '01', title: '반려견을 평소처럼\n걷게 합니다.', isS1: true, bg: 'transparent', ref: this.stepRef },
        { num: '02', title: '반려견이 걷는 모습을\n옆에서 촬영합니다.', isS2: true, bg: 'transparent', ref: null },
        { num: '03', title: 'AI 모델이 관절점을 찾고,\n보행 패턴을 분석합니다.', isMorph: true, bg: 'transparent', ref: null },
        { num: '04', title: '결과를 보고서로 받아\nPDF로 저장할 수 있습니다.', isReport: true, bg: 'transparent', ref: null }],
      mo, repZoom: Math.min((s.introW || 280) / 262, ((s.introW || 280) * 4 / 3 - 16) / 394).toFixed(3), kneeA: knee(53), kneeB: knee(46),
      introCta: () => li ? this.goUpload() : this.go('signupOrg'), introCtaLabel: li ? '보행 분석 시작하기' : '지금 시작하기',

      navItems: [['home', '홈'], ['about', '서비스 소개'], ['results', '분석 결과']].map(([key, label]) => ({ label, ...navOn(key), go: () => this.go(key) })),
      myChipBg: ['my', 'account'].includes(sc) ? '#FCEEE3' : '#fff',
      navHome: () => this.go('home'), navMy: () => this.go('my'), goAccount: () => this.go('account'),
      toggleAcct: () => this.setState(st => ({ acctMenu: !st.acctMenu })), acctMenuOn: s.acctMenu, acctInit: (s.acct.name || '?')[0], acctName: s.acct.name,
      askLogout: () => this.setState({ modal: 'logout', acctMenu: false }),
      anaOn: !!ana && li, goAnalyzing: () => this.go('analyzing'), anaName: anaDog ? anaDog.name : '', anaPct: Math.round(anaP / 5 * 100), anaStep: STEPS[anaFloor], anaN: anaFloor + 1,
      goUpload: () => this.goUpload(),

      loginSub: '동물병원·재활센터 계정으로 로그인해요.', loginIdLabel: '아이디', loginIdPh: '가입할 때 만든 아이디',
      fLoginId: s.li.id, fLoginPw: s.li.pw, onLoginId: setK('li', 'id'), onLoginPw: setK('li', 'pw'),
      loginBg: s.li.id.length >= 2 && s.li.pw.length >= 4 ? '#D2601A' : '#C3C8CF',
      doLogin: () => { if (s.li.id.length >= 2 && s.li.pw.length >= 4) this.login(DEMO, true); else this.toast('아이디와 비밀번호를 입력해 주세요'); },
      orgFields: [
        { label: '기관명', ph: '예) 한빛동물병원', type: 'text', val: s.so.org, on: setK('so', 'org') },
        { label: '기관 주소', ph: '주소 검색', type: 'text', val: s.so.loc, on: setK('so', 'loc') },
        { label: '디바이스 번호', ph: '예) PP-2410-0381', type: 'text', val: s.so.dev, on: setK('so', 'dev'), hint: '측정 기기 뒷면 라벨에 적혀 있어요.', hc: '#5B6472' }],
      orgAcctFields: [
        { label: '아이디', ph: '영문·숫자 4~16자', type: 'text', val: s.so.id, on: setK('so', 'id') },
        { label: '비밀번호', ph: '4자 이상', type: 'password', val: s.so.pw, on: setK('so', 'pw') },
        { label: '비밀번호 확인', ph: '한 번 더 입력', type: 'password', val: s.so.pw2, on: setK('so', 'pw2'), hint: s.so.pw2 && s.so.pw !== s.so.pw2 ? '비밀번호가 달라요' : false, hc: '#C2412D' }],
      allOrgC: chk(s.to.every(Boolean)), allOrgToggle: () => this.setState(st => ({ to: st.to.map(() => !st.to.every(Boolean)) })),
      termsOrg: termRows('to', [['[필수] 서비스 이용약관', true], ['[필수] 개인정보 수집 및 이용', true], ['[필수] 측정 기기 연동 및 위치정보 이용', true], ['[선택] 마케팅 정보 수신', true]]),
      signOrgBg: orgOk ? '#D2601A' : '#C3C8CF',
      doSignupOrg: () => { if (!orgOk) return this.toast(!reqOrg ? '필수 약관에 동의해 주세요' : (s.so.pw2 && s.so.pw !== s.so.pw2) ? '비밀번호가 서로 달라요' : '입력하지 않은 항목이 있어요'); this.login({ type: 'org', name: s.so.org, id: s.so.id, loc: s.so.loc || '-', dev: s.so.dev }, false); this.toast(`${s.so.org} 가입을 환영해요`); },

      acctKind: '기관', hasDogs: s.dogs.length > 0, noDogs: !s.dogs.length,
      q: s.q, onQ: e => { const v = e.target.value; this.setState({ q: v }); }, noMatch: !!qq && !s.dogs.some(d => d.name.includes(qq)),
      homeHasRes: !!R, homeNoRes: !R, homeOpenRep: () => R && this.go('report', { resId: R.id, repType: 'g' }), homeOpenDetail: () => R && this.openRes(R.id),
      dogStrip: s.dogs.map((d, i) => ({ d, i })).filter(({ d }) => !qq || d.name.includes(qq)).map(({ d, i }) => { const all = s.results.filter(r => r.dog === d.id); return { init: d.name[0], name: d.name, breed: d.breed || '견종 미입력', meta: all.length ? `${all.length}회차 · ${short(all[0].date)}` : '측정 전', live: !!(ana && ana.dog === d.id), ...avStyle(i === di), pick: () => this.setState({ dogIdx: i }) }; }),
      dd, addPet: () => this.openPet(null), editCur: () => cur && this.openPet(cur), uploadCur: () => this.goUpload(cur && cur.id),
      recent: s.results.filter(r => dogById(r.dog)).slice(0, 12).map((r, i) => ({ init: dogById(r.dog).name[0], name: dogById(r.dog).name, when: `${r.date} · ${sessNo(r)}회차`, st: ST[r.st][0], bg: ST[r.st][1], c: ST[r.st][2], bt: i ? '1px solid #F2EFEA' : 'none', open: () => this.openRes(r.id) })),
      goResults: () => this.go('results'), goHome: () => this.go('home'),

      upDogs: s.dogs.map(d => ({ init: d.name[0], name: d.name, breed: d.breed || '견종 미입력', ...avStyle(d.id === s.upDog), pick: () => this.setState({ upDog: d.id }) })),
      sessW: s.sessW, onSessW: e => { const v = e.target.value; this.setState({ sessW: v }); }, sessWPh: upD.kg ? `등록 체중 ${upD.kg}` : '예) 28.1',
      noFile: !s.shots, hasFile: s.shots > 0, dropBd: s.drag ? '#D2601A' : s.shots ? '#ECE8E2' : '#D9D2C7', dropBg: s.drag ? '#FFF6EE' : '#fff',
      pickFile: this.addShot,
      onDragOver: e => { e.preventDefault(); if (!s.drag) this.setState({ drag: true }); }, onDragLeave: () => this.setState({ drag: false }),
      onDrop: e => { e.preventDefault(); this.addShot(); },
      clearFile: () => this.setState({ shots: 0 }),
      slots: Array.from({ length: 16 }, (_, i) => { const done = i < s.shots, next = i === s.shots; return { n: i + 1, done, next, bg: done ? '#141B22' : next ? '#FCEEE3' : '#F4F1EC', bs: next ? 'dashed' : 'solid', bd: done ? '#141B22' : next ? '#D2601A' : '#ECE8E2', nc: done ? 'rgba(255,255,255,.75)' : next ? '#B4501A' : '#A0A7B2', cur: next ? 'pointer' : 'default', tap: next ? this.addShot : () => {} }; }),
      shotN: s.shots, shotPct: Math.round(s.shots / 16 * 100),
      shotHint: s.shots >= 16 ? '16개를 모두 첨부했어요. 분석을 시작해 주세요.' : `${s.shots + 1}번째 영상을 이어서 올려 주세요. 16개를 모두 채우면 결과가 더 정확해요.`,
      fileName: `${upD.name || '반려견'} · 영상 ${s.shots}`,
      startBg: s.shots ? '#D2601A' : '#C3C8CF',
      startAna: () => { if (!s.shots) return this.toast('보행 영상을 1개 이상 올려 주세요'); this.go('analyzing', { ana: { dog: s.upDog, p: 0, n: s.shots, w: s.sessW } }); },

      prints: (() => { const ph = Math.floor(Date.now() / 420) % 11; return Array.from({ length: 8 }, (_, i) => { const on = ph <= 8 ? i < ph : ph === 9; const up = i % 2 === 0; const jy = [0, 4, -5, 3, -3, 6, -2, 4][i]; return { x: 1 + i * 12.6, y: (up ? 60 : 180) + jy * 2, r: 90 + (up ? 8 : -8), s: on ? 1 : 0.85, op: on ? 1 : 0 }; }); })(),

      resDogs: [{ id: 'all', name: '전체', init: '전체', breed: '' }, ...s.dogs.map(d => ({ id: d.id, name: d.name, init: d.name[0], breed: d.breed || '견종 미입력' }))].map(d => ({ init: d.init, name: d.name, breed: d.breed, hasBreed: !!d.breed, isAll: d.id === 'all', notAll: d.id !== 'all', ...avStyle(s.filt === d.id), pick: () => this.setState({ filt: d.id }) })),
      rows: filtList.map((r, i) => ({ name: dogById(r.dog).name, when: `${r.date} · ${sessNo(r)}회차`, st: ST[r.st][0], bg: ST[r.st][1], c: ST[r.st][2], pass: r.st === 'fail' ? '—' : `${r.ps[1]} / ${r.ps[0]}`, sym: r.st === 'fail' ? '—' : r.sym + '%', w: r.w + 'kg', bt: i ? '1px solid #F2EFEA' : 'none', open: () => this.openRes(r.id) })),
      hasRows: filtList.length > 0, noRows: !filtList.length,

      rd, rp, partMsg: '일부 통과에서 다리가 가려지거나 뛰어서 해당 통과를 제외하고 계산했습니다.',
      gaitSegs: seg([['walk', '평보'], ['trot', '속보']], G, 'gait'), gaitName: G === 'walk' ? '평보' : '속보',
      openRep: () => this.go('report', { repType: 'g' }), backDetail: () => this.go('detail'), retake: () => this.goUpload(R && R.dog),
      openCompareR: () => R && this.openCompare(R.dog),
      isRepG: s.repType === 'g', isRepV: s.repType === 'v', repKind: s.repType === 'v' ? '보행 분석 보고서 · 수의사용' : '보행 분석 보고서 · 보호자용',
      repSegs: seg([['g', '보호자용'], ['v', '수의사용']], s.repType, 'repType'),
      repStatus: R ? `생성 완료 · ${s.repType === 'v' ? '9.1' : '8.4'}초 · 분석 모델 ${R.model} · 템플릿 1.0` : '',
      regenRep: () => this.toast('보고서를 다시 만들고 있어요'), saveRep: () => this.toast('PDF를 내려받았어요'),

      cp, cmpSegs: seg([['base', '기준 회차 대비'], ['prev', '직전 회차 대비']], s.cmp || 'base', 'cmp'),
      trendKs: [['rom', '무릎 가동 범위'], ['stride', '걸음 길이'], ['stance', '입각기 비율'], ['sym', '대칭 지수']].map(([k, label]) => { const on = (s.tk || 'rom') === k; return { label, bg: on ? '#1B2433' : '#fff', c: on ? '#fff' : '#3A4250', bd: on ? '#1B2433' : '#ECE8E2', pick: () => this.setState({ tk: k }) }; }),
      reanalyze: () => this.toast('새 모델로 재분석을 요청했어요'),

      isOrg, isUser: false, myDev: s.acct.dev || '-',
      myDogs: s.dogs.map((d, i) => ({ init: d.name[0], name: d.name, desc: desc(d) + ' · ' + SEX[d.sex || 'm'], bt: i ? '1px solid #F2EFEA' : 'none', edit: () => this.openPet(d), del: () => this.setState({ modal: 'del', delId: d.id }) })),
      myDogCount: s.dogs.length + '마리',
      tgBg: s.notifOn ? '#D2601A' : '#DDD7CE', tgX: s.notifOn ? 22 : 2, toggleNotif: () => this.setState(st => ({ notifOn: !st.notifOn })),
      help: () => this.toast('고객센터로 연결할게요'), editAcct: () => this.toast('정보 수정은 준비 중이에요'),
      acctRows: [['계정 유형', '기관 회원'], ['기관명', s.acct.name], ['아이디', s.acct.id || '-'], ['기관 주소', s.acct.loc || '-'], ['디바이스 번호', s.acct.dev || '-'], ['가입일', '2026년 10월 2일']].map(([kk, v], i) => ({ k: kk, v, bt: i ? '1px solid #F2EFEA' : 'none' })),

      anyModal: !!s.modal, mPet: s.modal === 'pet', mDel: s.modal === 'del', mLogout: s.modal === 'logout', mGuide: s.modal === 'guide', openGuide: () => this.setState({ modal: 'guide' }),
      closeModal: () => this.setState({ modal: null }), stop: e => e.stopPropagation(),
      goSignupOrg: () => this.go('signupOrg'), modalToLogin: () => this.go('login'),
      petTitle: s.petMode === 'edit' ? '반려견 정보 수정' : '반려견 등록', petCta: s.petMode === 'edit' ? '저장하기' : '등록하기',
      petName: s.pet.name, onPetName: setK('pet', 'name'), petBreed: s.pet.breed, onPetBreed: setK('pet', 'breed'), petBirth: s.pet.birth, onPetBirth: setK('pet', 'birth'), petKg: s.pet.kg, onPetKg: setK('pet', 'kg'),
      petRehab: s.pet.rehab, onPetRehab: setK('pet', 'rehab'), petMemo: s.pet.memo, onPetMemo: setK('pet', 'memo'),
      showSug: !!bq && !bExact, noSug: !!bq && !bExact && !bList.length,
      sugs: bList.map((name, i) => ({ name, bt: i ? '1px solid #F2EFEA' : 'none', pick: () => this.setState(st => ({ pet: { ...st.pet, breed: name } })) })),
      sexes: Object.entries(SEX).map(([kk, label]) => ({ label, ...pickSt(s.pet.sex === kk), pick: () => this.setState(st => ({ pet: { ...st.pet, sex: kk } })) })),
      sizes: Object.entries(SIZE).map(([kk, label]) => ({ label, ...pickSt((s.pet.size || autoSz) === kk), pick: () => this.setState(st => ({ pet: { ...st.pet, size: st.pet.size === kk ? null : kk } })) })),
      sizeNote: s.pet.size ? '직접 선택 · 다시 누르면 자동 분류' : '견종·체중으로 자동 분류돼요',
      limbs: Object.entries(LIMB).map(([kk, label]) => ({ label, ...pickSt(s.pet.focus === kk), pick: () => this.setState(st => ({ pet: { ...st.pet, focus: st.pet.focus === kk ? null : kk } })) })),
      petBg: s.pet.name && s.pet.breed && s.pet.kg ? '#D2601A' : '#C3C8CF',
      doPet: () => {
        if (!s.pet.name || !s.pet.breed || !s.pet.kg) return this.toast('이름·견종·체중을 입력해 주세요');
        const save = { ...s.pet, size: s.pet.size || autoSz, sizeManual: !!s.pet.size };
        if (s.petMode === 'edit') { this.setState(st => ({ dogs: st.dogs.map(d => d.id === st.petId ? { ...d, ...save } : d), modal: null })); this.toast('저장했어요'); }
        else { const id = 'p' + Date.now(); this.setState(st => ({ dogs: [...st.dogs, { id, ...save }], dogIdx: st.dogs.length, modal: null })); this.toast(`${s.pet.name} 등록을 마쳤어요`); }
      },
      delName: (dogById(s.delId) || {}).name || '',
      confirmDel: () => { const n = (dogById(s.delId) || {}).name; this.setState(st => ({ dogs: st.dogs.filter(d => d.id !== st.delId), results: st.results.filter(r => r.dog !== st.delId), dogIdx: 0, modal: null, filt: 'all', ana: st.ana && st.ana.dog === st.delId ? null : st.ana })); this.toast(`${n} 정보를 삭제했어요`); },
      confirmLogout: () => this.go('landing', { loggedIn: false, li: { id: '', pw: '' } }),
      toastOn: !!s.toast, toastMsg: s.toast,
      jumpOpen: s.jumpOpen, toggleJump: () => this.setState(st => ({ jumpOpen: !st.jumpOpen })),
      jumps: jumps.map(j => ({ label: j[0], go: () => this.jump(j) }))
    };
  }
}
