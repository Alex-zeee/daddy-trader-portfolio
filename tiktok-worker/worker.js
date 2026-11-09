// Daddy Trader - TikTok robot (Cloudflare Worker: daddytrader-tiktok)
//
// GitHub ka signal robot naya card yahan bhejta hai, ye worker use TikTok par photo post karta hai.
//   /login     TikTok account jodna (QR code se login) -> daddytrader.live/tiktok-callback.html
//   /exchange  callback page ka code le kar TikTok chabi (token) KV mein rakhta hai
//   /post      GitHub robot (sirf Alex-zeee/daddy-trader-portfolio, GitHub OIDC se pehchan) card bhejta hai
//   /img/...   TikTok yahin se tasveer uthata hai (2 ghante baad khud mit jati hai)
// Bindings: TT (KV namespace). Secrets: TT_CLIENT_KEY, TT_CLIENT_SECRET. Var (ikhtiyari): TT_PRIVACY
// TikTok approval se pehle har post sirf "SELF_ONLY" (private) hoti hai; approval ke baad TT_PRIVACY = PUBLIC_TO_EVERYONE.

const SELF = "https://daddytrader-tiktok.blankweb1.workers.dev";
const REDIRECT = "https://daddytrader.live/tiktok-callback.html";
const SITE = "https://daddytrader.live";
const REPO = "Alex-zeee/daddy-trader-portfolio";
const AUD = "daddytrader-tiktok";
const API = "https://open.tiktokapis.com/v2";
const SCOPES = "user.info.basic,video.publish,video.upload";
// TikTok "URL prefix" verification files for this worker (name -> content)
const VERIFY = {
  "tiktokBfl0If8iS3moI4Xh7n2rTSMOEOePwDhQ.txt": "tiktok-developers-site-verification=Bfl0If8iS3moI4Xh7n2rTSMOEOePwDhQ", // sandbox
};

function json(obj, status, extra) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: { "content-type": "application/json; charset=utf-8", ...(extra || {}) },
  });
}
const CORS = {
  "access-control-allow-origin": SITE,
  "access-control-allow-methods": "POST, OPTIONS",
  "access-control-allow-headers": "content-type",
};

const KEY = (env) => String(env.TT_CLIENT_KEY || "").trim();
const SECRET = (env) => String(env.TT_CLIENT_SECRET || "").trim();

async function tokenCall(env, params) {
  const body = new URLSearchParams({ client_key: KEY(env), client_secret: SECRET(env), ...params });
  const r = await fetch(API + "/oauth/token/", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded", "cache-control": "no-cache" },
    body,
  });
  const d = await r.json();
  if (!d.access_token) throw new Error("token: " + JSON.stringify(d).slice(0, 300));
  const now = Date.now();
  const tok = {
    access_token: d.access_token,
    refresh_token: d.refresh_token,
    open_id: d.open_id,
    scope: d.scope,
    expires_at: now + (Number(d.expires_in || 86400) - 300) * 1000,
    refresh_expires_at: now + Number(d.refresh_expires_in || 0) * 1000,
  };
  await env.TT.put("tok", JSON.stringify(tok));
  return tok;
}

async function accessToken(env) {
  const tok = JSON.parse((await env.TT.get("tok")) || "null");
  if (!tok) throw new Error("TikTok abhi juda nahi - pehle " + SELF + "/login");
  if (Date.now() < tok.expires_at) return tok.access_token;
  return (await tokenCall(env, { grant_type: "refresh_token", refresh_token: tok.refresh_token })).access_token;
}

async function tt(env, path, body, method) {
  const at = await accessToken(env);
  const r = await fetch(API + path, {
    method: method || "POST",
    headers: { authorization: "Bearer " + at, "content-type": "application/json; charset=UTF-8" },
    body: method === "GET" ? undefined : JSON.stringify(body || {}),
  });
  return r.json();
}

function b64(s) {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  return Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
}

// Sirf apna GitHub robot: GitHub Actions ka OIDC token (koi password nahi chahiye)
async function fromOurGitHub(req) {
  try {
    const jwt = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
    const [h, p, s] = jwt.split(".");
    if (!s) return false;
    const head = JSON.parse(new TextDecoder().decode(b64(h)));
    const pay = JSON.parse(new TextDecoder().decode(b64(p)));
    if (pay.iss !== "https://token.actions.githubusercontent.com") return false;
    if (pay.aud !== AUD || String(pay.repository).toLowerCase() !== REPO.toLowerCase()) return false;
    if (!pay.exp || pay.exp * 1000 < Date.now()) return false;
    const jwks = await (await fetch("https://token.actions.githubusercontent.com/.well-known/jwks", { cf: { cacheTtl: 3600 } })).json();
    const k = (jwks.keys || []).find((x) => x.kid === head.kid);
    if (!k) return false;
    const key = await crypto.subtle.importKey(
      "jwk", { kty: k.kty, n: k.n, e: k.e, alg: "RS256", ext: true },
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    return await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, b64(s), new TextEncoder().encode(h + "." + p));
  } catch (e) {
    return false;
  }
}

async function post(env, b) {
  const urls = [];
  for (const im of (b.images || []).slice(0, 35)) {
    const id = crypto.randomUUID().replace(/-/g, "");
    await env.TT.put("img:" + id, b64(im), { expirationTtl: 7200 });
    urls.push(SELF + "/img/" + id + ".jpg");
  }
  if (!urls.length) return { ok: false, error: "koi tasveer nahi" };
  const ci = await tt(env, "/post/publish/creator_info/query/", {});
  const opts = (ci.data && ci.data.privacy_level_options) || [];
  const want = env.TT_PRIVACY || "SELF_ONLY";
  const privacy = opts.includes(want) ? want : opts.includes("SELF_ONLY") ? "SELF_ONLY" : opts[0] || "SELF_ONLY";
  const init = await tt(env, "/post/publish/content/init/", {
    post_info: {
      title: String(b.title || "").slice(0, 90),
      description: String(b.description || "").slice(0, 4000),
      disable_comment: false,
      privacy_level: privacy,
      auto_add_music: true,
    },
    source_info: { source: "PULL_FROM_URL", photo_cover_index: 0, photo_images: urls },
    post_mode: "DIRECT_POST",
    media_type: "PHOTO",
  });
  const ok = !!(init.error && init.error.code === "ok");
  return { ok, publish_id: init.data && init.data.publish_id, privacy, error: ok ? undefined : init.error || ci.error };
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    const path = url.pathname;
    if (VERIFY[path.slice(1)]) return new Response(VERIFY[path.slice(1)], { headers: { "content-type": "text/plain" } });

    if (path.startsWith("/img/")) {
      const id = path.slice(5).replace(/\.jpg$/, "");
      const v = await env.TT.get("img:" + id, "arrayBuffer");
      if (!v) return new Response("not found", { status: 404 });
      return new Response(v, { headers: { "content-type": "image/jpeg", "cache-control": "public, max-age=3600" } });
    }

    if (path === "/login") {
      const state = crypto.randomUUID();
      await env.TT.put("state:" + state, "1", { expirationTtl: 900 });
      const q = new URLSearchParams({ client_key: KEY(env), scope: SCOPES, response_type: "code", redirect_uri: REDIRECT, state });
      return Response.redirect("https://www.tiktok.com/v2/auth/authorize/?" + q.toString(), 302);
    }

    if (path === "/exchange") {
      if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
      try {
        const b = await req.json();
        if (!b.state || !(await env.TT.get("state:" + b.state))) return json({ ok: false, error: "purana ya ghalat link - dobara /login kholein" }, 400, CORS);
        await env.TT.delete("state:" + b.state);
        const tok = await tokenCall(env, { code: b.code, grant_type: "authorization_code", redirect_uri: REDIRECT });
        let name = "";
        try {
          const u = await tt(env, "/user/info/?fields=open_id,display_name", null, "GET");
          name = (u.data && u.data.user && u.data.user.display_name) || "";
        } catch (e) {}
        return json({ ok: true, name, scope: tok.scope }, 200, CORS);
      } catch (e) {
        return json({ ok: false, error: String(e.message || e).slice(0, 300) }, 500, CORS);
      }
    }

    if (path === "/post" && req.method === "POST") {
      if (!(await fromOurGitHub(req))) return json({ ok: false, error: "not allowed" }, 403);
      try {
        return json(await post(env, await req.json()));
      } catch (e) {
        return json({ ok: false, error: String(e.message || e).slice(0, 300) }, 500);
      }
    }

    if (path === "/status" && req.method === "POST") {
      if (!(await fromOurGitHub(req))) return json({ ok: false, error: "not allowed" }, 403);
      const b = await req.json();
      return json(await tt(env, "/post/publish/status/fetch/", { publish_id: b.publish_id }));
    }

    if (path === "/check") {
      // sirf lambai batata hai, chabi kabhi nahi dikhata
      const k = String(env.TT_CLIENT_KEY || ""), c = String(env.TT_CLIENT_SECRET || "");
      const info = (v) => ({ length: v.trim().length, extra_spaces: v.length !== v.trim().length, dots: /[\u2022*]/.test(v) });
      return json({ client_key: info(k), client_secret: info(c) });
    }

    if (path === "/") {
      const tok = JSON.parse((await env.TT.get("tok")) || "null");
      return new Response(
        "Daddy Trader TikTok robot\n" +
          (tok ? "TikTok juda hua hai. Chabi " + new Date(tok.refresh_expires_at).toISOString().slice(0, 10) + " tak.\n"
               : "TikTok abhi juda nahi. Jodne ke liye: " + SELF + "/login\n"),
        { headers: { "content-type": "text/plain; charset=utf-8" } });
    }
    return new Response("not found", { status: 404 });
  },
};
