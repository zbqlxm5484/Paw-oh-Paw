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
  document.addEventListener('click', function (e) {
    var o = e.target.closest('[data-open]');
    if (o) { e.preventDefault(); window.ppOpen(o.dataset.open); return; }
    var c = e.target.closest('[data-close]');
    if (c) { e.preventDefault(); window.ppClose(c); return; }
    if (e.target.classList && e.target.classList.contains('pp-modal')) e.target.style.display = 'none';
    var t = e.target.closest('[data-toast]');
    if (t) { e.preventDefault(); window.ppToast(t.dataset.toast); return; }
    // 행 전체를 누르면 이동 (안의 버튼 · 폼은 제외)
    var row = e.target.closest('[data-href]');
    if (row && !e.target.closest('form, button, a')) location.href = row.dataset.href;
  });

  // 작성자 이름: 기관 계정을 여러 명이 번갈아 써서 기록마다 이름을 받는다. 이 브라우저에서 마지막에 쓴 이름을 채워 둔다
  var AUTHOR = 'pp_author', last = '';
  try { last = localStorage.getItem(AUTHOR) || ''; } catch (e) {}
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
