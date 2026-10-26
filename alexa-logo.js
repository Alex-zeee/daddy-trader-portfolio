/* Daddy Trader logo — bilkul laptop wali Alexa jaisa (gold line-art, chalti candles, live gold tag) */
(function () {
  var orb = document.getElementById('waOrb'), holder = document.getElementById('waLogo');
  if (!orb || !holder) return;
  var NS = 'http://www.w3.org/2000/svg';
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  fetch('alexa-logo.svg?v=1').then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); }).then(function (txt) {
    holder.innerHTML = txt;
    var svg = holder.querySelector('svg');
    if (!svg) return;
    svg.removeAttribute('xmlns');
    orb.classList.add('has-logo');
    start(svg);
  }).catch(function () {});

  function state() { return orb.getAttribute('data-state') || 'idle'; }

  function start(svg) {
    // pehle logo khud banta hai, phir chalta rehta hai
    if (!reduce) { svg.classList.add('play'); setTimeout(function () { svg.classList.add('idle'); }, 3600); }

    // aakhri candle zinda rehti hai (bolte waqt tez)
    var live = svg.querySelector('#dtoLive'), pl = svg.querySelector('#dtoLiveLine');
    var body = live && live.querySelector('.dt-body'), wick = live && live.querySelector('.dt-wick');
    var OPEN = 79, close = 32, high = 0, target = 32, t0 = 0;
    var bodies = Array.prototype.slice.call(svg.querySelectorAll('.dt-cd .dt-body'));
    bodies.forEach(function (b) { b.style.transformBox = 'fill-box'; b.style.transformOrigin = '50% 100%'; });
    var danced = false;
    function tick(now) {
      var st = state();
      if (!reduce && body && svg.classList.contains('idle')) {
        var fast = st === 'speaking';
        if (now - t0 > (fast ? 260 : 700)) { t0 = now; target = Math.max(14, Math.min(58, 32 + (Math.random() - .5) * (fast ? 56 : 44) + (32 - close) * .4)); }
        close += (target - close) * (fast ? .16 : .08); high = Math.min(high, close - 6); if (Math.random() < .004) high = close - 6;
        body.setAttribute('y', close.toFixed(2)); body.setAttribute('height', (OPEN - close).toFixed(2));
        wick.setAttribute('y1', Math.max(-2, high).toFixed(2));
        if (pl) { pl.setAttribute('y1', close.toFixed(2)); pl.setAttribute('y2', close.toFixed(2)); }
      }
      // candles awaaz ke saath naachti hain, sunte waqt saans leti hain
      if (!reduce && (st === 'speaking' || st === 'listening' || st === 'thinking')) {
        bodies.forEach(function (b, i) {
          var k = st === 'speaking' ? 1 + .45 * (0.3 + 0.7 * Math.abs(Math.sin(now / 95 + i * 1.7)))
                : st === 'listening' ? 1 + .08 * Math.sin(now / 280 + i * .55)
                : 1 + .12 * Math.max(0, Math.sin(now / 160 - i * .45));
          b.style.transform = 'scaleY(' + k.toFixed(3) + ')';
        });
        danced = true;
      } else if (danced) { bodies.forEach(function (b) { b.style.transform = ''; }); danced = false; }
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);

    // live gold rate aakhri candle ke saath
    if (!body) return;
    var tag = document.createElementNS(NS, 'g');
    tag.setAttribute('class', 'dt-tag'); tag.style.opacity = '0'; tag.style.transition = 'opacity .6s';
    tag.innerHTML = '<rect x="0" y="-19" width="150" height="38" rx="9"/><text class="px" x="13" y="7"></text>';
    svg.appendChild(tag);
    var px = tag.querySelector('.px'), rc = tag.querySelector('rect');
    function fill() {
      fetch('https://api.gold-api.com/price/XAU', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (g) {
        if (!g || g.price == null) return;
        px.textContent = 'XAU ' + Number(g.price).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        try { rc.setAttribute('width', (13 + px.getComputedTextLength() + 13).toFixed(1)); } catch (e) {}
        tag.style.opacity = '1';
      }).catch(function () {});
    }
    fill(); setInterval(fill, 30000);
    function follow() { var y = Math.max(10, parseFloat(body.getAttribute('y')) || 32); tag.setAttribute('transform', 'translate(666 ' + y.toFixed(1) + ')'); requestAnimationFrame(follow); }
    requestAnimationFrame(follow);
  }
})();
