# Daddy Trader — Gold Market Monitor data collector
# Runs every 15 min via GitHub Actions. Writes monitor.json (deep market data, no API keys).
import json, re, urllib.request, urllib.error, datetime, email.utils
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

# ---------- 0. Gold — ASLI XAUUSD spot (Twelve Data) ----------
markets, gold = [], None
import os
TD_KEY = os.environ.get("TD_KEY", "").strip()
if TD_KEY:
    try:
        td = json.loads(get("https://api.twelvedata.com/time_series?symbol=XAU/USD"
                            "&interval=15min&outputsize=96&timezone=UTC&apikey=" + TD_KEY))
        vals = (td.get("values") or [])[::-1]
        if vals:
            closes = [float(v["close"]) for v in vals]
            highs = [float(v["high"]) for v in vals]
            lows = [float(v["low"]) for v in vals]
            c = closes[-1]
            o = float(vals[0]["open"])
            chg = round((c - o) / o * 100, 2) if o else 0.0
            gold = {"price": round(c, 2), "open": round(o, 2),
                    "high": round(max(highs), 2), "low": round(min(lows), 2),
                    "chg": chg, "src": "XAUUSD Spot",
                    "spark": [round(x, 2) for x in closes[-48:]]}
    except Exception as e:
        errs.append("td: %s" % e)

# ---------- 1. Markets — Yahoo Finance (silver, DXY, oil, yields, FX) ----------
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

if gold is not None and not gold.get("spark"):
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
KEY = re.compile(r"gold|xau|silver|precious|bullion|fed|fomc|powell|us dollar|u\.s\. dollar|usd|greenback|dxy|"
                 r"inflation|cpi|ppi|nfp|payroll|jobs report|rate cut|rate hike|"
                 r"yield|treasury|safe.haven|tariff|geopolit|iran|non-farm", re.I)
# sab se tez pehle: investingLive (pehle ForexLive) aur Federal Reserve ki apni feed
FEEDS = [("investingLive", "https://investinglive.com/feed"),
         ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_monetary.xml"),
         ("FXStreet", "https://www.fxstreet.com/rss/news"),
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

# ---------- 4d. Article bodies — news.html reader ke liye ----------
# Bot har news item ka poora article text utha ke monitor.json me likhta
# hai, taake viewer site pe hi article parh sake (external site pe jaane
# ki zaroorat nahi). Investing.com bot ko 403 deta hai (aur uski RSS me
# summary bhi nahi hoti) — un items ka sirf title milega, poora text nahi.
# Pichli run ki bodies link se reuse hoti hain (har dafa dobara fetch nahi).
from html.parser import HTMLParser as _HP

class _ArtParser(_HP):
    SKIP = {"script", "style", "nav", "header", "footer", "aside", "noscript", "form", "button", "svg"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.article_depth = 0
        self.main_depth = 0
        self.skip_depth = 0
        self.in_p = False
        self.in_content = False
        self.buf = []
        self.paras = []
    def handle_starttag(self, tag, attrs):
        if tag == "article": self.article_depth += 1
        elif tag == "main": self.main_depth += 1
        if tag in self.SKIP: self.skip_depth += 1
        if tag == "p" and self.skip_depth == 0:
            self.in_p = True
            self.in_content = self.article_depth > 0 or self.main_depth > 0
            self.buf = []
    def handle_endtag(self, tag):
        if tag == "article": self.article_depth = max(0, self.article_depth - 1)
        elif tag == "main": self.main_depth = max(0, self.main_depth - 1)
        if tag in self.SKIP: self.skip_depth = max(0, self.skip_depth - 1)
        if tag == "p" and self.in_p:
            self.in_p = False
            t = " ".join("".join(self.buf).split())
            if t:
                self.paras.append((t, self.in_content))
    def handle_data(self, data):
        if self.in_p and self.skip_depth == 0:
            self.buf.append(data)

_ART_JUNK = re.compile(r"cookie|subscribe|sign up|sign in|newsletter|advertisement|read more|follow us|share this|all rights reserved|terms of (use|service)|privacy policy|download the app|discover more insights", re.I)

def _article_paras(html_text):
    p = _ArtParser()
    try:
        p.feed(html_text)
    except Exception:
        return []
    paras = p.paras
    if any(c for _, c in paras):
        paras = [(t, c) for t, c in paras if c]
    out, seen = [], set()
    for t, _ in paras:
        if len(t) < 60:
            continue
        if _ART_JUNK.search(t):
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t[:1200])
        if len(out) >= 14:
            break
    return out

def _fetch_body(link):
    try:
        raw = get(link, t=8)
        html_text = raw.decode("utf-8", "ignore")
        if "Just a moment" in html_text[:2000] or "Attention Required" in html_text[:2000]:
            return None
        return _article_paras(html_text) or None
    except Exception:
        return None

_prev_bodies = {}
try:
    with open("monitor.json") as _fh:
        for _n in (json.load(_fh).get("news") or []):
            if _n.get("link") and _n.get("body"):
                _prev_bodies[_n["link"]] = _n["body"]
except Exception:
    pass
_new_fetch = 0
_no_body = 0
for _n in out["news"]:
    _link = _n.get("link") or ""
    if _link in _prev_bodies:
        _n["body"] = _prev_bodies[_link]
        continue
    if _new_fetch >= 8:
        _no_body += 1
        continue
    _new_fetch += 1
    _body = _fetch_body(_link)
    if _body:
        _n["body"] = _body
    else:
        _no_body += 1
if _no_body:
    errs.append("article: %d/%d no body" % (_no_body, len(out["news"])))

# ---------- 4c. ForexFactory latest posts (Tweets section) ----------
# X ka apna widget khaali aata hai (syndication endpoint 0 bytes) aur saare X
# mirrors band hain, is liye bot ForexFactory ki apni RSS se unki latest posts
# (wohi headlines jo wo X pe tweet karte hain) monitor.json me likhta hai.
# Page inhe news card jaisi card bana ke Tweets section me dikhata hai.
# Koi workflow change nahi chahiye: signals.yml pehle se monitor.py chalata
# hai aur monitor.json commit karta hai, har 15 minute.
tweets = []
for _ff_url in ("https://www.forexfactory.com/rss",
                "https://www.forexfactory.com/news/rss"):
    try:
        root = ET.fromstring(get(_ff_url))
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
            if not title or not link:
                continue
            if (NOW - ts).total_seconds() > 96 * 3600:
                continue
            tweets.append({"ts": ts.timestamp(), "title": title[:170],
                           "src": "ForexFactory", "link": link})
        tweets.sort(key=lambda x: -x["ts"])
        tweets = tweets[:6]
        break
    except Exception as e:
        errs.append("ff-tweets %s: %s" % (_ff_url, e))
        tweets = []
if not tweets:
    # ForexFactory ki apni RSS Cloudflare se band hai (runner ko bhi HTML
    # challenge page milta hai, XML nahi), is liye Google News se unki
    # recent stories lo — wohi headlines jo wo X pe tweet karte hain.
    try:
        root = ET.fromstring(get("https://news.google.com/rss/search?q=site:forexfactory.com&hl=en-US&gl=US&ceid=US:en"))
        seen_g = set()
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            if title.endswith(" - Forex Factory"):
                title = title[:-len(" - Forex Factory")].strip()
            link = (item.findtext("link") or "").strip()
            src_el = item.find("source")
            src = (src_el.text or "").strip() if src_el is not None else ""
            pub = item.findtext("pubDate") or ""
            try:
                ts = email.utils.parsedate_to_datetime(pub)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=datetime.timezone.utc)
            except Exception:
                ts = NOW
            if not title or not link or src != "Forex Factory":
                continue
            if (NOW - ts).total_seconds() > 96 * 3600:
                continue
            # forum/index pages nahi chahiye (News/Calendar page, "Gold with
            # No Drama | Page 5139" jaisi thread, "USD/JPY" jaisa pair thread)
            if title in ("News", "Calendar"):
                continue
            if re.search(r"\| Page \d+", title):
                continue
            if re.match(r"^[A-Z]{3}/[A-Z]{3}$", title):
                continue
            kk = title.lower()[:60]
            if kk in seen_g:
                continue
            seen_g.add(kk)
            tweets.append({"ts": ts.timestamp(), "title": title[:170],
                           "src": "ForexFactory", "link": link})
        tweets.sort(key=lambda x: -x["ts"])
        tweets = tweets[:6]
    except Exception as e:
        errs.append("ff-tweets google-news: %s" % e)
        tweets = []
if not tweets:
    # fetch fail ho tou pichli dafa wali posts rakho, section khaali na ho
    try:
        with open("monitor.json") as fh:
            tweets = (json.load(fh).get("tweets") or [])[:6]
    except Exception:
        tweets = []
out["tweets"] = tweets

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
