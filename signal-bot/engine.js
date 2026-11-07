/* Daddy Trader — ICT signal engine (Gold, M5) — JavaScript.
 *
 * ict_engine.py ka hoo-ba-hoo tarjuma (sirf do models):
 *   2022 : liquidity hunt (PDH/PDL ya pichla session high/low sweep)
 *          -> MSS (structure toote, displacement ke saath) -> M5 FVG
 *   M1   : H1 FVG (HTF POI) tap -> BOS -> M5 FVG
 *
 * Sessions (New York time, DST khud sambhalta hai):
 *   Asia 20:00-24:00 · London 02:00-05:00 · New York 07:00-11:00
 *
 * mode "live": FVG bante hi signal (Pending limit order, entry = FVG ka
 *   qareebi kinara). TP/SL usi waqt fix. Phir advance() status chalata hai:
 *   Pending -> Active -> TP Hit / SL Hit / Expired, ya Cancelled.
 * mode "py": bilkul Python jaisa (entry fill hone par signal) — sirf jaanch ke liye.
 */

export const P = {
  min_rr: 2.0,
  max_rr: 6.0,
  sweep_life: 24,
  fill_life: 12,
  fvg_min_atr: 0.15,
  disp_atr: 1.0,
  pad_atr: 0.15,
  min_risk: 1.5,
  max_risk_atr: 6.0,
  expire_h: 12,
  live_rr: 3.0,          // live signals: TP hamesha 1:3 (risk ka 3 guna)
};

export const MODEL_NAMES = {
  "2022": "ICT 2022 Model",
  M1: "Model 1 (HTF POI + BOS + FVG)",
};

const HOUR = 3600e3;
const DAY = 86400e3;

function nthSunday(y, m, n) {
  const first = (7 - new Date(Date.UTC(y, m, 1)).getUTCDay()) % 7;
  return Date.UTC(y, m, 1 + first + 7 * (n - 1));
}

// [yearStart, yearEnd, dstStart, dstEnd] — har candle par naya Date na banana pare
let yr = [0, -1, 0, 0];
export function nyOffset(ms) {
  if (ms < yr[0] || ms >= yr[1]) {
    const y = new Date(ms).getUTCFullYear();
    yr = [Date.UTC(y, 0, 1), Date.UTC(y + 1, 0, 1), nthSunday(y, 2, 2) + 7 * HOUR, nthSunday(y, 10, 1) + 6 * HOUR];
  }
  return ms >= yr[2] && ms < yr[3] ? -4 : -5;
}

function sessionOf(h) {
  if (h >= 20 && h < 24) return "asia";
  if (h >= 2 && h < 5) return "london";
  if (h >= 7 && h < 11) return "ny";
  return "";
}

// numpy jaisa round (half-to-even), taake Python wale numbers se hoo-ba-hoo milein
const r2 = (x) => {
  const v = x * 100;
  let r = Math.round(v);
  if (r - v === 0.5 && r % 2 !== 0) r -= 1;
  return r / 100;
};

function bisectLeft(a, x) {
  let lo = 0, hi = a.length;
  while (lo < hi) {
    const m = (lo + hi) >> 1;
    if (a[m] < x) lo = m + 1; else hi = m;
  }
  return lo;
}

/* candles: [{t (ms, bar open UTC), o, h, l, c}] oldest first */
export function prepare(candles) {
  const n = candles.length;
  const T = new Float64Array(n), O = new Float64Array(n), H = new Float64Array(n),
    L = new Float64Array(n), C = new Float64Array(n), ATR = new Float64Array(n);
  const SESS = new Array(n), TDAY = new Int32Array(n);
  for (let i = 0; i < n; i++) {
    const k = candles[i];
    T[i] = k.t; O[i] = k.o; H[i] = k.h; L[i] = k.l; C[i] = k.c;
    const local = k.t + nyOffset(k.t) * HOUR;
    const mins = Math.floor(local / 60000);
    const h = (((mins % 1440) + 1440) % 1440) / 60;
    SESS[i] = sessionOf(h);
    TDAY[i] = Math.floor((local - 18 * HOUR) / DAY);
  }
  const TR = new Float64Array(n);
  TR[0] = NaN;
  for (let i = 1; i < n; i++) {
    const pc = C[i - 1];
    TR[i] = Math.max(H[i] - L[i], Math.max(Math.abs(H[i] - pc), Math.abs(L[i] - pc)));
  }
  // rolling(14, min_periods=5).mean() — TR[0] NaN hai, baqi sab number
  let s = 0;
  for (let i = 1; i < n; i++) {
    s += TR[i];
    if (i >= 15) s -= TR[i - 14];
    const cnt = Math.min(i, 14);
    ATR[i] = cnt >= 5 ? s / cnt : NaN;
  }
  ATR[0] = NaN;
  return { n, T, O, H, L, C, ATR, SESS, TDAY };
}

function buildLevels(d) {
  const { n, T, H, L, SESS, TDAY } = d;
  // previous trading-day high/low
  const dh = new Map(), dl = new Map(), order = [];
  for (let i = 0; i < n; i++) {
    const k = TDAY[i];
    if (!dh.has(k)) { dh.set(k, H[i]); dl.set(k, L[i]); order.push(k); }
    else { if (H[i] > dh.get(k)) dh.set(k, H[i]); if (L[i] < dl.get(k)) dl.set(k, L[i]); }
  }
  const prev = new Map();
  for (let k = 1; k < order.length; k++) prev.set(order[k], order[k - 1]);
  const pdh = new Float64Array(n), pdl = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const p = prev.get(TDAY[i]);
    pdh[i] = p === undefined ? NaN : dh.get(p);
    pdl[i] = p === undefined ? NaN : dl.get(p);
  }
  // completed sessions: [end, name, hi, lo, start]
  const sessions = [];
  let start = -1;
  for (let i = 0; i <= n; i++) {
    const s = i < n ? SESS[i] : null;
    if (start >= 0 && (s !== SESS[start] || (i < n && TDAY[i] !== TDAY[start]))) {
      let hi = -Infinity, lo = Infinity;
      for (let j = start; j < i; j++) { if (H[j] > hi) hi = H[j]; if (L[j] < lo) lo = L[j]; }
      sessions.push([i - 1, SESS[start], hi, lo, start]);
      start = -1;
    }
    if (start < 0 && s && i < n) start = i;
  }
  const sessEnd = sessions.map((x) => x[0]);
  // M5 fractal swings
  const sh = [], sl = [];
  for (let j = 2; j < n - 2; j++) {
    if (H[j] >= H[j - 1] && H[j] >= H[j - 2] && H[j] > H[j + 1] && H[j] > H[j + 2]) sh.push(j);
    if (L[j] <= L[j - 1] && L[j] <= L[j - 2] && L[j] < L[j + 1] && L[j] < L[j + 2]) sl.push(j);
  }
  // M15-ish swings (har 3 candles ka group) — targets ke liye
  const m = 3, gN = Math.ceil(n / m);
  const hh = new Float64Array(gN).fill(-Infinity), ll = new Float64Array(gN).fill(Infinity);
  for (let i = 0; i < n; i++) {
    const g = (i / m) | 0;
    if (H[i] > hh[g]) hh[g] = H[i];
    if (L[i] < ll[g]) ll[g] = L[i];
  }
  const bigSh = [], bigSl = [];
  for (let j = 2; j < gN - 2; j++) {
    const conf = Math.min((j + 3) * m - 1, n - 1);
    if (hh[j] >= hh[j - 1] && hh[j] >= hh[j - 2] && hh[j] > hh[j + 1] && hh[j] > hh[j + 2]) bigSh.push([conf, hh[j], j * m]);
    if (ll[j] <= ll[j - 1] && ll[j] <= ll[j - 2] && ll[j] < ll[j + 1] && ll[j] < ll[j + 2]) bigSl.push([conf, ll[j], j * m]);
  }
  // H1 FVGs: [conf, dir, lo, hi]
  const hrs = [];
  for (let i = 0; i < n; i++) {
    const hk = Math.floor(T[i] / HOUR);
    const last = hrs[hrs.length - 1];
    if (!last || last.k !== hk) hrs.push({ k: hk, last: i, h: H[i], l: L[i] });
    else { last.last = i; if (H[i] > last.h) last.h = H[i]; if (L[i] < last.l) last.l = L[i]; }
  }
  const h1fvg = [];
  for (let k = 2; k < hrs.length; k++) {
    const conf = hrs[k].last;
    if (hrs[k].l > hrs[k - 2].h) h1fvg.push([conf, "bull", hrs[k - 2].h, hrs[k].l]);
    if (hrs[k].h < hrs[k - 2].l) h1fvg.push([conf, "bear", hrs[k].h, hrs[k - 2].l]);
  }

  // external liquidity: [price, name] pairs (flat array: p0, n0, p1, n1, ...)
  const hiName = { asia: "ASIA High", london: "LONDON High", ny: "NY High" };
  const loName = { asia: "ASIA Low", london: "LONDON Low", ny: "NY Low" };
  function external(i, high) {
    const out = [];
    if (high) { if (pdh[i] === pdh[i]) out.push(pdh[i], "PDH"); }
    else if (pdl[i] === pdl[i]) out.push(pdl[i], "PDL");
    const t = T[i];
    const k = bisectLeft(sessEnd, i);
    for (let q = Math.max(0, k - 8); q < k; q++) {
      const s = sessions[q];
      if (t - T[s[0]] > 30 * HOUR) continue;
      if (high) out.push(s[2], hiName[s[1]]); else out.push(s[3], loName[s[1]]);
    }
    return out;
  }

  function targets(i, dir, entry) {
    const pools = [];
    const from = Math.max(0, i - 600);
    const ext = external(i, dir !== "SELL");
    for (let q = 0; q < ext.length; q += 2) pools.push(ext[q]);
    if (dir === "SELL") {
      // run[j] = min(L[j..i])
      const run = new Float64Array(i - from + 2);
      run[i - from + 1] = 1e18;
      for (let j = i; j >= from; j--) run[j - from] = Math.min(L[j], run[j - from + 1]);
      for (let q = 0; q < bigSl.length; q++) {
        const conf = bigSl[q][0], p = bigSl[q][1];
        if (conf < i && i - conf < 600 && run[conf + 1 - from] > p) pools.push(p);
      }
      return pools.filter((x) => x < entry).sort((a, b) => b - a);
    }
    const run = new Float64Array(i - from + 2);
    run[i - from + 1] = -1e18;
    for (let j = i; j >= from; j--) run[j - from] = Math.max(H[j], run[j - from + 1]);
    for (let q = 0; q < bigSh.length; q++) {
      const conf = bigSh[q][0], p = bigSh[q][1];
      if (conf < i && i - conf < 600 && run[conf + 1 - from] < p) pools.push(p);
    }
    return pools.filter((x) => x > entry).sort((a, b) => a - b);
  }

  return { pdh, pdl, sessions, sh, sl, h1fvg, external, targets };
}

function pickTp(lv, i, dir, entry, sl) {
  const risk = Math.abs(entry - sl);
  for (const p of lv.targets(i, dir, entry)) {
    const rr = Math.abs(p - entry) / risk;
    if (rr >= P.min_rr) {
      if (rr <= P.max_rr) return [r2(p), "liquidity"];
      break;
    }
  }
  return [r2(dir === "SELL" ? entry - P.min_rr * risk : entry + P.min_rr * risk), "1:2"];
}

function findFvg(d, a, b, dir, atr) {
  const { H, L } = d;
  let best = null;
  for (let j = Math.max(a, 1); j < b; j++) {
    let lo, hi;
    if (dir === "SELL") { lo = H[j + 1]; hi = L[j - 1]; }
    else { lo = H[j - 1]; hi = L[j + 1]; }
    const size = hi - lo;
    if (size > P.fvg_min_atr * atr && (best === null || size > best[1] - best[0])) best = [lo, hi, j];
  }
  return best;
}

/* Returns { setups, d }.
 * live mode: setups = FVG bante hi (har ek: model,type,entry,sl,tp,tpk,guard,i,t,why)
 * py mode:   setups = Python jaisa, entry fill par */
export function run(candles, { models = ["2022", "M1"], mode = "live" } = {}) {
  const d = prepare(candles);
  const lv = buildLevels(d);
  const { n, T, O, H, L, C, ATR, SESS } = d;
  const want = new Set(models);
  let sweeps = [];
  let pend = [];
  const usedHi = new Set(), usedLo = new Set(), usedH1 = new Set();
  const out = [];
  let shPtr = 0, slPtr = 0, h1Lo = 0;
  const confSh = [], confSl = [];

  function riskOk(entry, sl, i) {
    const risk = Math.abs(entry - sl);
    return !(risk < P.min_risk || risk > P.max_risk_atr * ATR[i]);
  }

  function addPend(base, model, entry, why) {
    const sl = base.sl;
    const guard = base.dir === "SELL" ? entry - P.min_rr * (sl - entry) : entry + P.min_rr * (entry - sl);
    const x = { ...base, model, entry, why, guard };
    if (mode === "live") {
      if (!riskOk(entry, sl, base.made)) return;
      // TP = 1:3. Agar entry se pehle hi price TP tak chali jaye to signal cancel.
      const risk = Math.abs(entry - sl);
      const tpRaw = base.dir === "SELL" ? entry - P.live_rr * risk : entry + P.live_rr * risk;
      out.push({ model, type: base.dir, entry: r2(entry), sl: r2(sl), tp: r2(tpRaw), tpk: "1:3",
        guard: tpRaw, i: base.made, t: T[base.made], why, lvl: base.lvlName });
      return;
    }
    pend.push(x);
  }

  function emitPy(s, i) {
    if (!riskOk(s.entry, s.sl, i)) return;
    const [tp, tpk] = pickTp(lv, i, s.dir, s.entry, s.sl);
    out.push({ model: s.model, type: s.dir, entry: r2(s.entry), sl: r2(s.sl), tp, tpk, i, t: T[i], why: s.why });
  }

  for (let i = 20; i < n; i++) {
    const atr = ATR[i];
    if (!(atr > 0)) continue;
    while (shPtr < lv.sh.length && lv.sh[shPtr] + 2 <= i) confSh.push(lv.sh[shPtr++]);
    while (slPtr < lv.sl.length && lv.sl[slPtr] + 2 <= i) confSl.push(lv.sl[slPtr++]);
    const insess = !!SESS[i];
    const pad = P.pad_atr * atr;

    // 1) pending entries (sirf py mode)
    if (pend.length) {
      const keep = [];
      for (const s of pend) {
        if (i <= s.made) { keep.push(s); continue; }
        const filled = s.dir === "SELL" ? H[i] >= s.entry : L[i] <= s.entry;
        if (filled) { if (SESS[i]) emitPy(s, i); continue; }
        const ran = s.dir === "SELL" ? L[i] <= s.guard : H[i] >= s.guard;
        if (ran) continue;
        if (i - s.made < s.life) keep.push(s);
      }
      pend = keep;
    }

    if (!insess) {
      sweeps = sweeps.filter((w) => i - w.bar <= P.sweep_life);
      continue;
    }

    // 2) naye sweeps
    for (let side = 0; side < 2; side++) {
      const high = side === 0;
      const ext = lv.external(i, high);
      const usedSide = high ? usedHi : usedLo;
      for (let q = 0; q < ext.length; q += 2) {
        const p = ext[q];
        const key = r2(p);
        if (usedSide.has(key)) continue;
        const prevOk = high ? H[i - 1] < p : L[i - 1] > p;
        const hit = high ? H[i] > p : L[i] < p;
        if (hit && prevOk) {
          usedSide.add(key);
          sweeps.push({ dir: high ? "SELL" : "BUY", lvl: p, name: ext[q + 1], bar: i, ext: high ? H[i] : L[i], kind: "ext" });
        }
      }
    }
    while (h1Lo < lv.h1fvg.length && i - lv.h1fvg[h1Lo][0] > 72 * 12) h1Lo++;
    for (let q = h1Lo; q < lv.h1fvg.length; q++) {
      const f = lv.h1fvg[q];
      const conf = f[0];
      if (conf >= i) break;
      if (usedH1.has(q)) continue;
      const fd = f[1], lo = f[2], hi = f[3];
      if (fd === "bear" && H[i] >= lo && H[i - 1] < lo) {
        usedH1.add(q);
        sweeps.push({ dir: "SELL", lvl: lo, name: "H1 FVG", bar: i, ext: H[i], kind: "poi" });
      }
      if (fd === "bull" && L[i] <= hi && L[i - 1] > hi) {
        usedH1.add(q);
        sweeps.push({ dir: "BUY", lvl: hi, name: "H1 FVG", bar: i, ext: L[i], kind: "poi" });
      }
    }

    // 3) har active sweep: extreme update, MSS
    const keep = [];
    for (const w of sweeps) {
      if (i - w.bar > P.sweep_life) continue;
      const dir = w.dir;
      if (i > w.bar) {
        if (dir === "SELL" && H[i] > w.ext) { w.ext = H[i]; w.extBar = i; }
        if (dir === "BUY" && L[i] < w.ext) { w.ext = L[i]; w.extBar = i; }
      }
      const eb = w.extBar ?? w.bar;
      if (!("ref" in w)) {
        const lst = dir === "SELL" ? confSl : confSh;
        let k = bisectLeft(lst, w.bar) - 1;
        let ref = null;
        while (k >= 0 && w.bar - lst[k] < 150) {
          const j = lst[k];
          if ((dir === "SELL" && L[j] < w.ext) || (dir === "BUY" && H[j] > w.ext)) { ref = j; break; }
          k--;
        }
        w.ref = ref;
      }
      const ref = w.ref;
      const broke = ref !== null && (dir === "SELL" ? C[i] < L[ref] : C[i] > H[ref]);
      if (!broke) { keep.push(w); continue; }
      let body = 0;
      for (let j = eb; j <= i; j++) { const b = Math.abs(C[j] - O[j]); if (b > body) body = b; }
      if (body < P.disp_atr * atr) continue;
      const fvg = findFvg(d, eb + 1, i, dir, atr);
      if (!fvg) continue;
      const [lo, hi] = fvg;
      const sl = dir === "SELL" ? w.ext + pad : w.ext - pad;
      const base = { dir, sl, made: i, life: P.fill_life, lvlName: w.name };
      const entry = dir === "SELL" ? lo : hi;
      if (w.kind === "ext" && want.has("2022")) addPend(base, "2022", entry, w.name + " swept -> MSS -> FVG");
      if (w.kind === "poi" && want.has("M1")) addPend(base, "M1", entry, "H1 FVG tap -> BOS -> FVG");
    }
    sweeps = keep;
  }
  return { setups: out, d };
}

/* Signal ka status candles se nikalo (live mode wale signal ke liye).
 * sig: {type, entry, sl, tp, guard, t}  candles: [{t,o,h,l,c}] (sirf band candles)
 * Returns {status, fillT, endT} */
export function trace(sig, candles, startIdx = 0) {
  const buy = sig.type === "BUY";
  let status = "Pending", fillT = null, endT = null, k = 0;
  for (let j = startIdx; j < candles.length; j++) {
    const b = candles[j];
    if (b.t <= sig.t) continue;
    if (status === "Pending") {
      k++;
      const filled = buy ? b.l <= sig.entry : b.h >= sig.entry;
      if (filled) {
        status = "Active"; fillT = b.t;
        if (buy ? b.l <= sig.sl : b.h >= sig.sl) { status = "SL Hit"; endT = b.t; break; }
        continue;
      }
      const ran = buy ? b.h >= sig.guard : b.l <= sig.guard;
      if (ran) { status = "Cancelled"; endT = b.t; break; }
      if (k >= P.fill_life) { status = "Cancelled"; endT = b.t; break; }
      continue;
    }
    // Active
    if (buy ? b.l <= sig.sl : b.h >= sig.sl) { status = "SL Hit"; endT = b.t; break; }
    if (buy ? b.h >= sig.tp : b.l <= sig.tp) { status = "TP Hit"; endT = b.t; break; }
    if (b.t - fillT >= P.expire_h * HOUR) { status = "Expired"; endT = b.t; break; }
  }
  return { status, fillT, endT };
}

/* ---- Market bias + liquidity map (M15) — signals.py jaisa ---- */
export function toM15(candles) {
  const out = [];
  for (const k of candles) {
    const t = Math.floor(k.t / 900e3) * 900e3;
    const last = out[out.length - 1];
    if (!last || last.t !== t) out.push({ t, o: k.o, h: k.h, l: k.l, c: k.c });
    else { if (k.h > last.h) last.h = k.h; if (k.l < last.l) last.l = k.l; last.c = k.c; }
  }
  return out;
}

export function marketBias(m15) {
  const n = m15.length;
  if (n < 60) return null;
  const ema = (span) => {
    const a = 2 / (span + 1), r = new Float64Array(n);
    r[0] = m15[0].c;
    for (let i = 1; i < n; i++) r[i] = a * m15[i].c + (1 - a) * r[i - 1];
    return r;
  };
  const e20 = ema(20), e50 = ema(50);
  const i = n - 2;
  let g = 0, l = 0;
  for (let j = i - 13; j <= i; j++) {
    const dlt = m15[j].c - m15[j - 1].c;
    if (dlt > 0) g += dlt; else l -= dlt;
  }
  g /= 14; l /= 14;
  const rsi = 100 - 100 / (1 + g / (l || 1e-9));
  let score = 0;
  score += e20[i] > e50[i] ? 1 : -1;
  score += m15[i].c > e20[i] ? 1 : -1;
  if (rsi > 55) score += 1; else if (rsi < 45) score -= 1;
  const dir = score >= 2 ? "BUY" : score <= -2 ? "SELL" : "NEUTRAL";
  return { dir, strength: Math.floor((Math.abs(score) / 3) * 100), price: r2(m15[i].c), rsi: Math.floor(rsi), tf: "M15" };
}

export function liquidityMap(m15, price) {
  const n = m15.length;
  const above = new Set(), below = new Set();
  for (let i = 2; i < n - 2; i++) {
    const h = m15[i].h, l = m15[i].l;
    if (h >= m15[i - 1].h && h >= m15[i - 2].h && h > m15[i + 1].h && h > m15[i + 2].h && h > price) {
      let mx = 0;
      for (let j = i + 3; j < n; j++) if (m15[j].h > mx) mx = m15[j].h;
      if (mx < h) above.add(r2(h));
    }
    if (l <= m15[i - 1].l && l <= m15[i - 2].l && l < m15[i + 1].l && l < m15[i + 2].l && l < price) {
      let mn = 1e12;
      for (let j = i + 3; j < n; j++) if (m15[j].l < mn) mn = m15[j].l;
      if (mn > l) below.add(r2(l));
    }
  }
  return {
    above: [...above].sort((a, b) => a - b).slice(0, 3),
    below: [...below].sort((a, b) => b - a).slice(0, 3),
  };
}
