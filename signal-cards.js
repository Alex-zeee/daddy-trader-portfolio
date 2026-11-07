/* Daddy Trader — signal cards (Home aur Fundamental dono par yahi design)
 * Look: gehra navy card, upar icon + naam + LIVE nishan, bari qeemat, neeche sunehra chart.
 *
 * DTSig.card(signal)   -> signal card (Entry bari qeemat, SL / TP / Now, chart par teeno lines)
 * DTSig.hit(tpHit)     -> "TP Hit" card, date + time ke saath
 * DTSig.gold()         -> Gold ka live card (jab koi signal na ho)
 * DTSig.empty(opts)    -> "abhi koi signal nahi" wala card
 * DTSig.loadPrice()    -> monitor.json se Gold ki qeemat + chart le aata hai, sab cards update
 */
(function () {
  if (window.DTSig) return;

  var CSS = [
    '.dtc{--bg1:#121625;--bg2:#0c0f1a;--line:#1f2434;--txt:#f3f4f7;--mut:#8a90a2;--lab:#737a8e;--acc:#f5b82e;--up:#22c58b;--dn:#ff4d6d;',
    '  position:relative;display:flex;flex-direction:column;overflow:hidden;border-radius:28px;color:var(--txt);text-align:left;',
    '  font-family:Manrope,Inter,system-ui,sans-serif;background:linear-gradient(180deg,var(--bg1),var(--bg2));border:1px solid var(--line);',
    '  box-shadow:0 1px 0 rgba(255,255,255,.04) inset,0 30px 60px -30px rgba(0,0,0,.85);transition:transform .25s ease,border-color .25s ease,box-shadow .25s ease}',
    '.dtc:hover{transform:translateY(-3px);border-color:#2a3046;box-shadow:0 1px 0 rgba(255,255,255,.05) inset,0 36px 70px -30px rgba(0,0,0,.9)}',
    '.dtc-head{display:flex;align-items:center;gap:14px;padding:20px 22px 18px;border-bottom:1px solid var(--line)}',
    '.dtc-ico{flex:none;width:52px;height:52px;border-radius:15px;display:grid;place-items:center;',
    '  background:color-mix(in srgb,var(--ic,#f5b82e) 14%,#141826);border:1px solid color-mix(in srgb,var(--ic,#f5b82e) 45%,transparent)}',
    '.dtc-ico b{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:var(--ic,#f5b82e);color:#14100a;box-shadow:inset 0 -2px 0 rgba(0,0,0,.18)}',
    '.dtc-ico svg{width:17px;height:17px}',
    '.dtc-ttl{min-width:0;flex:1}',
    '.dtc-name{display:block;font-size:19px;font-weight:800;letter-spacing:-.01em;line-height:1.2}',
    '.dtc-sub{display:block;margin-top:3px;font-size:13px;color:var(--mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
    '.dtc-pill{flex:none;display:inline-flex;align-items:center;gap:7px;padding:6px 12px;border-radius:99px;font-size:12.5px;font-weight:800;letter-spacing:.05em;',
    '  color:var(--pc,#34d399);background:color-mix(in srgb,var(--pc,#34d399) 10%,transparent);border:1px solid color-mix(in srgb,var(--pc,#34d399) 40%,transparent)}',
    '.dtc-pill i{width:6px;height:6px;border-radius:50%;background:currentColor;animation:dtcPulse 1.8s ease-out infinite}',
    '.dtc.done .dtc-pill i{animation:none}',
    '@keyframes dtcPulse{0%{box-shadow:0 0 0 0 currentColor}100%{box-shadow:0 0 0 7px transparent}}',
    '.dtc-body{padding:20px 22px 6px}',
    '.dtc-price{display:flex;align-items:center;flex-wrap:wrap;gap:12px}',
    '.dtc-price b{font-size:clamp(32px,3.4vw,40px);font-weight:800;letter-spacing:-.035em;line-height:1;font-variant-numeric:tabular-nums}',
    '.dtc-chip{padding:5px 11px;border-radius:9px;font-size:14px;font-weight:700;color:var(--cc,#ff4d6d);',
    '  background:color-mix(in srgb,var(--cc,#ff4d6d) 12%,transparent);border:1px solid color-mix(in srgb,var(--cc,#ff4d6d) 38%,transparent)}',
    '.dtc-stats{display:flex;flex-wrap:wrap;gap:10px 30px;margin:18px 0 0}',
    '.dtc-stats dt{font-size:11.5px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--lab)}',
    '.dtc-stats dd{margin:4px 0 0;font-size:17px;font-weight:700;font-variant-numeric:tabular-nums;color:#e3e5ec}',
    '.dtc-stats .sl{color:#ff7d93}.dtc-stats .tp{color:#4fe0a6}',
    '.dtc-when{margin:10px 0 0;font-size:12.5px;color:#737a8e}',
    '.dtc-why{margin:14px 0 0;font-size:13px;line-height:1.55;color:var(--mut);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}',
    /* chart: kinare se kinare tak */
    '.dtc-chart{position:relative;height:118px;margin-top:10px}',
    '.dtc-chart svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}',
    '.dtc-lv{position:absolute;right:14px;transform:translateY(-50%);padding:2px 7px;border-radius:6px;font-size:10.5px;font-weight:800;letter-spacing:.04em;background:#0c0f1a;border:1px solid currentColor}',
    '.dtc-lv.sl{color:#ff7d93}.dtc-lv.en{color:#e3e5ec}.dtc-lv.tp{color:#4fe0a6}',
    '.dtc-nochart{height:10px}',
    '.dtc-foot{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:12px;padding:12px 22px 20px}',
    '.dtc-steps{display:flex;flex-wrap:wrap;gap:8px}',
    '.dtc-steps span{padding:7px 13px;border-radius:11px;font-size:13px;font-weight:700;color:var(--mut);background:#161a27;border:1px solid #252a3a}',
    '.dtc-steps span.on{color:var(--acc);border-color:color-mix(in srgb,var(--acc) 70%,transparent);background:color-mix(in srgb,var(--acc) 9%,transparent)}',
    '.dtc-steps span.bad{color:#ff7d93;border-color:rgba(255,77,109,.6);background:rgba(255,77,109,.08)}',
    '.dtc-rr{font-size:14px;color:var(--mut);white-space:nowrap}',
    '.dtc-rr b{margin-left:6px;color:var(--acc);font-weight:800}',
    '.dtc.done .dtc-price b,.dtc.done .dtc-name{color:#b9bdc9}',
    /* TP Hit */
    '.dtc.hit{border-color:rgba(245,184,46,.55);box-shadow:0 0 0 1px rgba(245,184,46,.12) inset,0 30px 70px -32px rgba(245,184,46,.45)}',
    '.dtc.hit .dtc-price b{color:#4fe0a6}',
    '.dtc-gbar{height:6px;margin:18px 22px 0;border-radius:99px;background:linear-gradient(90deg,#ff4d6d 0,#ff4d6d 25%,#22c58b 25%,#f5b82e 100%);opacity:.9}',
    /* khaali halat */
    '.dtc-empty{display:flex;flex-direction:column;justify-content:center;gap:12px;padding:26px 24px;border-radius:28px;color:#f3f4f7;font-family:Manrope,Inter,system-ui,sans-serif;',
    '  background:linear-gradient(180deg,#121625,#0c0f1a);border:1px dashed #2a3046}',
    '.dtc-radar{position:relative;width:58px;height:58px;border-radius:50%;border:1px solid rgba(52,211,153,.35);',
    '  background:radial-gradient(circle,rgba(52,211,153,.35) 0 4px,transparent 5px),repeating-radial-gradient(circle,transparent 0 9px,rgba(52,211,153,.14) 9px 10px)}',
    '.dtc-radar::after{content:"";position:absolute;inset:0;border-radius:50%;background:conic-gradient(from 0deg,rgba(52,211,153,.55),transparent 70deg);animation:dtcRadar 2.6s linear infinite}',
    '@keyframes dtcRadar{to{transform:rotate(360deg)}}',
    '.dtc-empty h3{margin:0;font-size:19px;font-weight:800;letter-spacing:-.01em}',
    '.dtc-empty p{margin:0;max-width:52ch;font-size:14px;line-height:1.6;color:#8a90a2}',
    '@media (max-width:420px){.dtc-head{padding:16px 16px 14px;gap:11px}.dtc-ico{width:44px;height:44px;border-radius:13px}.dtc-ico b{width:28px;height:28px}.dtc-body{padding:16px 16px 4px}.dtc-foot{padding:10px 16px 16px}.dtc-stats{gap:10px 20px}.dtc-pill{padding:5px 9px;font-size:11.5px}}',
    '@media (prefers-reduced-motion:reduce){.dtc,.dtc:hover{transition:none;transform:none}.dtc-pill i,.dtc-radar::after{animation:none}}'
  ].join('\n');

  function injectCss() {
    if (document.getElementById('dtc-css')) return;
    var st = document.createElement('style'); st.id = 'dtc-css'; st.textContent = CSS;
    (document.head || document.documentElement).appendChild(st);
  }

  function esc(v) { return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function num(v) { if (v == null || v === '') return null; var n = +v; return isFinite(n) ? n : null; }
  function fmt(v) { var n = num(v); return n == null ? '—' : n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function pair(p) { p = String(p || 'XAUUSD').toUpperCase().replace(/[^A-Z0-9]/g, ''); return p.length === 6 ? p.slice(0, 3) + '/' + p.slice(3) : p; }
  function rrOf(s) {
    if (num(s.rr)) return Math.round(num(s.rr) * 10) / 10;
    var e = num(s.entry), sl = num(s.sl), tp = num(s.tp);
    if (e == null || sl == null || tp == null || e === sl) return null;
    return Math.round(Math.abs(tp - e) / Math.abs(e - sl) * 10) / 10;
  }
  function kind(st) {
    st = String(st || '').toLowerCase();
    if (st.indexOf('tp') > -1) return 'hit';
    if (st.indexOf('sl') > -1) return 'sl';
    if (/expir|cancel|close/.test(st)) return 'closed';
    if (st.indexOf('pend') > -1) return 'pending';
    return 'active';
  }
  var PILL = { pending: '#f5b82e', active: '#34d399', sl: '#ff4d6d', closed: '#8a90a2', hit: '#f5b82e' };

  var ARROW_UP = '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M6 1.5l4.5 8h-9z" fill="currentColor"/></svg>';
  var ARROW_DN = '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M6 10.5L1.5 2.5h9z" fill="currentColor"/></svg>';
  var CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
  var BAR = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 16h14l-2.2-7H7.2z" fill="currentColor"/><path d="M8.5 9l1-3h5l1 3" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>';

  var price = null, spark = null, gold = null, mood = null, updated = '';

  function steps(k) {
    var on = { pending: 0, active: 1, hit: 2, sl: 2, closed: 2 }[k];
    var last = k === 'sl' ? 'SL hit' : k === 'closed' ? 'Closed' : 'TP hit';
    return '<div class="dtc-steps" aria-hidden="true">' +
      ['Pending', 'Active', last].map(function (t, i) {
        return '<span class="' + (i === on ? (k === 'sl' ? 'bad' : 'on') : '') + '">' + t + '</span>';
      }).join('') + '</div>';
  }
  function chartBox(s) {
    return '<div class="dtc-chart" data-sl="' + esc(s.sl) + '" data-en="' + esc(s.entry) + '" data-tp="' + esc(s.tp) + '" aria-hidden="true"></div>';
  }

  function card(s) {
    s = s || {};
    var k = kind(s.status);
    if (k === 'hit') return hit(s);
    var sell = String(s.type || '').toUpperCase() === 'SELL';
    var done = k === 'sl' || k === 'closed';
    var rr = rrOf(s);
    var dir = sell ? 'SELL' : 'BUY';
    return '<article class="dtc ' + k + (done ? ' done' : '') + '" aria-label="' + esc(pair(s.pair) + ' ' + dir + ' signal, ' + (s.status || '')) + '">' +
      '<div class="dtc-head">' +
        '<span class="dtc-ico" style="--ic:' + (sell ? '#ff4d6d' : '#22c58b') + '"><b>' + (sell ? ARROW_DN : ARROW_UP) + '</b></span>' +
        '<div class="dtc-ttl"><span class="dtc-name">' + esc(pair(s.pair)) + '</span>' +
          '<span class="dtc-sub">' + esc(s.model_name || 'Daddy Trader robot') + '</span></div>' +
        '<span class="dtc-pill" style="--pc:' + PILL[k] + '"><i></i>' + esc(String(s.status || 'Active').toUpperCase()) + '</span>' +
      '</div>' +
      '<div class="dtc-body">' +
        '<div class="dtc-price"><b>' + fmt(s.entry) + '</b><span class="dtc-chip" style="--cc:' + (sell ? '#ff4d6d' : '#22c58b') + '">' + dir + ' entry</span></div>' +
        '<dl class="dtc-stats"><div><dt>Stop loss</dt><dd class="sl">' + fmt(s.sl) + '</dd></div><div><dt>Take profit</dt><dd class="tp">' + fmt(s.tp) + '</dd></div>' +
          (done ? '' : '<div><dt>Gold now</dt><dd class="dtc-nowv">' + (price == null ? '—' : fmt(price)) + '</dd></div>') + '</dl>' +
        (s.note ? '<p class="dtc-why">' + esc(s.note) + '</p>' : '') +
        (s.date ? '<p class="dtc-when">Posted ' + esc(s.date) + '</p>' : '') +
      '</div>' +
      (done ? '<div class="dtc-nochart"></div>' : chartBox(s)) +
      '<div class="dtc-foot">' + steps(k) + (rr ? '<span class="dtc-rr">Risk : reward<b>1:' + rr + '</b></span>' : '') + '</div>' +
    '</article>';
  }

  function hit(h) {
    h = h || {};
    var sell = String(h.type || '').toUpperCase() === 'SELL';
    var e = num(h.entry), tp = num(h.tp);
    var move = e != null && tp != null ? Math.abs(tp - e) : null;
    var rr = rrOf(h);
    var when = h.signal || h.date || '';
    var at = h.hit || h.closed || '';
    return '<article class="dtc hit" aria-label="' + esc(pair(h.pair) + ' ' + (sell ? 'SELL' : 'BUY') + ' — TP hit') + '">' +
      '<div class="dtc-head">' +
        '<span class="dtc-ico" style="--ic:#f5b82e"><b>' + CHECK + '</b></span>' +
        '<div class="dtc-ttl"><span class="dtc-name">' + esc(pair(h.pair)) + ' · ' + (sell ? 'Sell' : 'Buy') + '</span>' +
          '<span class="dtc-sub">' + esc(h.model_name || 'Daddy Trader robot') + '</span></div>' +
        '<span class="dtc-pill" style="--pc:#f5b82e"><i></i>TP HIT</span>' +
      '</div>' +
      '<div class="dtc-body">' +
        '<div class="dtc-price"><b>' + (move != null ? '+' + fmt(move) : 'TP') + '</b>' + (rr ? '<span class="dtc-chip" style="--cc:#f5b82e">1:' + rr + ' target hit</span>' : '') + '</div>' +
        '<dl class="dtc-stats"><div><dt>Entry</dt><dd>' + fmt(h.entry) + '</dd></div><div><dt>Take profit</dt><dd class="tp">' + fmt(h.tp) + '</dd></div><div><dt>Stop loss</dt><dd class="sl">' + fmt(h.sl) + '</dd></div></dl>' +
      '</div>' +
      '<div class="dtc-gbar" aria-hidden="true"></div>' +
      '<div class="dtc-foot"><span class="dtc-rr">Signal<b style="color:#e3e5ec">' + esc(when || '—') + '</b></span><span class="dtc-rr">TP hit<b>' + esc(at || '—') + '</b></span></div>' +
    '</article>';
  }

  // Gold ka live card — jab koi signal na ho tab bhi page khaali na lage
  function goldCard() {
    return '<article class="dtc dtc-gold" aria-label="Gold live price">' +
      '<div class="dtc-head">' +
        '<span class="dtc-ico" style="--ic:#f5b82e"><b>' + BAR + '</b></span>' +
        '<div class="dtc-ttl"><span class="dtc-name">Gold</span><span class="dtc-sub">XAU · USD · spot price</span></div>' +
        '<span class="dtc-pill" style="--pc:#34d399"><i></i>LIVE</span>' +
      '</div>' +
      '<div class="dtc-body">' +
        '<div class="dtc-price"><b class="g-px">—</b><span class="dtc-chip g-chg" style="--cc:#8a90a2">today</span></div>' +
        '<dl class="dtc-stats"><div><dt>Today high</dt><dd class="g-hi">—</dd></div><div><dt>Today low</dt><dd class="g-lo">—</dd></div><div><dt>Market mood</dt><dd class="g-mood">—</dd></div></dl>' +
      '</div>' +
      '<div class="dtc-chart" aria-hidden="true"></div>' +
      '<div class="dtc-foot"><div class="dtc-steps"><span class="on">Recent moves</span></div><span class="dtc-rr g-upd"></span></div>' +
    '</article>';
  }

  function empty(o) {
    o = o || {};
    return '<div class="dtc-empty" role="status">' +
      '<span class="dtc-radar" aria-hidden="true"></span>' +
      '<h3>' + esc(o.title || 'No open signal right now') + '</h3>' +
      '<p>' + esc(o.text || 'The robot keeps watching Gold and posts a signal here only when a real ICT setup forms.') + '</p>' +
      (o.extra || '') + '</div>';
  }

  // ---- chart banana ----
  var uid = 0;
  function drawChart(box) {
    if (!spark || spark.length < 2) { box.innerHTML = ''; return; }
    var lv = { sl: num(box.getAttribute('data-sl')), en: num(box.getAttribute('data-en')), tp: num(box.getAttribute('data-tp')) };
    var vals = spark.slice();
    var all = vals.concat([lv.sl, lv.en, lv.tp].filter(function (v) { return v != null; }));
    var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all), pad = (hi - lo) * 0.12 || 1;
    lo -= pad; hi += pad;
    var W = 400, H = 118;
    function y(v) { return (hi - v) / (hi - lo) * H; }
    var pts = vals.map(function (v, i) { return [i / (vals.length - 1) * W, y(v)]; });
    var line = pts.map(function (p, i) { return (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1); }).join(' ');
    var id = 'dtcg' + (++uid);
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">' +
      '<defs><linearGradient id="' + id + '" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#f5b82e" stop-opacity=".42"/><stop offset="1" stop-color="#f5b82e" stop-opacity="0"/></linearGradient></defs>' +
      '<path d="' + line + ' L' + W + ' ' + H + ' L0 ' + H + ' Z" fill="url(#' + id + ')"/>';
    var labels = '', tags = [];
    [['sl', '#ff7d93', 'SL'], ['en', '#e3e5ec', 'Entry'], ['tp', '#4fe0a6', 'TP']].forEach(function (L) {
      var v = lv[L[0]]; if (v == null) return;
      var yy = y(v);
      svg += '<line x1="0" x2="' + W + '" y1="' + yy.toFixed(1) + '" y2="' + yy.toFixed(1) + '" stroke="' + L[1] + '" stroke-width="1.2" stroke-dasharray="5 5" vector-effect="non-scaling-stroke" opacity=".85"/>';
      tags.push({ k: L[0], t: L[2], y: yy });
    });
    // label ek doosre ke upar na aayen: kam se kam 20px ka faasla
    tags.sort(function (a, b) { return a.y - b.y; });
    for (var i = 1; i < tags.length; i++) if (tags[i].y - tags[i - 1].y < 20) tags[i].y = tags[i - 1].y + 20;
    var over = tags.length ? tags[tags.length - 1].y - (H - 8) : 0;
    if (over > 0) tags.forEach(function (t) { t.y -= over; });
    tags.forEach(function (t) { labels += '<span class="dtc-lv ' + t.k + '" style="top:' + (t.y / H * 100).toFixed(1) + '%">' + t.t + '</span>'; });
    svg += '<path d="' + line + '" fill="none" stroke="#f5b82e" stroke-width="2.4" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>';
    var last = pts[pts.length - 1];
    svg += '</svg>';
    box.innerHTML = svg + labels;
    // aakhri qeemat par chamakta nuqta (HTML mein, taake gol rahe)
    var dot = document.createElement('span');
    dot.style.cssText = 'position:absolute;width:9px;height:9px;border-radius:50%;background:#f5b82e;box-shadow:0 0 0 4px rgba(245,184,46,.22);transform:translate(-50%,-50%);left:calc(100% - 5px);top:' + (last[1] / H * 100).toFixed(1) + '%';
    box.appendChild(dot);
  }
  function refresh() {
    Array.prototype.forEach.call(document.querySelectorAll('.dtc-chart'), drawChart);
    if (price != null) Array.prototype.forEach.call(document.querySelectorAll('.dtc-nowv'), function (el) { el.textContent = fmt(price); });
    if (gold) Array.prototype.forEach.call(document.querySelectorAll('.dtc-gold'), function (c) {
      var up = +gold.chg >= 0;
      c.querySelector('.g-px').textContent = '$' + fmt(gold.price);
      var ch = c.querySelector('.g-chg');
      ch.textContent = (up ? '+' : '') + (+gold.chg).toFixed(2) + '% today';
      ch.style.setProperty('--cc', up ? '#22c58b' : '#ff4d6d');
      if (gold.high != null) c.querySelector('.g-hi').textContent = '$' + fmt(gold.high);
      if (gold.low != null) c.querySelector('.g-lo').textContent = '$' + fmt(gold.low);
      c.querySelector('.g-mood').textContent = mood || '—';
      var m = String(updated || '').match(/(\d{1,2}:\d{2})\s*PKT/);
      c.querySelector('.g-upd').innerHTML = m ? 'Updated<b>' + m[1] + ' PKT</b>' : '';
    });
  }
  function setPrice(p) { p = num(p); if (p != null) { price = p; refresh(); } }

  var pricePromise = null;
  function loadPrice() {
    if (!pricePromise) {
      pricePromise = fetch('monitor.json?t=' + Date.now()).then(function (r) { return r.json(); }).then(function (m) {
        if (m && m.gold) {
          gold = m.gold; price = num(m.gold.price);
          spark = (m.gold.spark || []).map(Number).filter(isFinite);
          mood = m.sentiment && m.sentiment.label; updated = m.updated || '';
        }
        refresh();
        return m;
      }).catch(function () { return null; });
    }
    return pricePromise;
  }

  injectCss();
  window.DTSig = { card: card, hit: hit, gold: goldCard, empty: empty, setPrice: setPrice, loadPrice: loadPrice, refresh: refresh, kind: kind, fmt: fmt };
})();
