"""Daddy Trader — signals ko WhatsApp channel par bhejna (Whapi.Cloud ke zariye).

signals.py naya signal ya TP/SL nateeja `.wa_events.json` mein likhta hai.
Ye script unhein channel par post karti hai.

GitHub Secrets (Settings -> Secrets -> Actions):
  WHAPI_TOKEN    Whapi.Cloud ka token (zaroori)
  WA_CHANNEL_ID  channel ki ID, jaise 120363xxxxxxxxxx@newsletter (na ho to khud dhoond leti hai)
  WA_NOTIFY_TO   jin numbers par signal ki copy jaye, comma se alag (na ho to Ali ka apna number)
Token na ho to script chup chaap kuch nahi karti, baqi bot chalta rehta hai.
"""
import json, os, sys, time, urllib.request, urllib.error

API = "https://gate.whapi.cloud"
TOKEN = os.environ.get("WHAPI_TOKEN", "").strip()
CHANNEL = os.environ.get("WA_CHANNEL_ID", "").strip()
NOTIFY = [n.strip().lstrip("+") for n in (os.environ.get("WA_NOTIFY_TO", "").strip() or "923470713257").split(",") if n.strip()]
EVENTS = ".wa_events.json"


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": "Bearer " + TOKEN,
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def find_channel():
    """Jora hua number jis channel ka maalik/admin hai, us ki ID."""
    res = call("GET", "/newsletters?count=100")
    items = res.get("newsletters") if isinstance(res, dict) else res
    items = items or []
    own = [n for n in items if str(n.get("role", "")).lower() in ("owner", "admin")]
    pick = (own or items or [None])[0]
    return pick.get("id") if pick else ""


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


def text(ev):
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
        if s.get("note"):
            lines += ["", str(s["note"])]
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
    lines += ["", "Live: https://daddytrader.live", "⚠️ Sirf taleem ke liye, financial advice nahi."]
    return "\n".join(lines)


def main():
    if not os.path.exists(EVENTS):
        return
    try:
        events = json.load(open(EVENTS))
    except Exception:
        events = []
    os.remove(EVENTS)
    if not TOKEN or not events:
        print("whatsapp: token nahi ya koi event nahi — skip")
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
    first = True
    for ev in events:
        for to in targets:
            if not first:
                time.sleep(15)  # WhatsApp spam se bachne ke liye faasla
            first = False
            try:
                call("POST", "/messages/text", {"to": to, "body": text(ev)})
                print("whatsapp: posted", ev["kind"], "->", "channel" if to == CHANNEL else "number")
            except urllib.error.HTTPError as e:
                print("whatsapp: error", e.code, e.read()[:300])
            except Exception as e:
                print("whatsapp: error", e)


if __name__ == "__main__":
    main()
    sys.exit(0)
