// 영상 업로드: 반려견 고르기, 영상 16개까지 차례로 첨부(끌어 놓기 · 고르기), 분석 시작
(function () {
  var cfg = window.UPLOAD, form = document.getElementById('upForm');
  var picker = document.getElementById('fileInput'), field = document.getElementById('filesField');
  var files = [], demo = cfg.demo, previewUrl = null;
  var $ = function (id) { return document.getElementById(id); };
  var count = function () { return files.length || demo; };

  // 1. 반려견 선택
  var dogs = Array.prototype.slice.call(document.querySelectorAll('.up-dog'));
  function pickDog(el) {
    form.elements.dog.value = el.dataset.id;
    dogs.forEach(function (d) {
      var on = d === el, av = d.querySelector('.av'), nm = d.querySelector('.nm');
      av.style.boxShadow = on ? '0 0 0 3px #FAF9F6,0 0 0 6px #D2601A' : 'none';
      av.style.background = on ? '#FCEEE3' : '#EEEAE4';
      av.style.color = on ? '#A8481A' : '#7A808A';
      nm.style.color = on ? '#1B2433' : '#5B6472';
      nm.style.fontWeight = on ? 700 : 500;
    });
    $('sessW').placeholder = el.dataset.kg ? '등록 체중 ' + el.dataset.kg : '예) 28.1';
    render();
  }
  dogs.forEach(function (d) { d.addEventListener('click', function () { pickDog(d); }); });

  // 3. 영상 첨부
  function add(list) {
    if (count() >= cfg.max) { window.ppToast('영상 ' + cfg.max + '개를 모두 첨부했어요'); return; }
    var added = 0, bad = 0;
    Array.prototype.forEach.call(list, function (f) {
      var ok = /^video\//.test(f.type) || /\.(mp4|mov|m4v)$/i.test(f.name);
      if (!ok) { bad++; return; }
      if (files.length < cfg.max) { files.push(f); added++; }
    });
    if (added) demo = 0;
    if (bad && !added) return window.ppToast('영상 파일(MP4 · MOV)만 올릴 수 있어요');
    if (added) window.ppToast(added === 1 ? files.length + '번째 영상을 첨부했어요' : '영상 ' + added + '개를 첨부했어요');
    render();
  }
  function render() {
    var n = count(), dogName = (dogs.filter(function (d) { return d.dataset.id === form.elements.dog.value; })[0] || {}).dataset;
    $('shotN').textContent = n + ' / ' + cfg.max;
    $('dropZone').style.display = n ? 'none' : 'flex';
    $('fileArea').style.display = n ? 'grid' : 'none';
    $('shotBar').style.width = Math.round(n / cfg.max * 100) + '%';
    $('fileName').textContent = (dogName ? dogName.name : '반려견') + ' · 영상 ' + n;
    $('shotHint').textContent = n >= cfg.max ? '16개를 모두 첨부했어요. 분석을 시작해 주세요.' : (n + 1) + '번째 영상을 이어서 올려 주세요. 16개를 모두 채우면 결과가 더 정확해요.';
    $('startBtn').style.background = n ? '#D2601A' : '#C3C8CF';
    // 첫 영상을 미리 보기
    var want = files.length ? files[0] : null;
    if (want && want._url !== previewUrl) { want._url = want._url || URL.createObjectURL(want); previewUrl = want._url; $('preview').src = previewUrl; }
    if (!want && previewUrl) { previewUrl = null; $('preview').src = cfg.sample; }
    // 칸 16개
    var box = $('slots'); box.innerHTML = '';
    for (var i = 0; i < cfg.max; i++) {
      var done = i < n, next = i === n, s = document.createElement('div');
      s.style.cssText = 'aspect-ratio:16 / 10;border-radius:10px;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;' +
        'background:' + (done ? '#141B22' : next ? '#FCEEE3' : '#F4F1EC') + ';border:1.5px ' + (next ? 'dashed' : 'solid') + ' ' + (done ? '#141B22' : next ? '#D2601A' : '#ECE8E2') + ';cursor:' + (next ? 'pointer' : 'default');
      if (done && files[i]) { s.title = files[i].name; }
      if (next) { s.innerHTML = '<span style="font-size:22px;font-weight:500;color:#D2601A;line-height:1">+</span>'; s.addEventListener('click', function () { picker.click(); }); }
      var num = document.createElement('span');
      num.textContent = i + 1;
      num.style.cssText = 'position:absolute;left:7px;top:4px;font-size:11px;font-weight:700;font-variant-numeric:tabular-nums;color:' + (done ? 'rgba(255,255,255,.75)' : next ? '#B4501A' : '#A0A7B2');
      s.appendChild(num);
      box.appendChild(s);
    }
  }

  $('dropZone').addEventListener('click', function () { picker.click(); });
  picker.addEventListener('change', function () { add(picker.files); picker.value = ''; });
  $('clearFiles').addEventListener('click', function () { files = []; demo = 0; render(); });
  document.querySelectorAll('.drop').forEach(function (z) {
    var bd = z.style.borderColor, bg = z.style.background;
    var reset = function () { z.style.borderColor = bd; z.style.background = bg; };
    z.addEventListener('dragover', function (e) { e.preventDefault(); z.style.borderColor = '#D2601A'; z.style.background = '#FFF6EE'; });
    z.addEventListener('dragleave', reset);
    z.addEventListener('drop', function (e) { e.preventDefault(); reset(); if (e.dataTransfer.files.length) add(e.dataTransfer.files); });
  });

  form.addEventListener('submit', function (e) {
    if (!count()) { e.preventDefault(); window.ppToast('보행 영상을 1개 이상 올려 주세요'); return; }
    var dt = new DataTransfer();
    files.forEach(function (f) { dt.items.add(f); });
    field.files = dt.files;
    form.elements.demo_count.value = files.length ? 0 : demo;
  });

  render();
})();
