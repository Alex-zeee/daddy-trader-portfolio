/* Alexa (website wali) — Daddy Trader
   Laptop wali Alexa off ho to yehi website par baat karti hai.
   Dimagh: Google Gemini. Data: Daddy Trader ka apna data (BackBar candles, monitor.json, signals.json),
   live gold/silver: gold-api.com, crypto: Binance. */
(function () {
  'use strict';

  // ---------------- settings ----------------
  var KEY = ["eZA", "4ZN52", "0dQ-Z", "Qq_lk", "vWaBS", "tQl8D", "0V3aM", "u7zB3", "mRrn1", "8RN6J", "AQ.Ab"].reverse().join('');
  var MODELS = ['gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-flash-latest', 'gemini-3.1-flash-lite'];
  var TTS_MODELS = ['gemini-3.8-flash-lite-tts', 'gemini-3.1-flash-tts-preview', 'gemini-2.5-flash-preview-tts'];
  var TTS_VOICE = 'Kore';
  var TITLE = 'Sir';
  var G = 'https://generativelanguage.googleapis.com/v1beta/models/';
  var HIST_KEY = 'alexa_web_hist_v1', MUTE_KEY = 'alexa_web_mute';
  var startModel = 0;   // jo model pichli dafa chala, wahi pehle

  // ---------------- small helpers ----------------
  function $(id) { return document.getElementById(id); }
  function sget(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function sset(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function round(x, d) { if (x == null || isNaN(x)) return null; var p = Math.pow(10, d); return Math.round(x * p) / p; }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function fetchT(url, opt, ms) {
    var c = ('AbortController' in window) ? new AbortController() : null;
    var t = setTimeout(function () { if (c) c.abort(); }, ms || 15000);
    opt = opt || {}; if (c) opt.signal = c.signal;
    return fetch(url, opt).finally(function () { clearTimeout(t); });
  }
  function getJSON(url, ms) { return fetchT(url, { cache: 'no-store' }, ms).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }); }

  // ---------------- time (Pakistan / New York) ----------------
  var DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'], MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function firstSunday(y, m) { var wd = (new Date(Date.UTC(y, m - 1, 1)).getUTCDay() + 6) % 7; return 1 + (6 - wd) % 7; }
  function nyOffset(ts) {
    var y = new Date(ts * 1000).getUTCFullYear();
    var start = Date.UTC(y, 2, firstSunday(y, 3) + 7, 7) / 1000, end = Date.UTC(y, 10, firstSunday(y, 11), 6) / 1000;
    return (ts >= start && ts < end) ? -4 : -5;
  }
  function nyTime(ts) { return new Date((ts + nyOffset(ts) * 3600) * 1000); }   // read with getUTC*
  function pkTime(ts) { return new Date((ts + 5 * 3600) * 1000); }
  function hm12(d) { var h = d.getUTCHours(), m = d.getUTCMinutes(); var ap = h < 12 ? 'AM' : 'PM'; h = h % 12 || 12; return h + ':' + (m < 10 ? '0' : '') + m + ' ' + ap; }
  function dayStr(d) { return DAYS[d.getUTCDay()] + ' ' + (d.getUTCDate() < 10 ? '0' : '') + d.getUTCDate() + ' ' + MON[d.getUTCMonth()]; }
  function tag(ts) { var d = pkTime(ts); return DAYS[d.getUTCDay()] + ' ' + hm12(d); }
  function pkRange(t0, secs) { return hm12(pkTime(t0)) + ' - ' + hm12(pkTime(t0 + (secs || 3600))); }
  function nyWallToTs(y, m, d, hour) { var wall = Date.UTC(y, m, d, hour) / 1000; return wall - nyOffset(wall + 5 * 3600) * 3600; }
  function left(secs) { var m = Math.max(0, Math.floor(secs / 60)); return m >= 60 ? (Math.floor(m / 60) + 'h ' + (m % 60) + 'm') : (m + ' min'); }
  function nowPK() {
    var d = pkTime(Date.now() / 1000);
    var full = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][d.getUTCDay()];
    var mf = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'][d.getUTCMonth()];
    return full + ', ' + d.getUTCDate() + ' ' + mf + ' ' + d.getUTCFullYear() + ', ' + hm12(d);
  }

  var SB_DEF = [[3, 'London', 'London Silver Bullet'], [10, 'AM', 'AM Silver Bullet'], [14, 'PM', 'PM Silver Bullet']];
  var SB_BY_HOUR = {}; SB_DEF.forEach(function (s) { SB_BY_HOUR[s[0]] = s; });

  function sbUpcoming(now, count) {
    now = now || Date.now() / 1000; count = count || 3;
    var out = [], d0 = nyTime(now);
    for (var dd = 0; dd < 7; dd++) {
      var day = new Date(Date.UTC(d0.getUTCFullYear(), d0.getUTCMonth(), d0.getUTCDate() + dd));
      var wd = (day.getUTCDay() + 6) % 7;
      if (wd >= 5) continue;
      for (var i = 0; i < SB_DEF.length; i++) {
        var h = SB_DEF[i][0], t0 = nyWallToTs(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), h);
        if (t0 + 3600 > now) {
          var running = t0 <= now;
          out.push({ name: SB_DEF[i][2], t0: t0, pk: pkRange(t0), pk_day: dayStr(pkTime(t0)), running: running,
                     left: left(running ? (t0 + 3600 - now) : (t0 - now)) });
          if (out.length >= count) return out;
        }
      }
    }
    return out;
  }

  function marketSessions() {
    var now = new Date(), h = now.getUTCHours() + now.getUTCMinutes() / 60, wd = (now.getUTCDay() + 6) % 7;
    var sess = { Sydney: [21, 6], Tokyo: [0, 9], London: [7, 16], 'New York': [12, 21] }, open = [];
    Object.keys(sess).forEach(function (n) { var a = sess[n][0], b = sess[n][1]; if (a < b ? (h >= a && h < b) : (h >= a || h < b)) open.push(n); });
    var weekend = wd === 5 || (wd === 6 && h < 21) || (wd === 4 && h >= 21);
    return { ok: true, open_sessions: weekend ? [] : open, forex_weekend_closed: weekend, pakistan_time: nowPK() };
  }

  // ---------------- symbols ----------------
  var ALIAS = {
    gold: 'XAUUSD', xau: 'XAUUSD', xauusd: 'XAUUSD', sona: 'XAUUSD', 'سونا': 'XAUUSD', 'گولڈ': 'XAUUSD',
    silver: 'XAGUSD', xag: 'XAGUSD', xagusd: 'XAGUSD', chandi: 'XAGUSD',
    nasdaq: 'NAS100', nas100: 'NAS100', us100: 'NAS100', nq: 'NAS100',
    sp500: 'SPX500', spx: 'SPX500', spx500: 'SPX500', us500: 'SPX500', 'S&P500': 'SPX500',
    dow: 'US30', dowjones: 'US30', us30: 'US30',
    dax: 'GER40', ger40: 'GER40', de40: 'GER40', ftse: 'UK100', uk100: 'UK100', nikkei: 'JP225', jp225: 'JP225',
    oil: 'WTI', wti: 'WTI', usoil: 'WTI', crude: 'WTI', brent: 'BRENT', ukoil: 'BRENT',
    bitcoin: 'BTCUSDT', btc: 'BTCUSDT', btcusd: 'BTCUSDT', btcusdt: 'BTCUSDT',
    ethereum: 'ETHUSDT', eth: 'ETHUSDT', ethusd: 'ETHUSDT', ethusdt: 'ETHUSDT',
    solana: 'SOLUSDT', sol: 'SOLUSDT', bnb: 'BNBUSDT', xrp: 'XRPUSDT', ripple: 'XRPUSDT'
  };
  var CRYPTO = { BTCUSDT: 'Bitcoin (BTCUSDT)', ETHUSDT: 'Ethereum (ETHUSDT)', SOLUSDT: 'Solana (SOLUSDT)', BNBUSDT: 'BNB (BNBUSDT)', XRPUSDT: 'XRP (XRPUSDT)' };
  var _index = null, _indexAt = 0;
  function siteIndex() {
    if (_index && Date.now() - _indexAt < 5 * 60e3) return Promise.resolve(_index);
    return getJSON('data/index.json?t=' + Date.now()).then(function (d) { _index = d; _indexAt = Date.now(); return d; });
  }
  function resolve(sym) {
    var s = String(sym || 'gold').toLowerCase().replace(/[\s\/\-_.]/g, '');
    var code = ALIAS[s] || s.toUpperCase();
    if (CRYPTO[code]) return Promise.resolve({ code: code, label: CRYPTO[code], crypto: true, dec: code === 'BTCUSDT' ? 1 : (code === 'XRPUSDT' ? 4 : 2) });
    return siteIndex().then(function (idx) {
      var info = idx.symbols[code];
      if (!info) throw new Error('symbol "' + sym + '" Daddy Trader data mein nahi. Ye hain: gold, silver, ' + idx.order.join(', ') + ', bitcoin, ethereum');
      return { code: code, label: info.name + ' (' + code + ')', crypto: false, dec: info.dec, info: info };
    });
  }

  // ---------------- candles ----------------
  var _csvCache = {};
  function siteCsv(code, month) {
    var k = code + '/' + month, hit = _csvCache[k];
    if (hit && Date.now() - hit.at < 5 * 60e3) return Promise.resolve(hit.rows);
    return fetchT('data/fx/' + code + '/m5/' + month + '.csv?t=' + Math.floor(Date.now() / 300000), { cache: 'no-store' }, 20000)
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); })
      .then(function (txt) {
        var rows = [];
        txt.split('\n').forEach(function (ln) { var p = ln.split(','); if (p.length >= 5 && p[0]) rows.push([+p[0], +p[1], +p[2], +p[3], +p[4]]); });
        _csvCache[k] = { at: Date.now(), rows: rows };
        return rows;
      });
  }
  function aggregate(rows, tf) {
    if (tf === 5) return rows;
    var sec = tf * 60, out = [], cur = null;
    rows.forEach(function (r) {
      var b = Math.floor(r[0] / sec) * sec;
      if (!cur || cur[0] !== b) { cur = [b, r[1], r[2], r[3], r[4]]; out.push(cur); }
      else { if (r[2] > cur[2]) cur[2] = r[2]; if (r[3] < cur[3]) cur[3] = r[3]; cur[4] = r[4]; }
    });
    return out;
  }
  var BARS = { 5: 700, 15: 500, 60: 500, 240: 300 };
  function candles(sym, tf) {
    return resolve(sym).then(function (s) {
      if (s.crypto) {
        var iv = { 5: '5m', 15: '15m', 60: '1h', 240: '4h' }[tf];
        return getJSON('https://api.binance.com/api/v3/klines?symbol=' + s.code + '&interval=' + iv + '&limit=' + BARS[tf]).then(function (k) {
          var rows = k.map(function (x) { return [Math.floor(x[0] / 1000), +x[1], +x[2], +x[3], +x[4]]; });
          return { s: s, rows: rows, source: 'Binance (live)' };
        });
      }
      var months = (s.info.m5 || []).slice(-(tf >= 60 ? 3 : 2));
      return Promise.all(months.map(function (m) { return siteCsv(s.code, m); })).then(function (parts) {
        var m5 = [].concat.apply([], parts);
        var rows = aggregate(m5, tf).slice(-BARS[tf]);
        if (rows.length < 30) throw new Error('candles kam hain');
        return { s: s, rows: rows, source: 'Daddy Trader BackBar data (Dukascopy), aakhri candle ' + tag(rows[rows.length - 1][0]) + ' PKT' };
      });
    });
  }

  // ---------------- live price ----------------
  function livePrice(sym) {
    return resolve(sym).then(function (s) {
      if (s.crypto) {
        return getJSON('https://api.binance.com/api/v3/ticker/24hr?symbol=' + s.code).then(function (t) {
          return { ok: true, symbol: s.label, price: round(+t.lastPrice, s.dec), change_24h_pct: round(+t.priceChangePercent, 2), high_24h: round(+t.highPrice, s.dec), low_24h: round(+t.lowPrice, s.dec), source: 'Binance live' };
        });
      }
      if (s.code === 'XAUUSD' || s.code === 'XAGUSD') {
        return getJSON('https://api.gold-api.com/price/' + (s.code === 'XAUUSD' ? 'XAU' : 'XAG'), 8000).then(function (g) {
          var out = { ok: true, symbol: s.label, price: round(g.price, 2), source: 'gold-api.com live spot', updated_pk: g.updatedAt ? tag(Date.parse(g.updatedAt) / 1000) + ' PKT' : null };
          if (s.info && s.info.price) { out.daily_change_pct_site = s.info.chg; }
          return out;
        }).catch(function () {
          return { ok: true, symbol: s.label, price: s.info.price, change_pct: s.info.chg, source: 'Daddy Trader data', as_of: tag(s.info.last) + ' PKT (live nahi mila)' };
        });
      }
      return { ok: true, symbol: s.label, price: s.info.price, change_pct: s.info.chg, source: 'Daddy Trader BackBar data', as_of: tag(s.info.last) + ' PKT', note: 'ye live rate nahi, is waqt ka aakhri rate hai' };
    });
  }

  // ---------------- analysis (laptop Alexa jaisi) ----------------
  function swings(H, L, k) {
    var hs = [], ls = [];
    for (var i = k; i < H.length - k; i++) {
      var wh = H.slice(i - k, i + k + 1), wl = L.slice(i - k, i + k + 1), bh = H.slice(i - k, i), bl = L.slice(i - k, i);
      if (H[i] === Math.max.apply(null, wh) && H[i] > Math.max.apply(null, bh)) hs.push(i);
      if (L[i] === Math.min.apply(null, wl) && L[i] < Math.min.apply(null, bl)) ls.push(i);
    }
    return [hs, ls];
  }
  function tfNum(t) {
    t = String(t).toLowerCase().replace(/\s/g, '');
    var m = { '5': 5, '5m': 5, m5: 5, '15': 15, '15m': 15, m15: 15, '60': 60, '1h': 60, h1: 60, '240': 240, '4h': 240, h4: 240 };
    return m[t] || 15;
  }
  function uniqSorted(a, desc) { a = a.filter(function (v, i) { return a.indexOf(v) === i; }); a.sort(function (x, y) { return desc ? y - x : x - y; }); return a; }

  function marketAnalysis(args) {
    var sym = (args && args.symbol) || 'gold';
    var tfs = ((args && args.timeframes) || ['60', '15']).map(tfNum).slice(0, 3);
    var out = { ok: true, timeframes: [] };
    return tfs.reduce(function (p, tf) {
      return p.then(function () {
        return candles(sym, tf).then(function (d) {
          var rows = d.rows, dec = d.s.dec, f = function (x) { return round(x, dec); };
          var T = rows.map(function (r) { return r[0]; }), H = rows.map(function (r) { return r[2]; }), L = rows.map(function (r) { return r[3]; }), C = rows.map(function (r) { return r[4]; });
          var n = rows.length, price = C[n - 1];
          if (!out.symbol) { out.symbol = d.s.label; out.last_candle_close = f(price); out.source = d.source; }
          var sw = swings(H, L, tf >= 60 ? 2 : 3), hs = sw[0].slice(-6), ls = sw[1].slice(-6);
          var trend = 'range';
          if (hs.length >= 2 && ls.length >= 2) {
            var hh = H[hs[hs.length - 1]] > H[hs[hs.length - 2]], hl = L[ls[ls.length - 1]] > L[ls[ls.length - 2]];
            trend = (hh && hl) ? 'bullish (higher high, higher low)' : (!hh && !hl) ? 'bearish (lower high, lower low)' : 'range / mixed';
          }
          var bos = null;
          if (hs.length && price > H[hs[hs.length - 1]]) bos = 'bullish BOS: price ne swing high ' + f(H[hs[hs.length - 1]]) + ' upar toda';
          else if (ls.length && price < L[ls[ls.length - 1]]) bos = 'bearish BOS: price ne swing low ' + f(L[ls[ls.length - 1]]) + ' neeche toda';
          var fb = [], fs = [];
          for (var i = Math.max(2, n - 160); i < n; i++) {
            var restL = L.slice(i + 1), restH = H.slice(i + 1);
            if (L[i] > H[i - 2] && (restL.length ? Math.min.apply(null, restL) : L[i]) > H[i - 2]) fb.push([f(H[i - 2]), f(L[i]), tag(T[i])]);
            if (H[i] < L[i - 2] && (restH.length ? Math.max.apply(null, restH) : H[i]) < L[i - 2]) fs.push([f(H[i]), f(L[i - 2]), tag(T[i])]);
          }
          var tol = price * 0.0006, eqh = [], eql = [];
          for (var a = 0; a + 1 < hs.length; a++) if (Math.abs(H[hs[a]] - H[hs[a + 1]]) <= tol) eqh.push(f(H[hs[a]]));
          for (var b = 0; b + 1 < ls.length; b++) if (Math.abs(L[ls[b]] - L[ls[b + 1]]) <= tol) eql.push(f(L[ls[b]]));
          var above = hs.filter(function (i) { return H[i] > price; }).map(function (i) { return f(H[i]); });
          var below = ls.filter(function (i) { return L[i] < price; }).map(function (i) { return f(L[i]); });
          var lo = ls.length ? Math.min.apply(null, ls.slice(-3).map(function (i) { return L[i]; })) : Math.min.apply(null, L);
          var hi = hs.length ? Math.max.apply(null, hs.slice(-3).map(function (i) { return H[i]; })) : Math.max.apply(null, H);
          var eq = (hi + lo) / 2;
          out.timeframes.push({
            tf: { 60: '1 hour', 240: '4 hour' }[tf] || (tf + ' minute'), trend: trend, break_of_structure: bos || 'abhi koi naya break nahi',
            swing_highs: hs.slice(-4).map(function (i) { return [f(H[i]), tag(T[i])]; }), swing_lows: ls.slice(-4).map(function (i) { return [f(L[i]), tag(T[i])]; }),
            buy_side_liquidity_above: uniqSorted(above).slice(0, 4), sell_side_liquidity_below: uniqSorted(below, true).slice(0, 4),
            equal_highs: eqh.slice(-3), equal_lows: eql.slice(-3), unfilled_bullish_fvg: fb.slice(-3), unfilled_bearish_fvg: fs.slice(-3),
            dealing_range: [f(lo), f(hi)], equilibrium_50pct: f(eq),
            price_zone: price > eq ? 'premium (50% se upar, sell zone)' : 'discount (50% se neeche, buy zone)'
          });
        });
      });
    }, Promise.resolve()).then(function () {
      return candles(sym, 60).then(function (d) {
        var days = {}, keys = [];
        d.rows.forEach(function (r) { var nt = nyTime(r[0] + 7 * 3600); var k = nt.getUTCFullYear() + '-' + nt.getUTCMonth() + '-' + nt.getUTCDate(); if (!days[k]) { days[k] = []; keys.push(k); } days[k].push(r); });
        if (keys.length >= 2) {
          var prev = days[keys[keys.length - 2]];
          out.previous_day_high = round(Math.max.apply(null, prev.map(function (r) { return r[2]; })), d.s.dec);
          out.previous_day_low = round(Math.min.apply(null, prev.map(function (r) { return r[3]; })), d.s.dec);
        }
      }).catch(function () {});
    }).then(function () {
      return livePrice(sym).then(function (lp) { out.live_price = lp.price; out.live_price_source = lp.source + (lp.as_of ? ', ' + lp.as_of : ''); }).catch(function () {});
    }).then(function () { return out; });
  }

  function ictAnalyze(rows, tf) {
    var tfSec = tf * 60, n = rows.length, sweepLook = 10, maxAge = 60, liqBars = Math.max(1, Math.floor(2 * 3600 / tfSec)), fvgExt = 30;
    var T = [], O = [], H = [], L = [], C = [];
    rows.forEach(function (r) { T.push(r[0]); O.push(r[1]); H.push(r[2]); L.push(r[3]); C.push(r[4]); });
    var wk = new Array(n), winOf = new Array(n).fill(-1), windows = [];
    for (var i = 0; i < n; i++) {
      var d = nyTime(T[i]), wd = (d.getUTCDay() + 6) % 7, h = d.getUTCHours();
      wk[i] = (wd < 5 && SB_BY_HOUR[h]) ? (d.getUTCFullYear() + '-' + d.getUTCMonth() + '-' + d.getUTCDate() + '|' + h) : null;
    }
    i = 0;
    while (i < n) {
      if (wk[i] === null) { i++; continue; }
      var j = i; while (j + 1 < n && wk[j + 1] === wk[i]) j++;
      var dd = nyTime(T[i]), hr = dd.getUTCHours(), def = SB_BY_HOUR[hr];
      var t0 = nyWallToTs(dd.getUTCFullYear(), dd.getUTCMonth(), dd.getUTCDate(), hr), a = Math.max(0, i - liqBars);
      var w = { name: def[2], t0: t0, hi: Math.max.apply(null, H.slice(i, j + 1)), lo: Math.min.apply(null, L.slice(i, j + 1)), pk: pkRange(t0), pk_day: dayStr(pkTime(t0)),
                done: T[j] + tfSec >= t0 + 3600, bsl: i > a ? Math.max.apply(null, H.slice(a, i)) : null, ssl: i > a ? Math.min.apply(null, L.slice(a, i)) : null, bsl_sweep: null, ssl_sweep: null };
      for (var k = i; k <= j; k++) {
        winOf[k] = windows.length;
        if (w.bsl !== null && !w.bsl_sweep && H[k] > w.bsl) w.bsl_sweep = { p: H[k], t: T[k] };
        if (w.ssl !== null && !w.ssl_sweep && L[k] < w.ssl) w.ssl_sweep = { p: L[k], t: T[k] };
      }
      windows.push(w); i = j + 1;
    }
    var fvgs = [];
    for (k = 2; k < n; k++) {
      if (winOf[k] < 0) continue;
      if (L[k] > H[k - 2]) fvgs.push({ type: 'bull', w: winOf[k] });
      else if (H[k] < L[k - 2]) fvgs.push({ type: 'bear', w: winOf[k] });
    }
    var cisd = [], dnOpen = null, dnBar = null, dnLow = null, upOpen = null, upBar = null, upHigh = null, pBull = null, pBullBar = null, pBear = null, pBearBar = null;
    for (i = 0; i < n; i++) {
      var isDn = C[i] < O[i], isUp = C[i] > O[i], prevDn = i > 0 && C[i - 1] < O[i - 1], prevUp = i > 0 && C[i - 1] > O[i - 1];
      if (isDn && !prevDn) { dnOpen = O[i]; dnBar = i; dnLow = L[i]; } else if (isDn) dnLow = Math.min(dnLow, L[i]);
      if (isUp && !prevUp) { upOpen = O[i]; upBar = i; upHigh = H[i]; } else if (isUp) upHigh = Math.max(upHigh, H[i]);
      if (prevDn && !isDn && dnBar !== null) { var a1 = Math.max(0, dnBar - sweepLook); var pr = dnBar > a1 ? Math.min.apply(null, L.slice(a1, dnBar)) : null; if (pr !== null && dnLow < pr) { pBull = dnOpen; pBullBar = dnBar; } }
      if (prevUp && !isUp && upBar !== null) { var a2 = Math.max(0, upBar - sweepLook); var pr2 = upBar > a2 ? Math.max.apply(null, H.slice(a2, upBar)) : null; if (pr2 !== null && upHigh > pr2) { pBear = upOpen; pBearBar = upBar; } }
      if (pBull !== null && i - pBullBar > maxAge) pBull = null;
      if (pBear !== null && i - pBearBar > maxAge) pBear = null;
      if (winOf[i] >= 0 && pBull !== null && C[i] > pBull) { cisd.push({ type: 'bullish', level: pBull, t: T[i], w: winOf[i] }); pBull = null; }
      if (winOf[i] >= 0 && pBear !== null && C[i] < pBear) { cisd.push({ type: 'bearish', level: pBear, t: T[i], w: winOf[i] }); pBear = null; }
    }
    return { windows: windows, fvgs: fvgs, cisd: cisd };
  }

  function ictStatus(args) {
    var now = Date.now() / 1000;
    var out = { ok: true, pakistan_time_now: nowPK(), silver_bullet_windows_new_york: 'London 03:00-04:00, AM 10:00-11:00, PM 14:00-15:00 (New York time)',
      next_windows: sbUpcoming(now, 3).map(function (w) { return { name: w.name, pakistan_time: w.pk_day + ' ' + w.pk, status: w.running ? ('abhi chal raha hai, ' + w.left + ' baqi') : (w.left + ' baad shuru') }; }) };
    return candles((args && args.symbol) || 'gold', 5).then(function (d) {
      var r = ictAnalyze(d.rows, 5), dec = d.s.dec, f = function (x) { return x == null ? null : round(x, dec); };
      out.symbol = d.s.label; out.data_source = d.source; out.last_candle_close = f(d.rows[d.rows.length - 1][4]);
      out.recent_windows = r.windows.slice(-3).map(function (w) {
        var wi = r.windows.indexOf(w);
        return { name: w.name, pakistan_time: w.pk_day + ' ' + w.pk, finished: w.done, range_high: f(w.hi), range_low: f(w.lo), bsl_before_window: f(w.bsl), ssl_before_window: f(w.ssl),
          bsl_swept: w.bsl_sweep ? ('haan, ' + f(w.bsl_sweep.p) + ' tak (' + hm12(pkTime(w.bsl_sweep.t)) + ' PKT)') : 'nahi',
          ssl_swept: w.ssl_sweep ? ('haan, ' + f(w.ssl_sweep.p) + ' tak (' + hm12(pkTime(w.ssl_sweep.t)) + ' PKT)') : 'nahi',
          fvg_count: r.fvgs.filter(function (x) { return x.w === wi; }).length,
          cisd: r.cisd.filter(function (c) { return c.w === wi; }).map(function (c) { return { type: c.type, level: f(c.level), confirmed_pakistan_time: hm12(pkTime(c.t + 300)) }; }) };
      });
      return out;
    }).catch(function (e) { out.chart_data_error = String(e.message || e).slice(0, 160); return out; });
  }

  // ---------------- Daddy Trader site data ----------------
  function monitor() { return getJSON('monitor.json?ts=' + Date.now()); }
  function marketNews() {
    return monitor().then(function (m) {
      return { ok: true, updated: m.updated, sentiment: m.sentiment, news: (m.news || []).slice(0, 8).map(function (n) { return { time: n.t, title: n.title, urdu: n.ur, source: n.src }; }),
               other_markets: (m.markets || []).map(function (x) { return { name: x.name, price: x.price, change_pct: x.chg }; }) };
    });
  }
  function econCalendar() {
    return monitor().then(function (m) { return { ok: true, updated: m.updated, mode: m.cal_mode, events_pakistan_time: (m.calendar || []).slice(0, 15) }; });
  }
  function signals() { return getJSON('signals.json?t=' + Date.now()).then(function (s) { s.ok = true; return s; }); }
  function currencyRate(args) {
    var from = String((args && args.from) || 'USD').toUpperCase(), to = String((args && args.to) || 'PKR').toUpperCase();
    return getJSON('https://open.er-api.com/v6/latest/' + from).then(function (d) {
      if (!d.rates || !d.rates[to]) throw new Error('rate nahi mila');
      return { ok: true, pair: from + '/' + to, rate: d.rates[to], updated: d.time_last_update_utc, note: 'din mein aik dafa update hota hai (open market/interbank se thora farq ho sakta hai)' };
    });
  }

  var pendingNav = null;
  function openSection(args) {
    var s = String((args && args.section) || '').toLowerCase();
    var url = /back/.test(s) ? 'backtest.html' : /fund|news|daddy|signal|home/.test(s) ? 'fundamental.html' : null;
    if (!url) return Promise.resolve({ ok: false, error: 'section: fundamental ya backtest' });
    pendingNav = url;
    return Promise.resolve({ ok: true, opening: url });
  }

  var TOOLS = {
    get_market_price: { fn: function (a) { return livePrice(a && a.symbol); }, d: 'Kisi market ka abhi ka rate. Gold/silver live spot, crypto live (Binance), forex/indices/oil Daddy Trader data ka aakhri rate.', p: { symbol: { type: 'string', description: 'gold, silver, EURUSD, GBPUSD, USDJPY, NAS100, US30, SPX500, GER40, WTI, BRENT, bitcoin, ethereum, waghera' } }, r: ['symbol'] },
    market_analysis: { fn: marketAnalysis, d: 'Asli candles se structure: trend, swings, BOS, liquidity (BSL/SSL, equal highs/lows), unfilled FVG, dealing range, premium/discount, PDH/PDL, live price. Trade idea / levels / analysis se PEHLE ye chalao.', p: { symbol: { type: 'string', description: 'gold, EURUSD, NAS100, bitcoin...' }, timeframes: { type: 'array', items: { type: 'string' }, description: 'jaise ["240","60","15"] ya ["4h","1h","15m"]; default ["60","15"]' } }, r: ['symbol'] },
    ict_status: { fn: ictStatus, d: 'Silver Bullet windows (agla kab, Pakistan time), haal ke windows mein BSL/SSL sweep, FVG aur CISD.', p: { symbol: { type: 'string' } } },
    market_news: { fn: marketNews, d: 'Daddy Trader monitor se Gold ki taaza khabrein (Urdu khulasa ke saath), sentiment, aur doosri markets (silver, DXY, oil...). "Kyun upar/neeche gaya", khabrein, sentiment ke liye.', p: {} },
    economic_calendar: { fn: econCalendar, d: 'Is hafte ke economic events (NFP, CPI, Fed/FOMC...) Pakistan time ke saath, forecast/previous.', p: {} },
    daddy_trader_signals: { fn: signals, d: 'Daddy Trader website ka apna auto signal bot: Gold bias, RSI, liquidity upar/neeche, trade idea aur active signals.', p: {} },
    market_sessions: { fn: function () { return Promise.resolve(marketSessions()); }, d: 'Kaun se forex sessions khule hain, weekend band hai ya nahi, Pakistan ka waqt.', p: {} },
    currency_rate: { fn: currencyRate, d: 'Currency conversion rate jaise dollar to rupee (USD PKR), riyal, dirham.', p: { from: { type: 'string', description: 'USD, EUR, SAR, AED...' }, to: { type: 'string', description: 'PKR...' } } },
    open_section: { fn: openSection, d: 'Website ka hissa kholna: "fundamental" (Daddy Trader news/signals page) ya "backtest" (BackBar chart replay).', p: { section: { type: 'string', enum: ['fundamental', 'backtest'] } }, r: ['section'] }
  };
  function decls() {
    return Object.keys(TOOLS).map(function (n) {
      var t = TOOLS[n], o = { name: n, description: t.d };
      if (Object.keys(t.p).length) o.parameters = { type: 'object', properties: t.p, required: t.r || [] };
      return o;
    });
  }

  // ---------------- persona ----------------
  function systemPrompt() {
    var t = TITLE;
    return 'Tum "Alexa" ho — ' + t + ' (M. Ali Alvi, Daddy Trader) ki personal AI assistant, Iron Man ke JARVIS jaisi. Tum aurat ho: "karti hoon", "bata rahi hoon". User ko "' + t + '" kaho.\n' +
      'Tum is waqt Daddy Trader WEBSITE par ho (laptop wali Alexa abhi on nahi). Tum international markets aur trading (gold/XAUUSD, forex, oil, indices, crypto, ICT), aam sawal, likhna (message, post), hisaab-kitaab, tarjuma aur mashwara karti ho.\n' +
      'Abhi Pakistan ka waqt: ' + nowPK() + '.\n\n' +
      'Qaide:\n' +
      '- SIRF wohi jawab do jo poocha gaya. Har jawab mein gold ka rate mat jodo; get_market_price sirf tab chalao jab rate/price poocha jaye ya analysis maange. Andaze se price KABHI mat batao.\n' +
      '- "Kyun upar/neeche gaya", khabrein, sentiment ke liye market_news chalao. Events/calendar (NFP, CPI, Fed) ke liye economic_calendar. Daddy Trader ke signal/bias ke liye daddy_trader_signals.\n' +
      '- Trade ka mashwara, prediction, analysis ya levels maange: PEHLE market_analysis chalao (zaroorat ho to ict_status, market_news, daddy_trader_signals bhi), phir asli numbers ke saath qadam ba qadam batao: bara timeframe ka trend, structure (BOS), liquidity kahan hai (BSL/SSL, equal highs/lows), unfilled FVG, premium/discount, aur aakhir mein tumhari raye: bias, entry zone, stop loss, target — har level ke saath wajah. "Faisla aap ka" ya "risk sambhal kar" jaisi line BILKUL mat kaho; ' + t + ' ko ye pasand nahi.\n' +
      '- Analysis mein live_price ko abhi ka rate maano. Agar candles ka aakhri waqt (source) kaafi purana ho to ek chhoti line mein bata do ke chart data kis waqt tak ka hai.\n' +
      '- Silver Bullet / CISD / sweep ke sawal par ict_status chalao aur Pakistan ka waqt batao.\n' +
      '- Khabron ki wajah sirf tool ke nateeje se batao; kuch na mile to saaf kaho "abhi taaza khabar nahi mil saki" — apni taraf se wajah mat ghado.\n' +
      '- Weekend par forex/gold band hota hai; tab batao ke ye Friday ka aakhri rate hai.\n' +
      '- Website ke hisse kholne ko kahe ("fundamental kholo", "backtest kholo") to open_section chalao.\n' +
      '- Laptop ke kaam (app/website kholna, YouTube, WhatsApp, screen ya chart dekhna, TradingView par marking, awaz, screenshot) website se nahi ho sakte: ek line mein batao ke ye laptop wali Alexa karti hai — laptop par Alexa (start.bat) on karein to wohi yahan website par aa jayegi. Phir jo madad yahan ho sakti hai woh foran do.\n' +
      '- Internet search yahan nahi hai. Aam sawalon ka jawab apne ilm se do; agar taaza khabar chahiye (markets ke ilawa) aur tumhe pakka maloom nahi, to saaf kaho ke taaza maloomat yahan nahi mil sakti.\n' +
      '- JHOOT KABHI NAHI. Tool error de to saaf batao kya nahi hua.\n' +
      '- Agar baat adhoori ya be-maani lagay to sirf "Ji ' + t + '?" kaho.\n\n' +
      'SHOW wali line Roman Urdu mein likho, jaisa Pakistan mein WhatsApp par likhte hain (jaise "Ji sir, gold abhi 2415 par hai").\n' +
      'Aam taur par jawab 2-4 jumlon mein do. Agar user "detail mein / tafseel se / step by step" kahe ya sawal hi tafseeli ho (jaise analysis), to 8-16 jumlon mein poori tafseel do. Markdown, bullets ya emoji bilkul nahi (ye bol kar sunaya jata hai).\n\n' +
      'Aakhri jawab HAMESHA bilkul is format mein do:\nSHOW: <screen par dikhane wala jawab>\n' +
      'SPEAK: SHOW wala bilkul wohi jawab, lekin sahi Urdu (Nastaliq) script mein — kyunke ise Urdu awaz parhegi. Angrezi alfaz Urdu mein likho jaise bole jaate hain (گولڈ، ڈالر، یورو، بٹ کوائن)۔ Numbers digits mein rehne do (2415.30) aur SPEAK mein % ki jagah فیصد likho. SHOW line mein % hi likho.';
  }

  // ---------------- Gemini ----------------
  function genConfig(model, think) {
    var g = { maxOutputTokens: 1600, temperature: 0.6 };
    if (think && /^gemini-3/.test(model) && model.indexOf('3.5-flash-lite') < 0) g.thinkingConfig = { thinkingLevel: 'minimal' };
    if (think && /latest/.test(model)) g.thinkingConfig = { thinkingBudget: 0 };
    return g;
  }
  function gemini(model, body, ms) {
    return fetchT(G + model + ':generateContent', { method: 'POST', headers: { 'x-goog-api-key': KEY, 'Content-Type': 'application/json' }, body: JSON.stringify(body) }, ms || 30000)
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { status: r.status, j: j }; }); });
  }

  function brain(history, onStep) {
    var contents = history.map(function (m) { return { role: m.role, parts: [{ text: m.text }] }; });
    var mi = startModel, think = true, busy = 0;
    function round_(depth) {
      if (depth > 6) return Promise.resolve('SHOW: Maaf kijiye ' + TITLE + ', jawab banane mein der ho gayi. Dobara poochiye.\nSPEAK: معاف کیجیے سر، دوبارہ پوچھیے۔');
      var model = MODELS[mi];
      return gemini(model, { system_instruction: { parts: [{ text: systemPrompt() }] }, contents: contents, tools: [{ function_declarations: decls() }], generationConfig: genConfig(model, think) })
        .catch(function (e) { return { status: 0, j: { error: { message: String(e && e.name === 'AbortError' ? 'timeout' : e) } } }; })
        .then(function (res) {
          var st = res.status, j = res.j || {};
          if (st !== 200) {
            var msg = (j.error && j.error.message) || ('HTTP ' + st);
            if (st === 400 && /thinking/i.test(msg) && think) { think = false; return round_(depth); }
            if ((st === 503 || st === 500) && mi + 1 >= MODELS.length && busy < 2) { busy++; return sleep(1200 * busy).then(function () { return round_(depth); }); }
            if ((st === 429 || st === 404 || st >= 500 || st === 0) && mi + 1 < MODELS.length) { mi++; busy = 0; think = true; return round_(depth); }
            if (st === 429) throw new Error('limit');
            if (st === 400 || st === 403) throw new Error('key: ' + msg);
            throw new Error(msg);
          }
          var cand = (j.candidates || [])[0];
          if (!cand) throw new Error('khaali jawab');
          startModel = mi;
          var content = cand.content || { role: 'model', parts: [] }, parts = content.parts || [];
          var calls = parts.filter(function (p) { return p.functionCall; }).map(function (p) { return p.functionCall; });
          var text = parts.filter(function (p) { return p.text && !p.thought; }).map(function (p) { return p.text; }).join('');
          if (!calls.length) return text;
          contents.push(content);
          return Promise.all(calls.map(function (c) {
            var t = TOOLS[c.name];
            if (onStep) onStep(c.name);
            var p = t ? Promise.resolve().then(function () { return t.fn(c.args || {}); }) : Promise.resolve({ ok: false, error: 'aisa tool nahi' });
            return p.catch(function (e) { return { ok: false, error: String((e && e.message) || e).slice(0, 200) }; })
              .then(function (r) { var fr = { name: c.name, response: { result: r } }; if (c.id) fr.id = c.id; return { functionResponse: fr }; });
          })).then(function (resp) { contents.push({ role: 'user', parts: resp }); return round_(depth + 1); });
        });
    }
    return round_(0);
  }

  function parseReply(txt) {
    txt = String(txt || '').trim();
    var sm = txt.match(/SHOW:\s*([\s\S]*?)(?:\n\s*SPEAK:|$)/i), sp = txt.match(/SPEAK:\s*([\s\S]*)$/i);
    var show = (sm ? sm[1] : txt.replace(/SPEAK:[\s\S]*$/i, '')).trim().replace(/[*#\x60]/g, '');
    var speak = sp ? sp[1].trim() : '';
    return { show: show || ('Ji ' + TITLE + '?'), speak: speak };
  }

  // ---------------- voice out ----------------
  var audio = null, speaking = false;
  function pcmToWav(b64, rate) {
    var bin = atob(b64), len = bin.length, buf = new ArrayBuffer(44 + len), v = new DataView(buf);
    function ws(o, s) { for (var i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); }
    ws(0, 'RIFF'); v.setUint32(4, 36 + len, true); ws(8, 'WAVE'); ws(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); ws(36, 'data'); v.setUint32(40, len, true);
    for (var i = 0; i < len; i++) v.setUint8(44 + i, bin.charCodeAt(i));
    return URL.createObjectURL(new Blob([buf], { type: 'audio/wav' }));
  }
  function stopSpeak() {
    try { if (audio) { audio.pause(); audio = null; } } catch (e) {}
    try { window.speechSynthesis && speechSynthesis.cancel(); } catch (e) {}
    speaking = false; setState('idle');
  }
  function browserSpeak(text) {
    return new Promise(function (res) {
      try {
        var vs = speechSynthesis.getVoices(), v = vs.filter(function (x) { return /^ur/i.test(x.lang); })[0];
        if (!v) return res(false);
        var u = new SpeechSynthesisUtterance(text); u.voice = v; u.lang = v.lang;
        u.onend = u.onerror = function () { res(true); };
        speechSynthesis.speak(u);
      } catch (e) { res(false); }
    });
  }
  function speak(text) {
    if (!text || sget(MUTE_KEY) === '1') return Promise.resolve();
    stopSpeak(); speaking = true; setState('speaking');
    var ti = 0;
    function tryTts() {
      if (ti >= TTS_MODELS.length) return Promise.reject(new Error('tts'));
      var m = TTS_MODELS[ti++];
      return gemini(m, { contents: [{ parts: [{ text: text }] }], generationConfig: { responseModalities: ['AUDIO'], speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: TTS_VOICE } } } } }, 25000)
        .then(function (r) {
          var p = r.status === 200 && r.j.candidates && r.j.candidates[0].content && r.j.candidates[0].content.parts[0];
          var d = p && p.inlineData;
          if (!d) return tryTts();
          var mt = d.mimeType || '', rate = +((mt.match(/rate=(\d+)/) || [])[1] || 24000);
          return /wav|mpeg|mp3|ogg/.test(mt) ? ('data:' + mt.split(';')[0] + ';base64,' + d.data) : pcmToWav(d.data, rate);
        }, function () { return tryTts(); });
    }
    return tryTts().then(function (src) {
      if (!speaking) return;
      return new Promise(function (res) {
        audio = new Audio(src);
        audio.onended = audio.onerror = function () { res(); };
        var pl = audio.play(); if (pl && pl.catch) pl.catch(function () { res(); });
      });
    }).catch(function () { return browserSpeak(text); }).then(function () { speaking = false; setState('idle'); });
  }

  // ---------------- voice in ----------------
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition, rec = null, listening = false;
  function listen() {
    if (!SR) { setStatus('Is browser mein mic se baat nahi hoti — Chrome istemal karein, ya neeche likh dein.'); return; }
    if (listening) { try { rec.stop(); } catch (e) {} return; }
    stopSpeak();
    rec = new SR(); rec.lang = 'ur-PK'; rec.interimResults = true; rec.maxAlternatives = 1;
    var finalTxt = '';
    rec.onstart = function () { listening = true; setState('listening'); setStatus('Sun rahi hoon…'); };
    rec.onresult = function (e) {
      var s = ''; for (var i = e.resultIndex; i < e.results.length; i++) { if (e.results[i].isFinal) finalTxt += e.results[i][0].transcript; else s += e.results[i][0].transcript; }
      $('waInput').value = (finalTxt + s).trim();
    };
    rec.onerror = function (e) { if (e.error === 'not-allowed') setStatus('Mic ki ijazat nahi mili — browser mein mic Allow karein.'); };
    rec.onend = function () { listening = false; setState('idle'); var t = (finalTxt || $('waInput').value || '').trim(); if (t) ask(t); else setStatus(hint()); };
    try { rec.start(); } catch (e) {}
  }

  // ---------------- UI ----------------
  var hist = [];
  try { hist = JSON.parse(sget(HIST_KEY) || '[]'); } catch (e) { hist = []; }
  var busyAsk = false;
  function hint() { var touch = window.matchMedia && matchMedia('(pointer:coarse)').matches; return touch ? 'Bolne ke liye logo ya mic dabayein, ya neeche likhein.' : 'Bolne ke liye logo dabayein (ya Space), ya neeche likh kar Enter.'; }
  function setStatus(t) { var el = $('waStatus'); if (el) el.textContent = t; }
  function setState(s) { var o = $('waOrb'); if (o) o.setAttribute('data-state', s); }
  function addLine(who, text) {
    var box = $('waLog'); if (!box) return;
    var p = document.createElement('div'); p.className = 'wa-line ' + who; p.textContent = text;
    box.appendChild(p);
    while (box.children.length > 12) box.removeChild(box.firstChild);
    box.scrollTop = box.scrollHeight;
  }
  var STEP_TXT = { get_market_price: 'rate dekh rahi hoon', market_analysis: 'chart analysis kar rahi hoon', ict_status: 'Silver Bullet dekh rahi hoon', market_news: 'khabrein parh rahi hoon',
                   economic_calendar: 'calendar dekh rahi hoon', daddy_trader_signals: 'Daddy Trader signals dekh rahi hoon', market_sessions: 'sessions dekh rahi hoon', currency_rate: 'rate dekh rahi hoon', open_section: 'khol rahi hoon' };

  function ask(text) {
    text = String(text || '').trim();
    if (!text || busyAsk) return;
    busyAsk = true; $('waInput').value = '';
    addLine('you', text);
    hist.push({ role: 'user', text: text });
    setState('thinking'); setStatus('Soch rahi hoon…');
    brain(hist.slice(-16), function (name) { setStatus((STEP_TXT[name] || 'kaam kar rahi hoon') + '…'); })
      .then(function (raw) {
        var r = parseReply(raw);
        hist.push({ role: 'model', text: 'SHOW: ' + r.show });
        hist = hist.slice(-20); sset(HIST_KEY, JSON.stringify(hist));
        addLine('alexa', r.show);
        setStatus(hint());
        var nav = pendingNav; pendingNav = null;
        return speak(r.speak).then(function () { if (nav) location.href = nav; });
      })
      .catch(function (e) {
        hist.pop();
        var m = String((e && e.message) || e);
        addLine('alexa', m === 'limit' ? 'Maaf kijiye ' + TITLE + ', Google ki aaj ki free limit poori ho gayi hai. Thori der baad phir poochiye.'
          : /^key/.test(m) ? 'Maaf kijiye ' + TITLE + ', Gemini key kaam nahi kar rahi.' : 'Maaf kijiye ' + TITLE + ', raabta nahi ho saka. Internet check kar ke dobara poochiye.');
        setState('idle'); setStatus(hint());
      })
      .finally(function () { busyAsk = false; });
  }

  function init() {
    if (!$('webAlexa')) return;
    if (hist.length) {
      hist.slice(-4).forEach(function (m) { addLine(m.role === 'user' ? 'you' : 'alexa', m.text.replace(/^SHOW:\s*/, '')); });
    } else {
      addLine('alexa', 'Assalam o Alaikum ' + TITLE + '! Main Alexa. Gold, forex, analysis, khabrein ya kuch bhi poochiye.');
    }
    setStatus(hint());
    $('waOrb').addEventListener('click', listen);
    $('waMic').addEventListener('click', listen);
    $('waForm').addEventListener('submit', function (e) { e.preventDefault(); ask($('waInput').value); });
    var mute = $('waMute');
    function paintMute() { var m = sget(MUTE_KEY) === '1'; mute.setAttribute('aria-pressed', m ? 'true' : 'false'); mute.title = m ? 'Awaaz band hai' : 'Awaaz on hai'; }
    mute.addEventListener('click', function () { sset(MUTE_KEY, sget(MUTE_KEY) === '1' ? '0' : '1'); if (sget(MUTE_KEY) === '1') stopSpeak(); paintMute(); });
    paintMute();
    $('waClear').addEventListener('click', function () { hist = []; sset(HIST_KEY, '[]'); $('waLog').innerHTML = ''; addLine('alexa', 'Ji ' + TITLE + ', nayi baat shuru karte hain.'); });
    document.addEventListener('keydown', function (e) {
      if (e.code === 'Space' && document.activeElement !== $('waInput') && !$('stage').classList.contains('live')) { e.preventDefault(); listen(); }
      if (e.key === 'Escape') { stopSpeak(); if (listening) try { rec.stop(); } catch (x) {} }
    });
    if (window.speechSynthesis) try { speechSynthesis.getVoices(); } catch (e) {}
  }

  window.AlexaWeb = { ask: ask, busy: function () { return busyAsk || speaking || listening; }, stop: stopSpeak, _tools: TOOLS };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
