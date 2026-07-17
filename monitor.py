# Daddy Trader — Gold Market Monitor data collector
# Runs every 15 min via GitHub Actions. Writes monitor.json (deep market data, no API keys).
import json, re, urllib.request, datetime, email.utils
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "Accept": "*/*"}

def get(url, t=20):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=t).read()

PKT = datetime.timezone(datetime.timedelta(hours=5))
NOW = datetime.datetime.now(datetime.timezone.utc)
errs = []
out = {"updated": NOW.astimezone(PKT).strftime("%d-%m-%Y %H:%M PKT")}

# ---------- 1. Markets — Yahoo Finance (silver, DXY, oil, yields, FX) ----------
markets, gold = [], None
TICKS = [("SI=F", "Silver (fut)"), ("DX-Y.NYB", "Dollar Index"),
         ("CL=F", "Oil WTI"), ("^TNX", "US 10Y Yield"),
         ("EURUSD=X", "EUR/USD"), ("GBPUSD=X", "GBP/USD"), ("JPY=X", "USD/JPY")]
try:
    import yfinance as yf
    df = yf.download([s for s, _ in TICKS], period="1mo", interval="1d",
                     progress=False, group_by="ticker", threads=True)
    for sym, name in TICKS:
        try:
            closes = df[sym]["Close"].dropna()
            if len(closes) == 0:
                continue
            vals = [float(x) for x in closes.tolist()][-22:]
            if sym == "^TNX" and vals[-1] > 20:  # kabhi 45.7 (x10) format aata hai
                vals = [v / 10.0 for v in vals]
            c = vals[-1]
            prev = vals[-2] if len(vals) > 1 else c
            chg = round((c - prev) / prev * 100, 2) if prev else 0.0
            markets.append({"name": name, "price": round(c, 4), "chg": chg,
                            "spark": [round(v, 4) for v in vals]})
        except Exception:
            continue
except Exception as e:
    errs.append("yf: %s" % e)

# ---------- 2. Crypto (Kraken) + PAXG gold fallback ----------
try:
    k = json.loads(get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD,ETHUSD,PAXGUSD"))
    for key, v in (k.get("result") or {}).items():
        if key == "last":
            continue
        c, o = float(v["c"][0]), float(v["o"])
        chg = round((c - o) / o * 100, 2) if o else 0.0
        if "PAXG" in key:
            if gold is None:
                gold = {"price": c, "open": o, "high": float(v["h"][1]),
                        "low": float(v["l"][1]), "chg": chg, "src": "PAXG (Kraken)"}
        elif "XBT" in key:
            markets.append({"name": "Bitcoin", "price": c, "chg": chg})
        elif "ETH" in key:
            markets.append({"name": "Ethereum", "price": c, "chg": chg})
except Exception as e:
    errs.append("kraken: %s" % e)

# sparklines for gold/crypto (Kraken hourly closes, last 48h)
def _kspark(pair):
    try:
        o = json.loads(get("https://api.kraken.com/0/public/OHLC?pair=%s&interval=60" % pair))
        res = o.get("result") or {}
        key = next((k for k in res if k != "last"), None)
        return [round(float(r[4]), 2) for r in res[key][-48:]] if key else []
    except Exception:
        return []

if gold is not None:
    gold["spark"] = _kspark("PAXGUSD")
for m in markets:
    if m["name"] == "Bitcoin":
        m["spark"] = _kspark("XBTUSD")
    elif m["name"] == "Ethereum":
        m["spark"] = _kspark("ETHUSD")

out["gold"] = gold
out["markets"] = markets

# ---------- 3. USD Economic Calendar (ForexFactory public JSON) ----------
allev, upcoming = [], []
for wk in ("thisweek", "nextweek"):
    try:
        data = json.loads(get("https://nfs.faireconomy.media/ff_calendar_%s.json?version=1" % wk))
        for ev in data:
            if ev.get("country") != "USD" or ev.get("impact") not in ("High", "Medium"):
                continue
            try:
                ts = datetime.datetime.fromisoformat(ev["date"])
            except Exception:
                continue
            row = {"ts": ts.timestamp(),
                   "t": ts.astimezone(PKT).strftime("%a %d %b · %I:%M %p"),
                   "title": str(ev.get("title", ""))[:80],
                   "impact": ev.get("impact"),
                   "forecast": str(ev.get("forecast") or ""),
                   "previous": str(ev.get("previous") or "")}
            allev.append(row)
            if ts > NOW - datetime.timedelta(hours=3):
                upcoming.append(row)
    except Exception as e:
        if wk == "thisweek":
            errs.append("cal-%s: %s" % (wk, e))
allev.sort(key=lambda x: x["ts"])
upcoming.sort(key=lambda x: x["ts"])
# weekend pe upcoming khali ho tou hafte ke aakhri events dikhao
out["calendar"] = upcoming[:10] if upcoming else allev[-6:]
out["cal_mode"] = "upcoming" if upcoming else "past"

# ---------- 4. Gold-related news (free RSS feeds, keyword filtered) ----------
KEY = re.compile(r"gold|xau|silver|precious|bullion|fed|fomc|powell|dollar|dxy|"
                 r"inflation|cpi|ppi|nfp|payroll|jobs report|rate cut|rate hike|"
                 r"yield|treasury|safe.haven", re.I)
FEEDS = [("FXStreet", "https://www.fxstreet.com/rss/news"),
         ("Investing.com", "https://www.investing.com/rss/news_11.rss"),
         ("CNBC", "https://www.cnbc.com/id/20910258/device/rss/rss.html")]
news = []
for src, url in FEEDS:
    try:
        root = ET.fromstring(get(url))
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = item.findtext("pubDate") or ""
            try:
                ts = email.utils.parsedate_to_datetime(pub)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=datetime.timezone.utc)
            except Exception:
                ts = NOW
            if not title or not KEY.search(title):
                continue
            if (NOW - ts).total_seconds() > 96 * 3600:
                continue
            news.append({"ts": ts.timestamp(), "title": title[:170], "src": src,
                         "link": link,
                         "t": ts.astimezone(PKT).strftime("%d %b · %I:%M %p")})
    except Exception as e:
        errs.append("%s: %s" % (src, e))
news.sort(key=lambda x: -x["ts"])
seen, ded = set(), []
for n in news:
    kk = n["title"].lower()[:60]
    if kk in seen:
        continue
    seen.add(kk)
    ded.append(n)
out["news"] = ded[:10]

# ---------- 4b. Roman Urdu translation (Google gtx, free) ----------
import urllib.parse

def roman_ur(text):
    try:
        u = ("https://translate.googleapis.com/translate_a/single"
             "?client=gtx&sl=en&tl=ur&dt=t&dt=rm&q=" + urllib.parse.quote(text))
        data = json.loads(get(u, t=12))
        roman, urdu = "", ""
        for s in (data[0] or []):
            if not isinstance(s, list):
                continue
            if s and isinstance(s[0], str):
                urdu += s[0]
            # romanization entries: first element None, roman text at idx 2 ya 3
            for idx in (2, 3):
                if len(s) > idx and s[0] is None and isinstance(s[idx], str):
                    roman += s[idx] + " "
                    break
        return roman.strip()
    except Exception:
        return ""

# pehle English idioms ko saada English banao (warna tarjuma ajeeb hota hai)
EN_SIMPLIFY = [
    (r"[Ll]ive levels", ""), (r"bear'?s eye", "bears ka target hai"),
    (r"bull'?s eye", "bulls ka target hai"), (r"\bcoils\b", "trade kar raha hai"),
    (r"\bstalls\b", "ruk gaya hai"), (r"\bpennant\b", "pattern"),
    (r"\bwipeout\b", "loss"), (r"\btestimony\b", "bayan"),
]

# phir Google ke Roman output ke mushkil/ghalat alfaz asan banao,
# trading terms wapas English mein (jaise log asal mein baat karte hain)
RO_FIX = {
    "min": "mein", "or": "aur", "se": "se", "ki": "ki",
    "qeemt": "qeemat", "qimt": "qeemat", "keemt": "qeemat", "qimat": "qeemat",
    "pition goi": "forecast", "pishin goi": "forecast", "peshin goi": "forecast",
    "paishin goi": "forecast", "pesh goi": "forecast", "pishn goi": "forecast",
    "richh": "bears", "bhalo": "bears", "bil": "bulls",
    "afrat zar": "inflation (mehngai)", "afraat zar": "inflation (mehngai)",
    "shrah sod": "interest rate", "sod ki shrah": "interest rate",
    "shrah": "rate", "sod": "interest",
    "daler": "Dollar", "dalr": "Dollar", "dallar": "Dollar",
    "amriki": "US", "amrici": "US", "amrika": "America",
    "si pi i": "CPI", "si pi ai": "CPI", "pi pi i": "PPI",
    "nchala": "neechla", "nchale": "neechle", "dhanchah": "dhancha",
    "hamayat": "support", "muzahemat": "resistance", "muzahmat": "resistance",
    "bahali": "recovery", "indah": "aainda", "aindah": "aainda",
    "taayewan": "Taiwan", "sone": "Gold (sone)", "sona": "Gold (sona)",
    "chandi": "Silver (chandi)", "khazane": "treasury", "zar mubadlah": "currency",
    "janchane": "test karne", "mtahan": "test",
    "hay": "hai", "hidaf": "target", "ahdaf": "targets",
    "balo": "bears", "belo": "bears", "bl": "bull",
    "ue es": "US", "yo es": "US", "bink": "Bank",
    "biyan": "bayan", "sharah": "rate", "izafe": "izafay",
    "kam unchi sakht": "lower high structure", "sakht": "structure",
    "woon": "Won", "koryai": "Korea ki", "janobi": "South",
    "baraamadat": "exports", "daramdat": "imports",
    "kamers bink": "Commerzbank", "mzbut": "mazboot", "kmzor": "kamzor",
    "sti": "steady", "mustehkam": "stable",
}
RO_RX = [(re.compile(r"\b" + re.escape(k) + r"\b", re.I), v) for k, v in RO_FIX.items()]

def polish(r):
    for rx, v in RO_RX:
        r = rx.sub(v, r)
    r = re.sub(r"\s+", " ", r).strip()
    return (r[:1].upper() + r[1:]) if r else r

tr_fail = 0
for n in out["news"]:
    en = n["title"]
    for pat, rep in EN_SIMPLIFY:
        en = re.sub(pat, rep, en)
    r = roman_ur(en.strip(" -:"))
    if r:
        n["ur"] = polish(r)[:220]
    else:
        tr_fail += 1
if tr_fail:
    errs.append("translate: %d/%d failed" % (tr_fail, len(out["news"])))

# ---------- 5. Risk sentiment (Fear & Greed) ----------
try:
    f = json.loads(get("https://api.alternative.me/fng/?limit=1"))
    d = f["data"][0]
    out["sentiment"] = {"value": int(d["value"]), "label": d["value_classification"]}
except Exception as e:
    errs.append("fng: %s" % e)
    out["sentiment"] = None

out["err"] = errs or None

# nayi top news aayi ho tou .new_news likho (workflow ntfy push bhejta hai)
try:
    with open("monitor.json") as fh:
        old_link = ((json.load(fh).get("news") or [{}])[0]).get("link")
except Exception:
    old_link = None
top = (out["news"] or [{}])[0]
if top.get("link") and old_link and top["link"] != old_link:
    with open(".new_news", "w") as fh:
        fh.write((top.get("ur") or top.get("title") or "")[:200])

with open("monitor.json", "w") as fh:
    json.dump(out, fh, indent=1)
print("monitor.json written | markets:%d cal:%d news:%d | errs:%s"
      % (len(markets), len(out["calendar"]), len(ded), errs))
