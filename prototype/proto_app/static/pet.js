// 반려견 등록 · 수정 모달: 견종 자동완성, 성별 · 체급 · 관심 다리 고르기, 체급 자동 분류
(function () {
  var form = document.getElementById('petForm');
  if (!form) return;
  var BREEDS = window.PP.breeds, DOGS = window.PP.dogs;
  var SMALL = ['말티즈', '푸들', '토이 푸들', '포메라니안', '시츄', '치와와', '비숑 프리제', '요크셔테리어', '닥스훈트', '미니어처 슈나우저', '퍼그', '이탈리안 그레이하운드', '잭 러셀 테리어'];
  var LARGE = ['골든 리트리버', '래브라도 리트리버', '사모예드', '시베리안 허스키', '저먼 셰퍼드', '말라뮤트', '풍산개'];
  var el = function (n) { return form.elements[n]; };
  var sug = document.getElementById('breedSug');

  function autoSize() {
    var b = el('breed').value, kg = +el('kg').value;
    if (SMALL.indexOf(b) >= 0) return 'S';
    if (LARGE.indexOf(b) >= 0) return 'L';
    if (BREEDS.indexOf(b) >= 0 && b !== '믹스견') return 'M';
    return kg ? (kg < 10 ? 'S' : kg < 25 ? 'M' : 'L') : 'M';
  }
  function paint() {
    form.querySelectorAll('.pick').forEach(function (p) {
      var f = p.dataset.field, cur = el(f).value || (f === 'size' ? autoSize() : '');
      var on = cur === p.dataset.val;
      p.style.borderColor = on ? '#D2601A' : '#ECE8E2';
      p.style.background = on ? '#FCEEE3' : '#fff';
      p.style.color = on ? '#A8481A' : '#3A4250';
    });
    document.getElementById('sizeNote').textContent = el('size').value ? '직접 선택 · 다시 누르면 자동 분류' : '견종·체중으로 자동 분류돼요';
    document.getElementById('petCta').style.background = el('name').value && el('breed').value && el('kg').value ? '#D2601A' : '#C3C8CF';
    // 견종 자동완성
    var q = el('breed').value.trim().replace(/\s/g, ''), exact = BREEDS.indexOf(el('breed').value) >= 0;
    var list = q ? BREEDS.filter(function (b) { return b.replace(/\s/g, '').indexOf(q) >= 0; }).slice(0, 6) : [];
    sug.innerHTML = '';
    if (q && !exact) {
      list.forEach(function (name, i) {
        var d = document.createElement('div');
        d.className = 'hv-menu';
        d.textContent = name;
        d.style.cssText = 'min-height:44px;padding:0 16px;display:flex;align-items:center;font-size:15px;cursor:pointer;border-top:' + (i ? '1px solid #F2EFEA' : 'none');
        d.addEventListener('mousedown', function (e) { e.preventDefault(); el('breed').value = name; paint(); });
        sug.appendChild(d);
      });
      if (!list.length) {
        var n = document.createElement('div');
        n.textContent = '목록에 없어요 · 입력한 이름으로 등록돼요';
        n.style.cssText = 'min-height:44px;padding:0 16px;display:flex;align-items:center;font-size:14px;color:#5B6472';
        sug.appendChild(n);
      }
      sug.style.display = 'flex';
    } else sug.style.display = 'none';
  }

  form.querySelectorAll('.pick').forEach(function (p) {
    p.addEventListener('click', function () {
      var f = el(p.dataset.field);
      f.value = (p.dataset.toggle && f.value === p.dataset.val) ? '' : p.dataset.val;
      paint();
    });
  });
  ['name', 'breed', 'kg'].forEach(function (n) { el(n).addEventListener('input', paint); });
  form.addEventListener('submit', function (e) {
    if (!(el('name').value && el('breed').value && el('kg').value)) { e.preventDefault(); window.ppToast('이름·견종·체중을 입력해 주세요'); }
  });

  // data-pet="new" 또는 data-pet="<반려견 id>"로 연다
  window.ppOpenPet = function (id) {
    var d = id && id !== 'new' ? DOGS[id] : null;
    form.reset();
    el('dog_id').value = d ? d.id : '';
    ['name', 'breed', 'kg', 'birth', 'rehab', 'memo'].forEach(function (n) { el(n).value = d ? (d[n] || '') : ''; });
    el('sex').value = d ? (d.sex || 'm') : 'm';
    el('size').value = d && d.size_manual ? d.size : '';
    el('focus').value = d && d.focus ? d.focus : '';
    document.getElementById('petTitle').textContent = d ? '반려견 정보 수정' : '반려견 등록';
    document.getElementById('petCta').textContent = d ? '저장하기' : '등록하기';
    paint();
    window.ppOpen('petModal');
  };
  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-pet]');
    if (t) { e.preventDefault(); e.stopPropagation(); window.ppOpenPet(t.dataset.pet); }
  }, true);
  if (window.PP.openPet) window.ppOpenPet('new');
})();
