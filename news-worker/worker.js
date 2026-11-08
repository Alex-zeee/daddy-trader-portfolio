// Daddy Trader — tez Gold news (Cloudflare Worker)
//
// Website har minute  https://<worker>/news  parhti hai.
// Worker usi waqt 5 news feeds se taaza headlines laata hai (zyada se zyada 60 second purani),
// gold se mutalliq khabrein chunta hai, Roman Urdu translation lagata hai aur JSON deta hai.
// Roman Urdu: robot (monitor.json) ki AI translation, nayi khabar ke liye Cloudflare Workers AI (binding naam: AI).
// Koi KV / cron nahi chahiye — Cloudflare ka free plan kaafi hai.

const FEEDS = [
  ["investingLive", "https://investinglive.com/feed"],
  ["Federal Reserve", "https://www.federalreserve.gov/feeds/press_monetary.xml"],
  ["FXStreet", "https://www.fxstreet.com/rss/news"],
  ["Investing.com", "https://www.investing.com/rss/news_11.rss"],
  ["CNBC", "https://www.cnbc.com/id/20910258/device/rss/rss.html"],
];
const KEY = /gold|xau|silver|precious|bullion|fed|fomc|powell|us dollar|u\.s\. dollar|usd|greenback|dxy|inflation|cpi|ppi|nfp|payroll|jobs report|rate cut|rate hike|yield|treasury|safe.haven|tariff|geopolit|iran|non-farm/i;
const MAX_AGE_H = 96;
const KEEP = 10;
const CACHE_SEC = 60;          // website ko khabar zyada se zyada 60 second purani milti hai
const MONITOR = "https://daddytrader.live/monitor.json"; // pehle se bani Roman Urdu yahan se
const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, OPTIONS",
  "content-type": "application/json; charset=utf-8",
};
// worker ki apni yaad (jab tak chal raha hai): pichla jawab aur translations
let MEM = { at: 0, body: "" };
const TR = new Map();

function decode(s) {
  return String(s || "")
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#0?39;|&apos;|&#8217;|&rsquo;/g, "'")
    .replace(/&#8216;|&lsquo;/g, "'").replace(/&#822[01];|&[lr]dquo;/g, '"')
    .replace(/&#8211;|&ndash;/g, "-").replace(/&#8212;|&mdash;/g, "-")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n))
    .replace(/\s+/g, " ").trim();
}

function tag(block, name) {
  const m = block.match(new RegExp("<" + name + "(?:\\s[^>]*)?>([\\s\\S]*?)</" + name + ">", "i"));
  return m ? decode(m[1]) : "";
}

function pkTime(ts) {
  const d = new Date(ts * 1000 + 5 * 3600e3);
  const mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][d.getUTCMonth()];
  let h = d.getUTCHours();
  const ap = h >= 12 ? "PM" : "AM";
  h = h % 12 || 12;
  const p2 = (n) => String(n).padStart(2, "0");
  return p2(d.getUTCDate()) + " " + mon + " · " + p2(h) + ":" + p2(d.getUTCMinutes()) + " " + ap;
}

async function feed(src, url) {
  try {
    const r = await fetch(url, {
      headers: { "user-agent": "Mozilla/5.0 (DaddyTrader news bot; +https://daddytrader.live)" },
      cf: { cacheTtl: 30, cacheEverything: true },
    });
    if (!r.ok) return [];
    const xml = await r.text();
    const out = [];
    const now = Date.now() / 1000;
    for (const m of xml.matchAll(/<item[\s>][\s\S]*?<\/item>/gi)) {
      const b = m[0];
      const title = tag(b, "title");
      if (!title || !KEY.test(title)) continue;
      let link = tag(b, "link");
      if (!link) { const g = b.match(/<guid[^>]*>([^<]+)<\/guid>/i); link = g ? g[1].trim() : ""; }
      const ts = Date.parse(tag(b, "pubDate")) / 1000 || now;
      if (now - ts > MAX_AGE_H * 3600) continue;
      out.push({ ts, title: title.slice(0, 170), src, link });
    }
    return out;
  } catch (e) {
    return [];
  }
}

const AI_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";
const AI_PROMPT = "You translate English financial news headlines into natural Roman Urdu (Urdu written in English letters), " +
  "the way Pakistani traders write on WhatsApp. Keep names, tickers and numbers as they are (Gold, Fed, USD, NFP, 4,040). " +
  "Reply with only the translation as one short sentence, no quotes, no notes.";

async function romanUr(text, env, cache) {
  if (TR.has(text)) return TR.get(text);
  const key = new Request("https://cache.local/tr/" + encodeURIComponent(text.slice(0, 160)));
  const hit = await cache.match(key);
  if (hit) { const t = await hit.text(); TR.set(text, t); return t; }
  if (!env || !env.AI) return "";
  try {
    const r = await env.AI.run(AI_MODEL, {
      messages: [{ role: "system", content: AI_PROMPT }, { role: "user", content: text }],
      max_tokens: 120,
    });
    let roman = String((r && (r.response || (r.choices && r.choices[0] && r.choices[0].message && r.choices[0].message.content))) || "").split("\n")[0].trim().replace(/^["'“”]+|["'“”]+$/g, "");
    if (!roman || /[\u0600-\u06FF]/.test(roman)) return "";
    TR.set(text, roman);
    await cache.put(key, new Response(roman, { headers: { "cache-control": "max-age=604800" } }));
    return roman;
  } catch (e) {
    return "";
  }
}

async function build(env, cache) {
  const lists = await Promise.all(FEEDS.map(([s, u]) => feed(s, u)));
  const all = lists.flat().sort((a, b) => b.ts - a.ts);
  const seen = new Set();
  const news = [];
  for (const n of all) {
    const k = n.title.toLowerCase().slice(0, 60);
    if (seen.has(k)) continue;
    seen.add(k);
    news.push(n);
    if (news.length >= KEEP) break;
  }
  // robot (monitor.json) ki translation pehle; nayi khabar ko Cloudflare AI se
  let known = {};
  try {
    const m = await (await fetch(MONITOR, { cf: { cacheTtl: 120 } })).json();
    for (const x of m.news || []) if (x.ur) known[x.title] = x.ur;
  } catch (e) {}
  await Promise.all(news.map(async (n) => {
    n.t = pkTime(n.ts);
    n.ur = known[n.title] || (await romanUr(n.title, env, cache));
  }));
  return { updated: pkTime(Date.now() / 1000), news };
}

export default {
  async fetch(req, env, ctx) {
    if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
    const url = new URL(req.url);
    if (url.pathname !== "/news" && url.pathname !== "/") {
      return new Response('{"error":"not found"}', { status: 404, headers: CORS });
    }
    const headers = { ...CORS, "cache-control": "public, max-age=30" };
    if (MEM.body && Date.now() - MEM.at < CACHE_SEC * 1000) return new Response(MEM.body, { headers });
    const cache = caches.default;
    const key = new Request("https://cache.local/news-v2");
    let res = await cache.match(key);
    if (res) {
      const body = await res.text();
      MEM = { at: Date.now(), body };
      return new Response(body, { headers });
    }
    const body = JSON.stringify(await build(env, cache));
    MEM = { at: Date.now(), body };
    ctx.waitUntil(cache.put(key, new Response(body, { headers: { ...CORS, "cache-control": "public, max-age=" + CACHE_SEC } })));
    return new Response(body, { headers });
  },
};
