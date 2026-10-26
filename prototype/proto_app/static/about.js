// 서비스 소개: 스크롤에 따라 다섯 장면이 아래에서 덮이며 바뀐다 (디자인의 scVals)
(function () {
  var story = document.getElementById('scStory');
  var layers = Array.prototype.slice.call(document.querySelectorAll('.sc-layer'));
  var steps = Array.prototype.slice.call(document.querySelectorAll('.sc-step'));
  var $ = function (id) { return document.getElementById(id); };
  var N = 5;
  var cl = function (v) { return Math.max(0, Math.min(1, v)); };

  // 보고서 카드의 곡선 (고정값)
  var pts = function (amp, ph) {
    var a = [];
    for (var i = 0; i <= 40; i++) a.push((24 + i * 7.15) + ',' + (75 - amp * Math.sin(i / 40 * Math.PI * 4 - ph)).toFixed(1));
    return a.join(' ');
  };
  $('kL').setAttribute('points', pts(48, 0));
  $('kR').setAttribute('points', pts(40, 0.5));

  var last = -1;
  function frame() {
    var r = story.getBoundingClientRect(), tot = r.height - window.innerHeight;
    var P = tot > 0 ? cl(-r.top / tot) : 0;
    if (P !== last) { last = P; apply(P); }
    requestAnimationFrame(frame);
  }

  function apply(P) {
    var sm = function (a, b) { var t = cl((P - a) / (b - a)); return t * t * (3 - 2 * t); };
    var bd = function (i) { return i / N; };
    var inP = function (i) { return i === 0 ? 1 : sm(bd(i) - 0.05, bd(i) + 0.025); };

    layers.forEach(function (el, i) {
      var nx = i < N - 1 ? inP(i + 1) : 0;
      el.style.clipPath = 'inset(' + ((1 - inP(i)) * 100).toFixed(3) + '% 0 0 0)';
      el.querySelector('.sc-scale').style.transform = 'scale(' + (1 - 0.05 * nx).toFixed(3) + ')';
      el.querySelector('.sc-dark').style.opacity = (0.35 * nx).toFixed(3);
    });

    // 영상 첨부 장면
    var u = cl((P - 0.44) / 0.12);
    $('upThumb').style.opacity = u > 0 ? 1 : 0;
    $('upBar').style.width = Math.round(u * 100) + '%';
    $('upTxt').textContent = u <= 0 ? '영상을 끌어다 놓거나 눌러서 선택' : (u < 1 ? '업로드 중 · ' + Math.round(u * 100) + '%' : '업로드 완료 · 00:12');
    $('upBox').style.borderColor = u > 0 ? '#D2601A' : '#E2DCD3';
    $('upBox').style.background = u > 0 ? '#FFF7F0' : '#FAF9F6';
    $('upBtn').style.background = u >= 1 ? '#D2601A' : '#E2DCD3';

    // AI 분석 장면
    var an = cl((P - 0.63) / 0.14), kx = cl((P - 0.62) / 0.1) * 100;
    $('anPct').textContent = Math.round(an * 100) + '%';
    $('anBar').style.width = Math.round(an * 100) + '%';
    $('kpImg').style.clipPath = 'inset(0 ' + (100 - kx).toFixed(3) + '% 0 0)';
    $('kpLine').style.left = kx.toFixed(3) + '%';
    $('kpLine').style.opacity = kx > 0 && kx < 100 ? 1 : 0;
    document.querySelectorAll('.an-step').forEach(function (el, i) {
      var done = an >= (i + 1) / 3 - 0.001, cur = !done && an >= i / 3;
      el.textContent = (done ? '✓ ' : '') + el.dataset.n;
      el.style.background = done ? '#FCEEE3' : (cur ? '#1B2433' : '#F1EDE6');
      el.style.color = done ? '#A8481A' : (cur ? '#fff' : '#7A808A');
    });

    // 리포트 장면: 카드를 위로 넘겨 본다
    var H = window.innerHeight * 0.7, repH = $('repCard').offsetHeight || 700;
    $('repScroll').style.transform = 'translate(-50%,-' + (Math.max(0, repH - H + 60) * sm(0.86, 0.98)).toFixed(1) + 'px)';

    // 위쪽 문장: 지금 장면의 문장을 단어별로 칠한다
    var idx = Math.min(N - 1, Math.floor(P * N + 0.02));
    steps.forEach(function (st, i) {
      var words = st.querySelectorAll('.sc-word'), a0 = bd(i) + (i ? 0.02 : 0.03), p = cl((P - a0) / 0.13);
      st.style.opacity = i === idx ? 1 : 0;
      words.forEach(function (w, k) {
        var dl = i === idx ? 120 + k * 55 : 0;
        w.style.transition = 'color .3s ease,opacity .7s ease ' + dl + 'ms,transform .9s cubic-bezier(.2,.7,.2,1) ' + dl + 'ms';
        w.style.color = p * words.length > k + 0.3 ? '#1B2433' : '#D6D0C7';
        w.style.opacity = i === idx ? 1 : 0;
        w.style.transform = 'translateY(' + (i === idx ? 0 : (i < idx ? -28 : 36)) + 'px)';
      });
    });
  }

  requestAnimationFrame(frame);
})();
