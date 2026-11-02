// 공통: 알림(toast), 화면 바로가기, 모달 열고 닫기, 분석 완료 알림
(function () {
  var toastEl = document.getElementById('toast'), toastMsg = document.getElementById('toastMsg'), tt;
  window.ppToast = function (m) {
    toastMsg.textContent = m;
    toastEl.style.display = 'flex';
    clearTimeout(tt);
    tt = setTimeout(function () { toastEl.style.display = 'none'; }, 2400);
  };
  if (window.PP.toast) window.ppToast(window.PP.toast);

  // 화면 바로가기 (PP_JUMPS=1 로 켰을 때만 있다)
  var menu = document.getElementById('jumpMenu'), jumpBtn = document.getElementById('jumpBtn');
  if (jumpBtn) jumpBtn.addEventListener('click', function () {
    menu.style.display = menu.style.display === 'flex' ? 'none' : 'flex';
  });

  // 모달: data-open="id" 로 열고, 배경 · X · data-close 로 닫는다
  window.ppOpen = function (id) { var m = document.getElementById(id); if (m) m.style.display = 'flex'; };
  window.ppClose = function (el) { var m = el.closest('.pp-modal'); if (m) m.style.display = 'none'; };
  document.addEventListener('keydown', function (e) {
    var box = document.getElementById('lightbox');
    if (e.key === 'Escape' && box && box.style.display === 'flex') box.style.display = 'none';
  });
  document.addEventListener('click', function (e) {
    var o = e.target.closest('[data-open]');
    if (o) { e.preventDefault(); window.ppOpen(o.dataset.open); return; }
    var c = e.target.closest('[data-close]');
    if (c) { e.preventDefault(); window.ppClose(c); return; }
    if (e.target.classList && e.target.classList.contains('pp-modal')) e.target.style.display = 'none';
    // 영상·사진: 누르면 화면 가운데 크게. 배경·닫기·Esc 로 닫는다
    var lb = e.target.closest('[data-lightbox]');
    if (lb) {
      e.preventDefault();
      var box = document.getElementById('lightbox');
      box.querySelector('img').src = lb.getAttribute('href');
      box.querySelector('img').alt = lb.dataset.caption || '';
      box.querySelector('.lb-cap').textContent = lb.dataset.caption || '';
      box.querySelector('.lb-orig').href = lb.getAttribute('href');
      box.style.display = 'flex';
      return;
    }
    var t = e.target.closest('[data-toast]');
    if (t) { e.preventDefault(); window.ppToast(t.dataset.toast); return; }
    // 행 전체를 누르면 이동 (안의 버튼 · 폼은 제외)
    var row = e.target.closest('[data-href]');
    if (row && !e.target.closest('form, button, a')) location.href = row.dataset.href;
  });

  // 작성자 이름: 로그인한 담당자 이름을 기본으로 채운다(고칠 수 있다). 이름이 없으면 이 브라우저에서 마지막에 쓴 이름
  var AUTHOR = 'pp_author', last = document.body.dataset.me || '';
  if (!last) { try { last = localStorage.getItem(AUTHOR) || ''; } catch (e) {} }
  document.querySelectorAll('input.author-inp').forEach(function (i) { if (!i.value) i.value = last; });
  document.addEventListener('submit', function (e) {
    var i = e.target.querySelector && e.target.querySelector('input.author-inp');
    if (i && i.value.trim()) { try { localStorage.setItem(AUTHOR, i.value.trim()); } catch (err) {} }
  }, true);

  // 다른 화면에 있을 때 분석이 끝나면 알림 (디자인: "콩이 분석이 끝났어요")
  if (window.PP.pollNotices) {
    var timer = setInterval(function () {
      fetch('/api/notices').then(function (r) { return r.json(); }).then(function (d) {
        if (d.notices.length) {
          window.ppToast(d.notices[0]);
          document.querySelectorAll('.live-badge').forEach(function (b) { b.remove(); });
        }
        if (!d.active) clearInterval(timer);
      }).catch(function () {});
    }, 1500);
  }
})();
