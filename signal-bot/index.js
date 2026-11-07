/* Daddy Trader — Gold signal bot (Cloudflare Worker)
 *
 * Har 5 minute (cron) chalta hai:
 *   1. XAU/USD ki M5 candles laata hai (Dukascopy, warna Twelve Data)
 *   2. engine.js se ICT setups dhoondta hai:
 *        ICT 2022 Model : liquidity hunt -> MSS -> M5 FVG
 *        Model 1        : H1 FVG tap -> BOS -> M5 FVG
 *      FVG bante hi signal post (limit entry FVG ke kinare par)
 *   3. Purane signals ka status chalata hai: Pending -> Active -> TP Hit / SL Hit
 *      (1 ghante mein entry na mile ya price bhaag jaye to Cancelled)
 *   4. Sab kuch KV mein rakhta hai; website /signals.json se parhti hai
 *   5. Naye signal par phone notification (ntfy.sh)
 */
import { run, trace, toM15, marketBias, liquidityMap, nyOffset, MODEL_NAMES, P } from "./engine.js";

const MODELS = ["2022", "M1"];
const LOOKBACK = 1000;          // M5 candles (~3.5 din)
const NEW_MIN = 60;             // itne minute purana setup bhi post ho sakta hai
const NOTIFY_MIN = 30;          // phone notification sirf taaza signal par
const KEEP_DAYS = 14;
const MAX_KEEP = 40;
const MAX_HITS = 100;           // TP hit cards kitne purane tak rakhne hain
const FINAL = new Set(["TP Hit", "SL Hit", "Expired", "Cancelled"]);
const PKT = 5 * 3600e3;
const BAR = 300e3;

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(scan(env, event.scheduledTime || Date.now()));
  },

  async fetch(req, env, ctx) {
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
    };
    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    const url = new URL(req.url);
    if (url.pathname !== "/" && url.pathname !== "/signals.json") {
      return new Response("Not found", { status: 404, headers: cors });
    }
    // 30 second cache, taake har visitor par KV na parhna pare
    const cache = caches.default;
    const key = new Request(url.origin + "/signals.json");
    let res = await cache.match(key);
    if (!res) {
      const body = (await env.SIG.get("state")) || JSON.stringify({ updated: null, market: null, signals: [] });
      res = new Response(body, {
        headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "public, max-age=30" },
      });
      ctx.waitUntil(cache.put(key, res.clone()));
    }
    const out = new Response(res.body, res);
    for (const [k, v] of Object.entries(cors)) out.headers.set(k, v);
    return out;
  },
};

/* ---------------- data ---------------- */

const UA = { "User-Agent": "Mozilla/5.0 (DaddyTrader signal bot)" };

async function twelvedata(key) {
  const url = "https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=5min&outputsize=" +
    LOOKBACK + "&timezone=UTC&apikey=" + encodeURIComponent(key);
  const r = await fetch(url, { headers: UA });
  const data = await r.json();
  const vals = data.values;
  if (!vals || !vals.length) throw new Error("TD: " + String(data.message || "no values").slice(0, 120));
  const out = new Array(vals.length);
  for (let i = 0; i < vals.length; i++) {
    const x = vals[vals.length - 1 - i];
    out[i] = { t: Date.parse(x.datetime.replace(" ", "T") + "Z"), o: +x.open, h: +x.high, l: +x.low, c: +x.close };
  }
  return out;
}

async function dukascopy() {
  const url = "https://freeserv.dukascopy.com/2.0/index.php?path=chart%2Fjson3&instrument=XAU%2FUSD" +
    "&offer_side=B&interval=5MIN&limit=" + LOOKBACK + "&time_direction=N&jsonp=";
  const r = await fetch(url, { headers: { ...UA, Referer: "https://freeserv.dukascopy.com/2.0/" } });
  let txt = await r.text();
  txt = txt.slice(txt.indexOf("["), txt.lastIndexOf("]") + 1);
  const rows = JSON.parse(txt);
  if (!rows.length) throw new Error("duka: empty");
  return rows.map((x) => ({ t: +x[0], o: +x[1], h: +x[2], l: +x[3], c: +x[4] }));
}

async function fetchGold(env) {
  const errs = [];
  // Dukascopy pehle: backtest bhi isi feed par hua hai. Twelve Data sirf backup (agar key rakhi ho)
  const sources = [["SPOT-duka", dukascopy]];
  if (env.TD_KEY) sources.push(["XAUUSD-spot", () => twelvedata(env.TD_KEY)]);
  for (const [name, fn] of sources) {
    try {
      const c = await fn();
      if (c.length > 60) return { candles: c, src: name, errs };
      errs.push(name + ": short data");
    } catch (e) {
      errs.push(name + ": " + String(e && e.message || e).slice(0, 140));
    }
  }
  return { candles: null, src: null, errs };
}

/* ---------------- helpers ---------------- */

function marketClosed(ms) {
  const d = new Date(ms), wd = d.getUTCDay(), h = d.getUTCHours();   // Sun=0
  if (wd === 5 && h >= 21) return true;
  if (wd === 6) return true;
  if (wd === 0 && h < 22) return true;
  return false;
}

// Naya setup sirf session ke andar banta hai (Asia 20-24, London 2-5, NY 7-11, NY time).
// Session ke dauran aur us ke 1 ghanta baad tak engine chalao; baqi waqt CPU bachao.
function nearSession(ms) {
  const local = ms + nyOffset(ms) * 3600e3;
  const h = (((Math.floor(local / 60000) % 1440) + 1440) % 1440) / 60;
  return (h >= 20 || h < 1) || (h >= 2 && h < 6) || (h >= 7 && h < 12);
}

function pkt(ms) {
  const d = new Date(ms + PKT);
  const p = (x) => String(x).padStart(2, "0");
  return p(d.getUTCDate()) + "-" + p(d.getUTCMonth() + 1) + "-" + d.getUTCFullYear() + " " +
    p(d.getUTCHours()) + ":" + p(d.getUTCMinutes()) + " PKT";
}

function makeSignal(s) {
  const at = s.t + BAR;                       // FVG wali candle band hone ka waqt
  const why = s.model === "2022"
    ? "Liquidity hunt (" + s.lvl + " swept) → MSS → M5 FVG"
    : "H1 FVG tap → BOS → M5 FVG";
  return {
    id: s.model + "|" + s.t,
    ts: new Date(at).toISOString(),
    date: pkt(at),
    t: s.t,
    pair: "XAUUSD",
    model: s.model,
    model_name: MODEL_NAMES[s.model],
    type: s.type,
    order: "Limit",
    entry: s.entry,
    sl: s.sl,
    tp: s.tp,
    rr: Math.round((Math.abs(s.tp - s.entry) / Math.abs(s.entry - s.sl)) * 10) / 10,
    guard: Math.round(s.guard * 100) / 100,
    status: "Pending",
    note: MODEL_NAMES[s.model] + ": " + why + ". Limit entry at the FVG; cancel if not filled in 1 hour.",
  };
}

function advance(sig, candles, idxOf, now) {
  if (FINAL.has(sig.status)) return;
  const i0 = idxOf.get(sig.t);
  if (i0 === undefined) {
    // candle window se bahar — itna purana signal khud khatam
    if (now - sig.t > (P.expire_h + 2) * 3600e3) {
      sig.status = sig.status === "Active" ? "Expired" : "Cancelled";
    }
    return;
  }
  const tr = trace(sig, candles, i0);
  if (tr.status !== sig.status) {
    sig.status = tr.status;
    if (tr.fillT) sig.filled = pkt(tr.fillT + BAR);
    if (tr.endT) sig.closed = pkt(tr.endT + BAR);
  }
}

async function notify(env, s) {
  const topic = env.NTFY_TOPIC || "daddytrader-ali-signals";
  const msg = s.type + " " + s.pair + " (limit) @ " + s.entry + " | SL " + s.sl + " | TP " + s.tp +
    " | " + s.model_name;
  try {
    await fetch("https://ntfy.sh/" + topic, { method: "POST", headers: { Title: "Daddy Trader Signal" }, body: msg });
  } catch (e) { /* notification fail ho to bhi signal site par rahe */ }
}

/* ---------------- main scan ---------------- */

async function scan(env, now) {
  const prev = (await env.SIG.get("state", "json")) || {};
  let sigs = Array.isArray(prev.signals) ? prev.signals : [];
  const closed = marketClosed(now);
  const out = {
    updated: pkt(now),
    market: closed ? "closed" : "open",
    src: null,
    err: null,
    bias: null,
    liq: null,
    idea: null,
    bot: "Cloudflare · every 5 min · " + MODELS.map((m) => MODEL_NAMES[m]).join(" + "),
    signals: sigs,
  };

  // weekend par sirf ghante mein ek dafa data check (feed theek hai ya nahi)
  const doFetch = !closed || new Date(now).getUTCMinutes() < 5;
  const fresh = [];
  if (doFetch) {
    const { candles: raw, src, errs } = await fetchGold(env);
    out.src = src;
    if (!raw) out.err = errs;
    if (raw) {
      const candles = raw.filter((k) => k.t + BAR <= now).slice(-LOOKBACK);   // sirf band candles
      const idxOf = new Map();
      for (let i = 0; i < candles.length; i++) idxOf.set(candles[i].t, i);
      if (!closed && nearSession(now)) {
        const { setups } = run(candles, { models: MODELS, mode: "live" });
        const have = new Set(sigs.map((s) => s.id));
        for (const s of setups) {
          const id = s.model + "|" + s.t;
          if (have.has(id) || now - (s.t + BAR) > NEW_MIN * 60e3) continue;
          // dono models ne bilkul wohi trade di? ek hi card, dono naam
          const twin = sigs.find((x) => x.t === s.t && x.type === s.type && x.entry === s.entry && x.sl === s.sl);
          if (twin) {
            if (!twin.model_name.includes(MODEL_NAMES[s.model])) twin.model_name += " + " + MODEL_NAMES[s.model];
            have.add(id);
            continue;
          }
          const sig = makeSignal(s);
          sigs.push(sig);
          have.add(id);
          if (now - (s.t + BAR) <= NOTIFY_MIN * 60e3) fresh.push(sig);
        }
      }
      if (!closed) {
        const m15 = toM15(candles);
        out.bias = marketBias(m15);
        if (m15.length > 3) out.liq = liquidityMap(m15.slice(0, -1), m15[m15.length - 2].c);
      }
      for (const s of sigs) advance(s, candles, idxOf, now);
      out.last_candle = candles.length ? pkt(candles[candles.length - 1].t + BAR) : null;
    }
  } else {
    out.src = prev.src || null;
  }

  // TP hit wale trades ki alag fehrist — website par har ek ka alag card (date + time ke saath)
  const hits = Array.isArray(prev.tp_hits) ? prev.tp_hits : [];
  const hitIds = new Set(hits.map((h) => h.id));
  for (const s of sigs) {
    if (s.status === "TP Hit" && !hitIds.has(s.id)) {
      hits.push({
        id: s.id, pair: s.pair, type: s.type, model_name: s.model_name,
        entry: s.entry, sl: s.sl, tp: s.tp, rr: s.rr,
        signal: s.date, hit: s.closed || pkt(now),
      });
      hitIds.add(s.id);
    }
  }
  out.tp_hits = hits.slice(-MAX_HITS);

  sigs = sigs.filter((s) => now - s.t < KEEP_DAYS * 864e5).slice(-MAX_KEEP);
  out.signals = sigs;
  await env.SIG.put("state", JSON.stringify(out));
  for (const s of fresh) await notify(env, s);
}
