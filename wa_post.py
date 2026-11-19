"""Daddy Trader — signals ko WhatsApp channel par bhejna (Whapi.Cloud ke zariye).

signals.py naya signal ya TP/SL nateeja `.wa_events.json` mein likhta hai.
Ye script unhein channel par post karti hai. WhatsApp par SIRF likha hua
msg jaata hai (Entry / Stop loss / Take profit) — koi card/tasveer nahi.
Card (tasveer, signal_card.py se) sirf Facebook page par jaata hai
(fb_post.py, FB_PAGE_TOKEN ho to), us ke neeche sirf link.
WhatsApp wale msg ke neeche bhi link (website, Facebook, TikTok). Link links.py mein hain.

GitHub Secrets (Settings -> Secrets -> Actions):
  WHAPI_TOKEN    Whapi.Cloud ka token (zaroori)
  WA_CHANNEL_ID  channel ki ID (na ho to DADDY TRADER channel)
  WA_NOTIFY_TO   jin numbers par signal ki copy jaye, comma se alag (na ho to Ali ka apna number)
Token na ho to script chup chaap kuch nahi karti, baqi bot chalta rehta hai.
"""
import json, os, sys, time, urllib.request, urllib.error

import links

API = "https://gate.whapi.cloud"
TOKEN = os.environ.get("WHAPI_TOKEN", "").strip()
# "DADDY TRADER" channel (maalik: 0347 0713257)
CHANNEL = os.environ.get("WA_CHANNEL_ID", "").strip() or "120363435117880289@newsletter"
NOTIFY = [n.strip().lstrip("+") for n in (os.environ.get("WA_NOTIFY_TO", "").strip() or "923470713257").split(",") if n.strip()]
EVENTS = ".wa_events.json"


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": "Bearer " + TOKEN,
        # Whapi ke aage Cloudflare hai: Python ka default naam (Python-urllib) wahan block hota hai (Error 1010)
        "user-agent": "Mozilla/5.0 (compatible; DaddyTraderBot/1.0; +https://daddytrader.live)",
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read() or b"{}")


def find_channel():
    """Jora hua number jis channel ka maalik/admin hai, us ki ID."""
    res = call("GET", "/newsletters?count=100")
    items = res.get("newsletters") if isinstance(res, dict) else res
    items = items or []
    # sirf wahi channel jis ka maalik/admin ye number ho — kisi aur ke channel par kabhi nahi
    own = [n for n in items if str(n.get("role", "")).lower() in ("owner", "admin")]
    return own[0].get("id") if own else ""


def money(v):
    try:
        return "{:,.2f}".format(float(v))
    except Exception:
        return str(v)


def pair(p):
    p = str(p or "XAUUSD").upper()
    return p[:3] + "/" + p[3:] if len(p) == 6 else p


def rr(s):
    try:
        e, sl, tp = float(s["entry"]), float(s["sl"]), float(s["tp"])
        return "1:{:g}".format(round(abs(tp - e) / abs(e - sl), 1))
    except Exception:
        return ""


def text(ev, platform="whatsapp"):
    s, k = ev["sig"], ev["kind"]
    p, t = pair(s.get("pair")), str(s.get("type", "")).upper()
    if k == "new":
        icon = "🟢" if t == "BUY" else "🔴"
        lines = [
            "{} *{} {}* — Daddy Trader Signal".format(icon, p, t),
            "",
            "Entry: *{}*".format(money(s.get("entry"))),
            "Stop loss: {}".format(money(s.get("sl"))),
            "Take profit: {}".format(money(s.get("tp"))),
        ]
        if rr(s):
            lines.append("Risk : reward {}".format(rr(s)))
        lines.append("📌 Move SL to breakeven after 100 pips")
        if s.get("date"):
            lines += ["", "🕒 " + str(s["date"])]
    elif k == "tp":
        lines = [
            "✅ *TP HIT — {} {}*".format(p, t),
            "",
            "Entry {} → Take profit {}".format(money(s.get("entry"), ), money(s.get("tp"))),
        ]
        if rr(s):
            lines.append("Target {} poora hua".format(rr(s)))
        if s.get("date"):
            lines.append("Signal: " + str(s["date"]))
    else:
        lines = [
            "❌ *SL HIT — {} {}*".format(p, t),
            "",
            "Entry {} → Stop loss {}".format(money(s.get("entry")), money(s.get("sl"))),
        ]
        if s.get("date"):
            lines.append("Signal: " + str(s["date"]))
    lines += ["", links.footer(platform)]
    return "\n".join(lines)


def card(ev):
    """Signal / TP HIT / SL HIT ka card (PNG bytes); na bane to None."""
    try:
        import signal_card
        return signal_card.make(ev["sig"], ev.get("kind", "new"))
    except Exception as e:
        print("card nahi bana", e)
        return None


def send(to, ev):
    """WhatsApp par sirf likha hua msg — koi card/tasveer nahi."""
    who = "channel" if to == CHANNEL else "number"
    try:
        call("POST", "/messages/text", {"to": to, "body": text(ev)})
        print("whatsapp: posted", ev["kind"], "->", who)
    except urllib.error.HTTPError as e:
        print("whatsapp: error", e.code, e.read()[:300])
    except Exception as e:
        print("whatsapp: error", e)


def main():
    if not os.path.exists(EVENTS):
        return
    try:
        events = json.load(open(EVENTS))
    except Exception:
        events = []
    os.remove(EVENTS)
    try:
        import fb_post
    except Exception as e:
        print("facebook: fb_post.py load nahi hua", e)
        fb_post = None
    fb = bool(fb_post and fb_post.TOKEN)
    if not events or (not TOKEN and not fb):
        print("whatsapp/facebook: token nahi ya koi event nahi — skip")
        return
    global CHANNEL
    try:
        if not CHANNEL:
            CHANNEL = find_channel()
            print("whatsapp: channel id", CHANNEL or "(nahi mili)")
    except Exception as e:
        print("whatsapp: channel dhoondne mein error", e)
    # pehle channel, phir Ali ke apne number par copy
    targets = ([CHANNEL] if CHANNEL else []) + [n + "@s.whatsapp.net" for n in NOTIFY if n.isdigit()]
    if not TOKEN:
        targets = []
    first = True
    for ev in events:
        # card sirf Facebook ke liye banta hai; WhatsApp par sirf likha hua msg jaata hai
        png = card(ev) if fb else None
        if fb:
            # card par signal likha hai: neeche sirf link; card na bane to poori likhai + link
            fb_post.post(png, links.footer("facebook") if png else text(ev, "facebook"))
        for to in targets:
            if not first:
                time.sleep(15)  # WhatsApp spam se bachne ke liye faasla
            first = False
            send(to, ev)


if __name__ == "__main__":
    main()
    sys.exit(0)
