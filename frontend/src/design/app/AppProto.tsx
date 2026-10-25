// @ts-nocheck
/* eslint-disable */
// 디자인 프로토타입 로직 원본(Paw oh Paw App). 1단계: 그대로 옮긴 뒤 데이터만 API 로 바꾼다.
import { DCLogic } from "../DCLogic"
import { AppView } from "./AppView"
import "./app-view.css"

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
const DEMO = { type: 'org', name: '한빛동물병원', id: 'hanbit_vet', email: 'kim@hanbit.vet', phone: '02-555-0137', loc: '서울 마포구 월드컵북로', dev: 'PP-2410-0381' };
const STEPS = ['업로드 완료', '반려견 찾는 중', '관절점 찾는 중', '보행 수치 계산 중', '보고서 만드는 중'];
const LINES = ['반려견의 걸음을', '더욱 정확하게', 'Paw oh Paw'];
const gs = (p, c, w) => Math.exp(-(((p - c) / w) ** 2));
const knee = (depth) => { const s = []; for (let i = 0; i <= 40; i++) { const p = i / 40; const a = 150 - 16 * gs(p, .12, .07) - depth * gs(p, .7, .11); s.push(`${(24 + p * 286).toFixed(1)},${(130 - (a - 90) / 60 * 110).toFixed(1)}`); } return s.join(' '); };
const EMPTY_PET = { name: '', breed: '', birth: '', kg: '', sex: 'm', size: null, rehab: '', focus: null, memo: '', base: null };
const BREEDS = ['말티즈', '푸들', '토이 푸들', '포메라니안', '시츄', '치와와', '비숑 프리제', '요크셔테리어', '닥스훈트', '미니어처 슈나우저', '웰시코기', '비글', '시바견', '진돗개', '풍산개', '골든 리트리버', '래브라도 리트리버', '보더콜리', '프렌치 불독', '퍼그', '사모예드', '시베리안 허스키', '저먼 셰퍼드', '스피츠', '이탈리안 그레이하운드', '잭 러셀 테리어', '말라뮤트', '믹스견'];
const SMALLB = ['말티즈', '푸들', '토이 푸들', '포메라니안', '시츄', '치와와', '비숑 프리제', '요크셔테리어', '닥스훈트', '미니어처 슈나우저', '퍼그', '이탈리안 그레이하운드', '잭 러셀 테리어'];
const LARGEB = ['골든 리트리버', '래브라도 리트리버', '사모예드', '시베리안 허스키', '저먼 셰퍼드', '말라뮤트', '풍산개'];
const autoSize = (breed, kg) => SMALLB.includes(breed) ? 'S' : LARGEB.includes(breed) ? 'L' : (BREEDS.includes(breed) && breed !== '믹스견') ? 'M' : (+kg ? (+kg < 10 ? 'S' : +kg < 25 ? 'M' : 'L') : 'M');
const SEX = { m: '수컷', f: '암컷', mn: '중성화 수컷', fs: '중성화 암컷' };
const SIZE = { S: '소형', M: '중형', L: '대형' };
const LIMB = { LF: '왼앞', RF: '오른앞', LH: '왼뒤', RH: '오른뒤' };
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

export class AppProto extends DCLogic {
  static View = AppView
  state = {
    screen: 'splash', stack: [], loggedIn: false, acct: DEMO, dogs: DOGS, results: RES, joint: false, line: 0, sheet: null, toast: '',
    li: { id: '', pw: '' }, so: { org: '', loc: '', dev: '', id: '', pw: '', pw2: '' }, to: [false, false, false, false],
    pet: EMPTY_PET, petMode: 'new', petId: null, delId: null, q: '', dogSel: 'd1',
    capDog: 'd1', shots: 0, sessW: '', rec: 0, recOn: false, ana: { dog: 'd2', p: 2.3, n: 16 }, resId: 'r1', repType: 'g', gait: 'trot', cmp: 'base', tk: 'rom', page: 0, filt: 'all', notifOn: true
  };
  vids = new Set();
  componentDidMount() {
    this.startSplash();
    this.iv = setInterval(() => this.tick(), 100);
    const loop = () => { this.frame(); this.raf = requestAnimationFrame(loop); };
    this.raf = requestAnimationFrame(loop);
  }
  componentWillUnmount() { clearInterval(this.iv); cancelAnimationFrame(this.raf); clearTimeout(this.t1); clearTimeout(this.t2); clearTimeout(this.tt); }
  startSplash() {
    clearTimeout(this.t1); clearTimeout(this.t2);
    this.setState({ joint: false });
    this.t1 = setTimeout(() => this.setState({ joint: true }), 300);
    this.t2 = setTimeout(() => { if (this.state.screen === 'splash') this.setState({ screen: 'landing', stack: [] }); }, 2200);
  }
  vid = el => {
    if (!el || this.vids.has(el)) return;
    this.vids.add(el);
    el.muted = true; el.volume = 0; el.loop = true; el.playsInline = true;
    const go = () => { el.muted = true; el.play().catch(() => {}); };
    go();
    el.addEventListener('canplay', go);
    el.addEventListener('pause', () => { if (el.isConnected) setTimeout(go, 60); });
  };
  storyRef = el => { if (el) this.storyEl = el; };
  repBox = el => { if (!el) return; requestAnimationFrame(() => { const h = el.parentElement && el.parentElement.offsetHeight; if (h && h !== this.state.repH) this.setState({ repH: h }); }); };
  frame() {
    if (this.state.screen === 'story' && this.state.page === 2) { const n = performance.now(); if (!this.lastMo || n - this.lastMo > 33) { this.lastMo = n; this.forceUpdate(); } }
    for (const v of this.vids) {
      if (!v.isConnected) { this.vids.delete(v); continue; }
      if (v.duration && v.currentTime >= v.duration - 0.2) v.currentTime = 0;
      if (v.dataset.lines && v.duration) {
        const seg = (v.duration - 0.2) / 3;
        const i = Math.min(2, Math.floor(v.currentTime / seg));
        if (i !== this.state.line) this.setState({ line: i });
      }
    }
  }
  tick() {
    const s = this.state;
    if (s.recOn) { const r = s.rec + 0.1; if (r >= 4) this.addShot(); else this.setState({ rec: r }); }
    if (s.ana && s.loggedIn) {
      const p = s.ana.p + (s.screen === 'analyzing' ? 0.07 : 0.035);
      if (p >= 5) this.finishAna(); else this.setState({ ana: { ...s.ana, p } });
    }
  }
  addShot = () => {
    const n = Math.min(16, this.state.shots + 1);
    this.setState(st => ({ shots: n, recOn: false, rec: 0, screen: 'capReview', sheet: null, stack: (st.screen === 'capSelect' ? [...st.stack, 'capSelect'] : st.stack).filter(x => x !== 'capReview' && x !== 'capGuide') }));
    this.toast(`${n}번째 영상을 첨부했어요`);
  };
  finishAna() {
    const s = this.state;
    const dog = s.dogs.find(d => d.id === s.ana.dog);
    const prev = s.results.find(r => r.dog === s.ana.dog && r.st !== 'fail');
    const b = prev || { sym: 88, rom: 46, sL: 30, sR: 28, j: J([60, 55], [42, 39], [50, 48]) };
    const n = s.ana.n || 16, meas = Math.round(n * 1.1), used = Math.round(meas * 0.68), exc = meas - used;
    const now = new Date();
    const r = { id: 'n' + Date.now(), dog: s.ana.dog, date: '10월 19일', time: String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0'), st: 'ok', sym: Math.min(98, b.sym + 2), rom: b.rom + 1, sL: b.sL, sR: Math.min(b.sL, b.sR + 1), j: b.j.map(([nm, l, rr]) => [nm, l, Math.min(l, rr + 2)]),
      w: s.ana.w || (dog && dog.kg) || '-', ps: [meas, used], ex: [['뛰었음', Math.ceil(exc / 2)], ['중간에 멈춤', Math.floor(exc / 2)]].filter(x => x[1] > 0), model: 'v1', rep: true };
    const onScreen = s.screen === 'analyzing';
    this.setState({ ana: null, shots: 0, results: [r, ...s.results], resId: onScreen ? r.id : s.resId });
    if (onScreen) this.setState({ screen: 'detail', stack: ['home'] });
    else this.toast(`${dog ? dog.name : ''} 분석이 끝났어요`);
  }
  nav = (screen, replace) => this.setState(s => ({ screen, sheet: null, stack: replace ? s.stack : [...s.stack, s.screen], ...(screen === 'story' ? { page: 0 } : {}) }));
  back = () => this.setState(s => { const st = [...s.stack]; const p = st.pop() || (s.loggedIn ? 'home' : 'landing'); return { screen: p, stack: st, sheet: null, recOn: false, rec: 0 }; });
  tab = (screen) => {
    if (!this.state.loggedIn && ['capSelect', 'results', 'my'].includes(screen)) return this.setState({ sheet: 'login' });
    if (screen === 'capSelect') return this.goCapture();
    this.setState({ screen, stack: [], sheet: null, ...(screen === 'story' ? { page: 0 } : {}) });
  };
  toast = (m) => { clearTimeout(this.tt); this.setState({ toast: m }); this.tt = setTimeout(() => this.setState({ toast: '' }), 2200); };
  goCapture = () => {
    const s = this.state;
    if (!s.dogs.length) { this.toast('먼저 반려견을 등록해 주세요'); return this.goPetNew(); }
    const cur = s.dogs.find(d => d.id === s.dogSel) || s.dogs[0];
    this.setState({ capDog: cur.id, shots: 0, sessW: '' });
    this.nav('capSelect');
  };
  startRot = () => { clearTimeout(this.r1); clearTimeout(this.r2); this.setState({ recOn: false, rec: 0, rotDone: false, rotAnim: false }); this.r1 = setTimeout(() => this.setState({ rotAnim: true }), 350); this.r2 = setTimeout(() => this.setState({ rotDone: true }), 1500); };
  goCapGuide = () => { if (this.state.shots >= 16) return this.toast('영상 16개를 모두 첨부했어요'); this.startRot(); this.nav('capGuide'); };
  goPetNew = () => { this.setState({ petMode: 'new', pet: EMPTY_PET, petId: null }); this.nav('petNew'); };
  openRes = (id) => { this.setState({ resId: id, gait: 'trot' }); this.nav('detail'); };
  openDog = (id) => { this.setState({ dogSel: id }); this.nav('dog'); };
  login = (acct, demo) => this.setState({ loggedIn: true, acct, screen: 'home', stack: [], sheet: null, q: '', ...(demo ? { dogs: DOGS, results: RES, ana: { dog: 'd2', p: 2.3, n: 16 }, dogSel: 'd1' } : { dogs: [], results: [], ana: null }) });
  jump = (j) => {
    const [, scr, needLi, extra] = j;
    const s = this.state;
    const base = { screen: scr, stack: [], sheet: null, recOn: false, rec: 0, page: 0 };
    if (needLi) {
      base.loggedIn = true;
      if (!s.loggedIn || !s.results.find(r => r.id === 'r1')) Object.assign(base, { acct: DEMO, dogs: DOGS, results: RES });
    } else base.loggedIn = false;
    if (scr === 'detail' || scr === 'report') { base.resId = extra || 'r1'; base.gait = 'trot'; base.stack = ['results']; if (scr === 'report') base.stack = ['results', 'detail']; }
    if (scr === 'analyzing') base.ana = s.ana || { dog: 'd2', p: 1, n: 16 };
    if (scr === 'account') base.stack = ['my'];
    if (scr === 'notif' || scr === 'petNew' || scr === 'dog') base.stack = ['home'];
    if (scr === 'dog' || scr === 'compare') base.dogSel = 'd1';
    if (scr === 'compare') { base.stack = ['home', 'dog']; base.cmp = 'base'; }
    if (scr === 'capSelect') Object.assign(base, { shots: 0, capDog: 'd1', stack: ['home'] });
    if (scr === 'capGuide') Object.assign(base, { capDog: 'd1', stack: ['home', 'capSelect', 'capReview'], shots: s.shots || 3 });
    if (scr === 'capReview') Object.assign(base, { shots: 11, capDog: 'd1', stack: ['home', 'capSelect'] });
    if (scr === 'capGuide') { base.rotDone = false; base.rotAnim = false; setTimeout(() => this.startRot(), 0); }
    if (scr === 'petNew') Object.assign(base, { petMode: 'new', pet: EMPTY_PET });
    this.setState(base);
    if (scr === 'splash') this.startSplash();
  };

  renderVals() {
    const s = this.state, sc = s.screen, li = s.loggedIn;
    const chk = on => on ? '#D2601A' : '#C9C4BC';
    const dogById = id => s.dogs.find(d => d.id === id);
    const desc = d => [d.breed || '견종 미입력', d.birth ? d.birth + '년생' : null, d.kg ? d.kg + 'kg' : null].filter(Boolean).join(' · ');
    const valid = id => s.results.filter(r => r.dog === id && r.st !== 'fail');
    const delta = (a, b, unit) => { if (b == null) return ['첫 측정', '#8E949C']; const d = a - b; return [d > 0 ? `직전 대비 +${d}${unit}` : d < 0 ? `직전 대비 −${-d}${unit}` : '직전과 같음', '#5B6472']; };
    const sessNo = R => { const all = s.results.filter(r => r.dog === R.dog); return all.length - all.findIndex(r => r.id === R.id); };
    const baseOf = d => (d.base && s.results.find(r => r.id === d.base && r.st !== 'fail')) ? d.base : ((valid(d.id).slice(-1)[0]) || {}).id;
    const seg = (list, cur, set) => list.map(([k, label]) => { const on = cur === k; return { label, bg: on ? '#fff' : 'transparent', c: on ? '#1B2433' : '#5B6472', sh: on ? '0 1px 3px rgba(27,36,51,.12)' : 'none', pick: () => this.setState({ [set]: k }) }; });
    const pick = (on) => ({ bd: on ? '#D2601A' : '#ECE8E2', bg: on ? '#FCEEE3' : '#fff', c: on ? '#A8481A' : '#3A4250' });

    const ana = s.ana, anaP = ana ? ana.p : 0, anaFloor = Math.min(4, Math.floor(anaP));
    const anaDog = ana ? dogById(ana.dog) : null;

    const qq = (s.q || '').trim();
    const shown = s.dogs.filter(d => !qq || d.name.includes(qq));
    const homeDogs = shown.map(d => { const all = s.results.filter(r => r.dog === d.id); return { init: d.name[0], name: d.name, desc: desc(d), live: !!((ana && ana.dog === d.id) || (s.shots > 0 && s.capDog === d.id)), meta: all.length ? `마지막 측정 ${all[0].date} · ${all.length}회차` : '아직 측정 기록이 없어요', open: () => this.openDog(d.id) }; });

    const D = dogById(s.dogSel) || s.dogs[0];
    let dd = { name: '', init: '', desc: '', tags: [], rows: [], hist: [], has: false, none: true, count: '', edit: () => {}, compare: () => {}, start: () => {} };
    if (D) {
      const all = s.results.filter(r => r.dog === D.id), bId = baseOf(D), bR = s.results.find(r => r.id === bId);
      dd = { name: D.name, init: D.name[0], desc: desc(D),
        tags: [SIZE[D.size || autoSize(D.breed, D.kg)] + (D.sizeManual ? ' · 직접 지정' : ' · 자동 분류'), SEX[D.sex || 'm']],
        rows: [{ k: '재활 시작일', v: D.rehab ? fmtD(D.rehab) : '미입력', sub: '' }, { k: '관심 다리', v: D.focus ? LIMB[D.focus] : '미선택', sub: '' },
          { k: '기준 회차', v: bR ? `${bR.date} · ${sessNo(bR)}회차` : '없음', sub: D.base ? '' : bR ? '가장 이른 회차로 자동 지정' : '' }, { k: '내부 메모', v: D.memo || '없음', sub: '보고서에는 넣지 않아요' }],
        hist: all.map((r, i) => { const stt = ST[r.st]; return { title: `${sessNo(r)}회차 · ${r.date}`, sub: r.st === 'fail' ? `체중 ${r.w}kg · 쓸 수 있는 통과 없음` : `체중 ${r.w}kg · 유효 통과 ${r.ps[1]} · 모델 ${r.model}`, base: r.id === bId, rep: !!r.rep, canBase: r.st !== 'fail' && r.id !== bId,
          setBase: e => { e.stopPropagation(); this.setState(st => ({ dogs: st.dogs.map(x => x.id === D.id ? { ...x, base: r.id } : x) })); this.toast(`${r.date} 회차를 기준으로 정했어요`); },
          st: stt[0], bg: stt[1], c: stt[2], bt: i ? '1px solid #F2EFEA' : 'none', open: () => this.openRes(r.id) }; }),
        has: all.length > 0, none: !all.length, count: all.length + '회차',
        edit: () => { this.setState({ petMode: 'edit', petId: D.id, pet: { ...EMPTY_PET, ...D, size: D.sizeManual ? D.size : null } }); this.nav('petNew'); },
        compare: () => valid(D.id).length < 2 ? this.toast('유효한 회차가 2개 이상 있어야 비교할 수 있어요') : (this.setState({ cmp: 'base' }), this.nav('compare')),
        start: () => { this.setState({ capDog: D.id, shots: 0, sessW: '' }); this.nav('capSelect'); } };
    }

    const R = s.results.find(r => r.id === s.resId) || s.results[0];
    const G = s.gait || 'trot';
    let rd = { ok: false, fail: false, part: false, rows: [], rank: [], ex: [], name: '', when: '', st: '', bg: '', c: '', topTitle: '', topSub: '' };
    let rp = { title: '', summary: '', items: [], rows: [], when: '', cond: '' };
    if (R) {
      const d = dogById(R.dog) || { name: '-' }, stt = ST[R.st];
      rd = { ...rd, name: d.name, when: `${R.date} · ${sessNo(R)}회차 · 체중 ${R.w}kg`, st: stt[0], bg: stt[1], c: stt[2], fail: R.st === 'fail', ok: R.st !== 'fail', part: R.st === 'part' };
      if (R.st !== 'fail') {
        const vv = valid(R.dog), idx = vv.findIndex(x => x.id === R.id), P = vv[idx + 1];
        const sd = delta(R.sym, P && P.sym, '%p'), rdl = delta(R.rom, P && P.rom, '°');
        const rows = mrows(R, G), rowsT = mrows(R, 'trot');
        const rank = rs => rs.filter(x => !x.na).map(x => { const df = Math.abs(x.l - x.r); return { ...x, df, si: df / ((x.l + x.r) / 2) * 100 }; }).sort((a, b) => b.si - a.si);
        const meas = rank(rows), top = meas[0], topT = rank(rowsT)[0];
        const sL = Math.round(R.sL * 1.5), sR = Math.round(R.sR * 1.5);
        Object.assign(rd, { sym: R.sym, symD: sd[0], symDC: sd[1], rom: R.rom, romD: rdl[0], romDC: rdl[1], sL, sR, stD: sL === sR ? '좌우 같음' : `${sL > sR ? '오른쪽' : '왼쪽'}이 ${Math.abs(sL - sR)}%p 짧음`, stC: '#5B6472',
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
          cond: `측면 촬영 · 영상 16개 · 통과 ${R.ps[0]}개 중 ${R.ps[1]}개 사용 · 분석 모델 pga-pose ${R.model}. 측정 불가 항목은 사유와 함께 표시했습니다.` };
      }
    }

    const CD = dogById(s.dogSel) || s.dogs[0];
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

    const orgOk = [s.to[0], s.to[1], s.to[2]].every(Boolean) && s.so.org && s.so.dev && s.so.id.length >= 4 && s.so.pw.length >= 4 && s.so.pw === s.so.pw2;
    const setSo = k => e => { const v = e.target.value; this.setState(st => ({ so: { ...st.so, [k]: v } })); };
    const setPet = k => e => { const v = e.target.value; this.setState(st => ({ pet: { ...st.pet, [k]: v } })); };
    const termRows = (key, labels) => labels.map(([label, view], i) => ({ label, view, c: chk(s[key][i]), toggle: () => this.setState(st => { const a = [...st[key]]; a[i] = !a[i]; return { [key]: a }; }) }));

    const showTabs = li && ['home', 'results', 'my', 'story'].includes(sc);
    const tbOn = k => { const on = (k === 'home' && sc === 'home') || (k === 'story' && sc === 'story') || (k === 'results' && sc === 'results') || (k === 'my' && sc === 'my'); return { bg: on ? '#F1EEE9' : 'transparent', c: on ? '#B4501A' : '#8E949C', w: on ? 700 : 500 }; };
    const dark = ['landing', 'capGuide'].includes(sc);
    const landscape = sc === 'capGuide' && s.rotDone;
    const page = s.page;
    const pagesCopy = [
      ['', '반려견을 평소처럼 걷게 합니다.', '', 'transparent', 0],
      ['', '반려견이 걷는 모습을 옆에서 촬영합니다.', '', 'transparent', 1],
      ['', 'AI 모델이 관절점을 찾고,\n보행 패턴을 분석합니다.', '', 'transparent', 2],
      ['', '결과를 보고서로 받아\nPDF로 저장할 수 있습니다.', '', 'transparent', 3]];
    const filtDogs = s.results.filter(r => dogById(r.dog) && (s.filt === 'all' || r.dog === s.filt));
    const hasR1 = !!s.results.find(r => r.id === 'r2');
    const jumps = [['스플래시', 'splash', 0], ['랜딩', 'landing', 0], ['서비스 소개', 'story', 0], ['로그인', 'login', 0], ['기관 회원가입', 'signupOrg', 0], ['홈 · 반려견 목록', 'home', 1], ['반려견 상세 · 측정 이력', 'dog', 1], ['반려견 등록', 'petNew', 1], ['알림', 'notif', 1], ['촬영 · 반려견 선택', 'capSelect', 1], ['촬영 화면', 'capGuide', 1], ['영상 첨부 (16개)', 'capReview', 1], ['분석 중', 'analyzing', 1], ['분석 결과', 'results', 1], ['회차 결과', 'detail', 1, 'r1'], ['회차 결과 · 실패', 'detail', 1, 'r3'], ['보고서', 'report', 1], ['경과 비교', 'compare', 1], ['마이페이지', 'my', 1], ['기본 정보', 'account', 1]];
    const isOrg = true;
    const capD = dogById(s.capDog) || {};
    const autoSz = autoSize(s.pet.breed, s.pet.kg);

    return {
      isSplash: sc === 'splash', isLanding: sc === 'landing', isLogin: sc === 'login', isSignupOrg: sc === 'signupOrg',
      isHome: sc === 'home', isDog: sc === 'dog', isPetNew: sc === 'petNew', isNotif: sc === 'notif', isStory: sc === 'story', isCapSelect: sc === 'capSelect', isCapGuide: sc === 'capGuide',
      isCapReview: sc === 'capReview', isAnalyzing: sc === 'analyzing', isResults: sc === 'results', isDetail: sc === 'detail', isReport: sc === 'report', isCompare: sc === 'compare', isMy: sc === 'my', isAccount: sc === 'account',
      vid: this.vid, storyRef: this.storyRef, repBox: this.repBox, back: this.back,
      jointOp: s.joint ? 1 : 0, jointTr: s.joint ? 'opacity 0.5s ease-out' : 'none', replaySplash: () => this.startSplash(),
      lines: LINES.map((t, i) => ({ t, op: i === s.line ? 1 : 0, ty: i === s.line ? 0 : (i < s.line ? -14 : 14) })),
      goStory: () => this.nav('story'), openStart: () => this.nav('signupOrg'), goLogin: () => this.nav('login'),
      fLoginId: s.li.id, fLoginPw: s.li.pw,
      onLoginId: e => { const v = e.target.value; this.setState(st => ({ li: { ...st.li, id: v } })); },
      onLoginPw: e => { const v = e.target.value; this.setState(st => ({ li: { ...st.li, pw: v } })); },
      loginBg: s.li.id.length >= 2 && s.li.pw.length >= 4 ? '#D2601A' : '#C3C8CF',
      doLogin: () => { if (s.li.id.length >= 2 && s.li.pw.length >= 4) this.login(DEMO, true); else this.toast('아이디와 비밀번호를 입력해 주세요'); },
      loginSub: '동물병원·재활센터 계정으로 로그인해요.', loginIdLabel: '아이디', loginIdPh: '가입할 때 만든 아이디',
      orgFields: [
        { label: '기관명', ph: '예) 한빛동물병원', type: 'text', val: s.so.org, on: setSo('org') },
        { label: '기관 주소', ph: '주소 검색', type: 'text', val: s.so.loc, on: setSo('loc') },
        { label: '디바이스 번호', ph: '예) PP-2410-0381', type: 'text', val: s.so.dev, on: setSo('dev'), hint: '측정 기기 뒷면 라벨에 적혀 있어요.', hc: '#5B6472' }],
      orgAcctFields: [
        { label: '아이디', ph: '영문·숫자 4~16자', type: 'text', val: s.so.id, on: setSo('id') },
        { label: '비밀번호', ph: '4자 이상', type: 'password', val: s.so.pw, on: setSo('pw') },
        { label: '비밀번호 확인', ph: '한 번 더 입력', type: 'password', val: s.so.pw2, on: setSo('pw2'), hint: s.so.pw2 && s.so.pw !== s.so.pw2 ? '비밀번호가 달라요' : false, hc: '#C2412D' }],
      allOrgC: chk(s.to.every(Boolean)), allOrgToggle: () => this.setState(st => ({ to: st.to.map(() => !st.to.every(Boolean)) })),
      termsOrg: termRows('to', [['[필수] 서비스 이용약관', true], ['[필수] 개인정보 수집 및 이용', true], ['[필수] 측정 기기 연동 및 위치정보 이용', true], ['[선택] 마케팅 정보 수신', true]]),
      signOrgBg: orgOk ? '#D2601A' : '#C3C8CF',
      doSignupOrg: () => { if (!orgOk) return this.toast(![s.to[0], s.to[1], s.to[2]].every(Boolean) ? '필수 약관에 동의해 주세요' : (s.so.pw2 && s.so.pw !== s.so.pw2) ? '비밀번호가 서로 달라요' : '입력하지 않은 항목이 있어요'); this.login({ type: 'org', name: s.so.org, id: s.so.id, loc: s.so.loc || '-', dev: s.so.dev }, false); this.toast(`${s.so.org} 가입을 환영해요`); },

      acctKind: '기관', acctName: s.acct.name,
      goNotif: () => this.nav('notif'), tabMy: () => this.tab('my'), tabHome: () => this.tab('home'), tabResults: () => this.tab('results'), tabStory: () => this.tab('story'), tabCapture: () => this.tab('capSelect'),
      hasDogs: s.dogs.length > 0, noDogs: !s.dogs.length, dogCount: s.dogs.length + '마리',
      q: s.q, onQ: e => { const v = e.target.value; this.setState({ q: v }); }, homeDogs, noMatch: !!qq && !shown.length,
      goPetNew: this.goPetNew, goCapture: this.goCapture, dd,
      anaOn: !!ana, goAnalyzing: () => this.nav('analyzing'), anaName: anaDog ? anaDog.name : '', anaPct: Math.round(anaP / 5 * 100), anaN: anaFloor + 1, anaStep: STEPS[anaFloor],
      prints: (() => { const ph = Math.floor(Date.now() / 420) % 11; return Array.from({ length: 8 }, (_, i) => { const on = ph <= 8 ? i < ph : ph === 9; const jx = [0, 6, -8, 4, -4, 10, -2, 5][i], jr = -23 + [7, -4, 10, -8, 4, -10, 8, -5][i]; return { x: (i % 2 ? 236 : 118) + jx * 2 + Math.round(Math.sin(i * 0.9) * 22), y: 656 - i * 68 + (i % 2 ? 10 : 0), r: jr, op: on ? 1 : 0, s: on ? 1 : 0.7 }; }); })(),

      petTitle: s.petMode === 'edit' ? '반려견 정보 수정' : '반려견 등록', petCta: s.petMode === 'edit' ? '저장하기' : '등록하기',
      petFields: [
        { label: '이름', ph: '예) 보리', val: s.pet.name, on: setPet('name') },
        (() => {
          const q = s.pet.breed.trim().replace(/\s/g, '');
          const list = q ? BREEDS.filter(b => b.replace(/\s/g, '').includes(q)).slice(0, 6) : [];
          const exact = BREEDS.includes(s.pet.breed);
          return { label: '견종', ph: '견종을 입력하면 목록이 떠요', val: s.pet.breed, on: setPet('breed'), showSug: !!q && !exact, noSug: !!q && !exact && !list.length,
            sugs: list.map((name, i) => ({ name, bt: i ? '1px solid #F2EFEA' : 'none', pick: () => this.setState(st => ({ pet: { ...st.pet, breed: name } })) })) };
        })(),
        { label: '체중 (kg)', ph: '예) 28.4', val: s.pet.kg, on: setPet('kg') },
        { label: '출생연도 (선택)', ph: '예) 2019', val: s.pet.birth, on: setPet('birth') }],
      sexes: Object.entries(SEX).map(([k, label]) => ({ label, ...pick(s.pet.sex === k), pick: () => this.setState(st => ({ pet: { ...st.pet, sex: k } })) })),
      sizes: Object.entries(SIZE).map(([k, label]) => ({ label, ...pick((s.pet.size || autoSz) === k), pick: () => this.setState(st => ({ pet: { ...st.pet, size: st.pet.size === k ? null : k } })) })),
      sizeNote: s.pet.size ? '직접 선택 · 다시 누르면 자동 분류' : '견종·체중으로 자동 분류돼요',
      limbs: Object.entries(LIMB).map(([k, label]) => ({ label, ...pick(s.pet.focus === k), pick: () => this.setState(st => ({ pet: { ...st.pet, focus: st.pet.focus === k ? null : k } })) })),
      petRehab: s.pet.rehab, onRehab: setPet('rehab'), petMemo: s.pet.memo, onMemo: setPet('memo'),
      petBg: s.pet.name && s.pet.breed && s.pet.kg ? '#D2601A' : '#C3C8CF',
      doPetNew: () => {
        if (!s.pet.name || !s.pet.breed || !s.pet.kg) return this.toast('이름·견종·체중을 입력해 주세요');
        const save = { ...s.pet, size: s.pet.size || autoSz, sizeManual: !!s.pet.size };
        if (s.petMode === 'edit') { this.setState(st => ({ dogs: st.dogs.map(d => d.id === st.petId ? { ...d, ...save } : d) })); this.back(); this.toast('저장했어요'); }
        else { const id = 'p' + Date.now(); this.setState(st => ({ dogs: [...st.dogs, { id, ...save }] })); this.back(); this.toast(`${s.pet.name} 등록을 마쳤어요`); }
      },

      notifs: (hasR1 ? [
        { title: `${anaDog ? anaDog.name : '콩이'} 분석이 진행 중이에요`, body: '영상 16개의 관절점을 찾고 있어요. 끝나면 알려 드릴게요.', when: '방금', dot: ana ? '#D2601A' : '#C9C4BC', open: () => ana ? this.nav('analyzing') : this.tab('results') },
        { title: '두부 보고서가 만들어졌어요', body: '보호자용·수의사용 보고서를 확인해 보세요.', when: '어제 17:42', dot: '#D2601A', open: () => this.openRes('r2') },
        { title: '탄이 분석에 실패했어요', body: '쓸 수 있는 통과가 없었어요. 다시 촬영해 주세요.', when: '어제 11:06', dot: '#C9C4BC', open: () => this.openRes('r3') },
        { title: '보리 정기 측정 시기예요', body: '마지막 측정 후 2주가 지났어요.', when: '10월 14일', dot: '#C9C4BC', open: () => { this.setState({ capDog: 'd1', shots: 0 }); this.nav('capSelect'); } }]
        : [{ title: '가입을 환영해요', body: '반려견을 등록하고 첫 보행 영상을 찍어 보세요.', when: '방금', dot: '#D2601A', open: this.goPetNew }]),

      storyBack: !li || s.stack.length > 0, storyTitlePad: !li || s.stack.length > 0 ? 0 : 12, storyBottom: showTabs ? 96 : 0,
      onStory: e => { const p = Math.round(e.target.scrollLeft / e.target.clientWidth); if (p !== this.state.page) { if (p === 2) this.moStart = Date.now(); this.setState({ page: p }); } },
      pages: pagesCopy.map((c, i) => ({ num: String(i + 1).padStart(2, '0'), tag: c[0], title: c[1], body: c[2], vbg: c[3], vh: c[4] === 3 ? 'auto' : (s.repH || 480) + 'px', v0: c[4] === 0, v1: c[4] === 1, v2: c[4] === 2, v3: c[4] === 3 })),
      pageDots: pagesCopy.map((_, i) => ({ w: i === page ? 18 : 6, c: i === page ? '#1B2433' : 'rgba(27,36,51,.2)' })),
      storyBtn: page < 3 ? '다음' : li ? '촬영하기' : '시작하기', storyBtnBg: page < 3 ? '#1B2433' : '#D2601A',
      storyKneeL: knee(53), storyKneeR: knee(46),
      mo: (() => {
        const T = 6.4, t = ((Date.now() - (this.moStart || 0)) / 1000) % T;
        const cl = v => Math.max(0, Math.min(1, v)), ez = v => v * v * (3 - 2 * v);
        const z = ez(cl((t - 0.4) / 1.4)), sk = ez(cl((t - 2.0) / 1.2)), m = ez(cl((t - 3.6) / 1.0)), out = ez(cl((t - 5.7) / 0.5));
        const k = 372 / 1254, SX = 2.069, SY = 2.036, TX = k * -701, OFF = ((s.repH || 480) - 372) / 2, TY = (OFF - 23) + k * -520 - OFF * SY;
        return { t1: `translate(${(z * TX).toFixed(2)}px,${(z * TY).toFixed(2)}px) scale(${(1 + z * (SX - 1)).toFixed(4)},${(1 + z * (SY - 1)).toFixed(4)})`, o1: ((1 - m) * (1 - out)).toFixed(3), o3: (sk * (1 - m)).toFixed(3), o2: (m * (1 - out)).toFixed(3) };
      })(),
      prevOp: page > 0 ? 1 : 0.35, prevPe: page > 0 ? 'auto' : 'none',
      storyPrev: () => { const el = this.storyEl; if (page > 0 && el) el.scrollTo({ left: (page - 1) * el.clientWidth, behavior: 'smooth' }); },
      storyNext: () => { const el = this.storyEl; if (page < 3 && el) el.scrollTo({ left: (page + 1) * el.clientWidth, behavior: 'smooth' }); else if (page >= 3) { li ? this.goCapture() : this.nav('signupOrg'); } },

      capDogs: s.dogs.map(d => { const on = d.id === s.capDog; return { init: d.name[0], name: d.name, desc: desc(d), bd: on ? '#D2601A' : '#ECE8E2', dot: on ? '#D2601A' : 'transparent', pick: () => this.setState({ capDog: d.id }) }; }),
      sessW: s.sessW, onSessW: e => { const v = e.target.value; this.setState({ sessW: v }); }, sessWPh: capD.kg ? `등록 체중 ${capD.kg}` : '예) 28.1',
      fromGallery: () => { if (s.shots >= 16) return this.toast('영상 16개를 모두 첨부했어요'); this.addShot(); },
      goCapGuide: this.goCapGuide,
      capDogName: capD.name || '',
      slots: Array.from({ length: 16 }, (_, i) => { const done = i < s.shots, next = i === s.shots; return { n: i + 1, done, next, bg: done ? '#141B22' : next ? '#FCEEE3' : '#F4F1EC', bs: next ? 'dashed' : 'solid', bd: done ? '#141B22' : next ? '#D2601A' : '#ECE8E2', nc: done ? 'rgba(255,255,255,.75)' : next ? '#B4501A' : '#A0A7B2', cur: next ? 'pointer' : 'default', tap: next ? this.goCapGuide : () => {} }; }),
      shotN: s.shots, shotPct: Math.round(s.shots / 16 * 100), moreOp: s.shots >= 16 ? 0.4 : 1,
      shotHint: s.shots >= 16 ? '16개를 모두 첨부했어요. 분석을 시작해 주세요.' : `${s.shots + 1}번째 영상을 이어서 찍어 주세요. 16개를 모두 채우면 결과가 더 정확해요.`,
      rotHint: !s.rotDone, rotDone: !!s.rotDone, rotDeg: s.rotAnim ? 90 : 0,
      recTime: `영상 ${Math.min(16, s.shots + 1)}/16 · 00:0${Math.floor(s.rec)} / 00:04`, recPillBg: s.recOn ? '#C2412D' : 'rgba(14,18,23,.55)', recDot: s.recOn ? '#fff' : '#E5604D',
      recBtnS: s.recOn ? 30 : 62, recBtnR: s.recOn ? 8 : 31, capHint: s.recOn ? '반려견이 옆으로 천천히 걷게 해 주세요' : '점선 안에 반려견 옆모습이 들어오게 맞춰 주세요',
      toggleRec: () => { if (s.recOn) { if (s.rec >= 2) this.addShot(); else { this.setState({ recOn: false, rec: 0 }); this.toast('2초 이상 찍어 주세요'); } } else this.setState({ recOn: true, rec: 0 }); },
      startAna: () => { if (!s.shots) return this.toast('영상을 1개 이상 첨부해 주세요'); this.setState({ ana: { dog: s.capDog, p: 0, n: s.shots, w: s.sessW }, screen: 'analyzing', stack: [] }); },

      filters: [{ id: 'all', label: '전체' }, ...s.dogs.map(d => ({ id: d.id, label: d.name }))].map(f => { const on = s.filt === f.id; return { label: f.label, bg: on ? '#1B2433' : '#fff', c: on ? '#fff' : '#3A4250', bd: on ? '#1B2433' : '#ECE8E2', pick: () => this.setState({ filt: f.id }) }; }),
      resList: filtDogs.map((r, i) => ({ name: dogById(r.dog).name, when: `${r.date} · ${sessNo(r)}회차`, st: ST[r.st][0], bg: ST[r.st][1], c: ST[r.st][2], sym: r.st === 'fail' ? '다시 촬영 필요' : `유효 통과 ${r.ps[1]}`, bt: i ? '1px solid #F2EFEA' : 'none', open: () => this.openRes(r.id) })),
      hasRes: filtDogs.length > 0, noRes: !filtDogs.length,
      rd, retake: () => { if (R) this.setState({ capDog: R.dog, shots: 0 }); this.nav('capSelect'); },
      gaitSegs: seg([['walk', '평보'], ['trot', '속보']], G, 'gait'), gaitName: G === 'walk' ? '평보' : '속보',
      openRep: () => { this.setState({ repType: 'g' }); this.nav('report'); },
      openCompare: () => { if (!R) return; if (valid(R.dog).length < 2) return this.toast('유효한 회차가 2개 이상 있어야 비교할 수 있어요'); this.setState({ dogSel: R.dog, cmp: 'base' }); this.nav('compare'); },
      partMsg: '일부 통과에서 다리가 가려지거나 뛰어서 해당 통과를 제외하고 계산했습니다.',
      rp, isRepG: s.repType === 'g', isRepV: s.repType === 'v', repKind: s.repType === 'v' ? '보행 분석 보고서 · 수의사용' : '보행 분석 보고서 · 보호자용',
      repStatus: R ? `생성 완료 · ${s.repType === 'v' ? '9.1' : '8.4'}초 · 분석 모델 ${R.model} · 템플릿 1.0` : '',
      repSegs: seg([['g', '보호자용'], ['v', '수의사용']], s.repType, 'repType'),
      regenRep: () => this.toast('보고서를 다시 만들고 있어요'), saveRep: () => this.toast('PDF를 내려받았어요'),

      cp, cmpSegs: seg([['base', '기준 회차 대비'], ['prev', '직전 회차 대비']], s.cmp || 'base', 'cmp'),
      trendKs: [['rom', '무릎 가동 범위'], ['stride', '걸음 길이'], ['stance', '입각기 비율'], ['sym', '대칭 지수']].map(([k, label]) => { const on = (s.tk || 'rom') === k; return { label, bg: on ? '#1B2433' : '#fff', c: on ? '#fff' : '#3A4250', bd: on ? '#1B2433' : '#ECE8E2', pick: () => this.setState({ tk: k }) }; }),
      reanalyze: () => this.toast('새 모델로 재분석을 요청했어요'),

      isOrg, isUser: false, myName: s.acct.name, myDev: s.acct.dev || '-',
      goAccount: () => this.nav('account'), help: () => this.toast('고객센터로 연결할게요'), settings: () => this.toast('앱 설정은 준비 중이에요'),
      myDogs: s.dogs.map(d => ({ init: d.name[0], name: d.name, desc: desc(d) + ' · ' + SEX[d.sex || 'm'], edit: () => { this.setState({ petMode: 'edit', petId: d.id, pet: { ...EMPTY_PET, ...d, size: d.sizeManual ? d.size : null } }); this.nav('petNew'); }, del: () => this.setState({ sheet: 'del', delId: d.id }) })),
      myDogCount: s.dogs.length + '마리',
      tgBg: s.notifOn ? '#D2601A' : '#DDD7CE', tgX: s.notifOn ? 22 : 2, toggleNotif: () => this.setState(st => ({ notifOn: !st.notifOn })),
      askLogout: () => this.setState({ sheet: 'logout' }),
      acctRows: [['계정 유형', '기관 회원'], ['기관명', s.acct.name], ['아이디', s.acct.id || '-'], ['기관 주소', s.acct.loc || '-'], ['디바이스 번호', s.acct.dev || '-'], ['가입일', '2026년 10월 2일']].map(([k, v], i) => ({ k, v, bt: i ? '1px solid #F2EFEA' : 'none' })),
      editAcct: () => this.toast('정보 수정은 준비 중이에요'),

      showTabs, tb: { home: tbOn('home'), story: tbOn('story'), results: tbOn('results'), my: tbOn('my') },
      sheetLogin: s.sheet === 'login', sheetDel: s.sheet === 'del', sheetLogout: s.sheet === 'logout', anySheet: !!s.sheet,
      closeSheet: () => this.setState({ sheet: null }),
      goSignupOrg: () => this.nav('signupOrg'), sheetToLogin: () => this.nav('login'),
      delName: (dogById(s.delId) || {}).name || '',
      confirmDel: () => { const n = (dogById(s.delId) || {}).name; this.setState(st => ({ dogs: st.dogs.filter(d => d.id !== st.delId), results: st.results.filter(r => r.dog !== st.delId), sheet: null, filt: 'all', ana: st.ana && st.ana.dog === st.delId ? null : st.ana })); this.toast(`${n} 정보를 삭제했어요`); },
      confirmLogout: () => this.setState({ loggedIn: false, screen: 'landing', stack: [], sheet: null, li: { id: '', pw: '' } }),
      toastOn: !!s.toast, toastMsg: s.toast,
      statusC: landscape ? 'transparent' : dark ? '#fff' : '#1B2433', indC: dark ? '#fff' : '#1B2433', indOp: landscape ? 0 : dark ? 0.8 : 0.25,
      jumps: jumps.map(j => { const on = sc === j[1] && (j[3] && j[1] === 'detail' ? s.resId === j[3] : true); return { label: j[0], bg: on ? '#1B2433' : '#fff', c: on ? '#fff' : '#1B2433', go: () => this.jump(j) }; })
    };
  }
}

