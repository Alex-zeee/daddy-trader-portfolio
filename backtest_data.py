"""Daddy Trader BackBar — backtest data robot.

Dukascopy ke public historical datafeed se forex, metals, indices aur oil ka
1-minute data le kar website ke data/ folder mein rakhta hai.

  data/index.json                      -> symbols ki list + kab update hua
  data/fx/<SYM>/m1/<YYYY-MM>.csv       -> 1-minute candles (aakhri ~2 mahine)
  data/fx/<SYM>/m5/<YYYY-MM>.csv       -> 5-minute candles (aakhri ~12 mahine)

CSV line: unix_seconds,open,high,low,close,volume

Chalane ka tareeqa:
  python backtest_data.py            # naya data + thora purana (har 30 min, ~40 min tak)
  python backtest_data.py --backfill # zyada der tak purana data bharo

Har run pehle har symbol ka naya data laata hai, phir waqt bache to peeche ki
taraf purana data thora thora bharta hai. Is tarah Dukascopy dheema bhi ho to
website par naya data foran aa jata hai aur purana waqt ke saath poora hota hai.
"""
import concurrent.futures as cf
import csv
import http.client
import io
import json
import lzma
import math
import os
import socket
import struct
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
FEED = "https://datafeed.dukascopy.com/datafeed"
UA = {"User-Agent": "Mozilla/5.0 (DaddyTrader BackBar data robot)"}
M1_MONTHS = 2      # kitne mahine 1-minute data rakhna hai
M5_MONTHS = 12     # kitne mahine 5-minute data rakhna hai
WORKERS = int(os.environ.get("WORKERS", "1"))  # ek waqt mein kitne downloads (Dukascopy zyada par timeout deta hai)
CHUNK_DAYS = 12    # har baari purane data ke kitne din

# code: (dukascopy id, naam, category, display decimals, andaaza price)
SYMBOLS = {
    "EURUSD": ("EURUSD", "Euro / U.S. Dollar", "forex", 5, 1.1),
    "GBPUSD": ("GBPUSD", "British Pound / U.S. Dollar", "forex", 5, 1.3),
    "USDJPY": ("USDJPY", "U.S. Dollar / Japanese Yen", "forex", 3, 150),
    "USDCHF": ("USDCHF", "U.S. Dollar / Swiss Franc", "forex", 5, 0.85),
    "AUDUSD": ("AUDUSD", "Australian Dollar / U.S. Dollar", "forex", 5, 0.65),
    "NZDUSD": ("NZDUSD", "New Zealand Dollar / U.S. Dollar", "forex", 5, 0.6),
    "USDCAD": ("USDCAD", "U.S. Dollar / Canadian Dollar", "forex", 5, 1.37),
    "EURGBP": ("EURGBP", "Euro / British Pound", "forex", 5, 0.85),
    "EURJPY": ("EURJPY", "Euro / Japanese Yen", "forex", 3, 165),
    "EURCHF": ("EURCHF", "Euro / Swiss Franc", "forex", 5, 0.94),
    "EURAUD": ("EURAUD", "Euro / Australian Dollar", "forex", 5, 1.7),
    "EURNZD": ("EURNZD", "Euro / New Zealand Dollar", "forex", 5, 1.85),
    "EURCAD": ("EURCAD", "Euro / Canadian Dollar", "forex", 5, 1.5),
    "GBPJPY": ("GBPJPY", "British Pound / Japanese Yen", "forex", 3, 195),
    "GBPCHF": ("GBPCHF", "British Pound / Swiss Franc", "forex", 5, 1.1),
    "GBPAUD": ("GBPAUD", "British Pound / Australian Dollar", "forex", 5, 2.0),
    "GBPNZD": ("GBPNZD", "British Pound / New Zealand Dollar", "forex", 5, 2.2),
    "GBPCAD": ("GBPCAD", "British Pound / Canadian Dollar", "forex", 5, 1.8),
    "AUDJPY": ("AUDJPY", "Australian Dollar / Japanese Yen", "forex", 3, 98),
    "AUDCHF": ("AUDCHF", "Australian Dollar / Swiss Franc", "forex", 5, 0.55),
    "AUDNZD": ("AUDNZD", "Australian Dollar / New Zealand Dollar", "forex", 5, 1.1),
    "AUDCAD": ("AUDCAD", "Australian Dollar / Canadian Dollar", "forex", 5, 0.9),
    "NZDJPY": ("NZDJPY", "New Zealand Dollar / Japanese Yen", "forex", 3, 88),
    "NZDCHF": ("NZDCHF", "New Zealand Dollar / Swiss Franc", "forex", 5, 0.5),
    "NZDCAD": ("NZDCAD", "New Zealand Dollar / Canadian Dollar", "forex", 5, 0.8),
    "CADJPY": ("CADJPY", "Canadian Dollar / Japanese Yen", "forex", 3, 108),
    "CADCHF": ("CADCHF", "Canadian Dollar / Swiss Franc", "forex", 5, 0.62),
    "CHFJPY": ("CHFJPY", "Swiss Franc / Japanese Yen", "forex", 3, 175),
    "XAUUSD": ("XAUUSD", "Gold Spot / U.S. Dollar", "metals", 3, 3500),
    "XAGUSD": ("XAGUSD", "Silver / U.S. Dollar", "metals", 3, 40),
    "US30": ("USA30IDXUSD", "Dow Jones Industrial Average", "indices", 1, 44000),
    "NAS100": ("USATECHIDXUSD", "Nasdaq 100", "indices", 1, 22000),
    "SPX500": ("USA500IDXUSD", "S&P 500", "indices", 1, 6000),
    "GER40": ("DEUIDXEUR", "DAX 40 (Germany)", "indices", 1, 23000),
    "UK100": ("GBRIDXGBP", "FTSE 100 (UK)", "indices", 1, 9000),
    "JP225": ("JPNIDXJPY", "Nikkei 225 (Japan)", "indices", 0, 40000),
    "WTI": ("LIGHTCMDUSD", "WTI Crude Oil", "energy", 2, 65),
    "BRENT": ("BRENTCMDUSD", "Brent Crude Oil", "energy", 2, 68),
}

ERRORS = []
LAST_ERR = {}


STATS = {"req": 0, "fail": 0, "sec": 0.0}
HOST = FEED.split("/")[2]
_orig_getaddrinfo = socket.getaddrinfo
_tls = threading.local()


def pick_server():
    """Dukascopy ke kai server address hain; kuch GitHub se jawab nahi dete.
    Har address ko test karo aur sab se tez wala pakka kar do."""
    try:
        infos = _orig_getaddrinfo(HOST, 443, socket.AF_INET, socket.SOCK_STREAM)
    except Exception as e:
        print("DNS fail:", repr(e)[:100], flush=True)
        return
    ips = list(dict.fromkeys(i[4][0] for i in infos))
    best = None
    for ip in ips:
        t0 = time.time()
        try:
            socket.create_connection((ip, 443), timeout=6).close()
            dt = time.time() - t0
            print("  server %s ok (%.2fs)" % (ip, dt), flush=True)
            if best is None or dt < best[1]:
                best = (ip, dt)
        except Exception as e:
            print("  server %s band (%s)" % (ip, type(e).__name__), flush=True)
    if best:
        ip = best[0]

        def gai(host, *a, **k):
            return _orig_getaddrinfo(ip if host == HOST else host, *a, **k)
        socket.getaddrinfo = gai
        print("Server chuna: %s" % ip, flush=True)


def _conn():
    c = getattr(_tls, "c", None)
    if c is None:
        c = http.client.HTTPSConnection(HOST, timeout=15)
        _tls.c = c
    return c


def http_get(url, tries=3):
    path = url.split(HOST, 1)[1]
    for k in range(tries):
        t0 = time.time()
        c = _conn()
        try:
            c.request("GET", path, headers=UA)
            r = c.getresponse()
            data = r.read()
            if r.status == 404:
                STATS["req"] += 1
                return b""
            if r.status != 200:
                raise IOError("HTTP %d" % r.status)
            STATS["req"] += 1
            STATS["sec"] += time.time() - t0
            return data
        except Exception as e:
            LAST_ERR["e"] = repr(e)[:150]
            try:
                c.close()
            except Exception:
                pass
            _tls.c = None
        STATS["fail"] += 1
        time.sleep(2 * (k + 1))
    ERRORS.append("download fail: %s (%s)" % (url, LAST_ERR.get("e")))
    return None


def unlzma(raw):
    if not raw:
        return b""
    try:
        return lzma.LZMADecompressor(format=lzma.FORMAT_AUTO).decompress(raw)
    except Exception:
        return b""


def day_candles(duka, day):
    """Ek UTC din ki 1-minute BID candles: list of (t, o, h, l, c, v) raw points."""
    url = "%s/%s/%04d/%02d/%02d/BID_candles_min_1.bi5" % (FEED, duka, day.year, day.month - 1, day.day)
    raw = http_get(url)
    if raw is None:
        return None
    data = unlzma(raw)
    base = int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())
    out = []
    for i in range(0, len(data) - 23, 24):
        t, o, c, lo, hi, v = struct.unpack(">IIIIIf", data[i:i + 24])
        if v <= 0:
            continue  # weekend / market band: flat candles chhor do
        out.append((base + t, o, hi, lo, c, v))
    return out


def hour_ticks_to_m1(duka, hour):
    """Ek ghante ki ticks se 1-minute BID candles."""
    url = "%s/%s/%04d/%02d/%02d/%02dh_ticks.bi5" % (FEED, duka, hour.year, hour.month - 1, hour.day, hour.hour)
    raw = http_get(url)
    if raw is None:
        return None
    data = unlzma(raw)
    base = int(hour.timestamp())
    bars = {}
    for i in range(0, len(data) - 19, 20):
        ms, ask, bid, av, bv = struct.unpack(">IIIff", data[i:i + 20])
        t = base + (ms // 1000) // 60 * 60
        b = bars.get(t)
        vol = av + bv
        if b is None:
            bars[t] = [t, bid, bid, bid, bid, vol]
        else:
            if bid > b[2]:
                b[2] = bid
            if bid < b[3]:
                b[3] = bid
            b[4] = bid
            b[5] += vol
    return [tuple(bars[k]) for k in sorted(bars)]


def scale_for(raw_bars, expect):
    """Raw points ko asal price banane wala divisor khud dhoondo (10 ki power)."""
    closes = sorted(b[4] for b in raw_bars if b[4] > 0)
    if not closes:
        return None
    med = closes[len(closes) // 2]
    p = round(math.log10(med / expect))
    return 10 ** p


def month_key(ts):
    d = datetime.fromtimestamp(ts, UTC)
    return "%04d-%02d" % (d.year, d.month)


def sym_dir(code, res):
    return os.path.join(ROOT, "fx", code, res)


def read_month(code, res, key):
    path = os.path.join(sym_dir(code, res), key + ".csv")
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return [tuple(float(x) if j else int(x) for j, x in enumerate(row)) for row in csv.reader(f) if row]


def write_month(code, res, key, bars, dec):
    os.makedirs(sym_dir(code, res), exist_ok=True)
    path = os.path.join(sym_dir(code, res), key + ".csv")
    buf = io.StringIO()
    fmt = "%d,%." + str(dec) + "f,%." + str(dec) + "f,%." + str(dec) + "f,%." + str(dec) + "f,%d\n"
    for b in bars:
        buf.write(fmt % (b[0], b[1], b[2], b[3], b[4], round(b[5])))
    with open(path, "w", newline="") as f:
        f.write(buf.getvalue())


def to_m5(m1):
    out, cur = [], None
    for t, o, h, l, c, v in m1:
        bt = t - t % 300
        if cur is None or cur[0] != bt:
            if cur:
                out.append(tuple(cur))
            cur = [bt, o, h, l, c, v]
        else:
            cur[2] = max(cur[2], h)
            cur[3] = min(cur[3], l)
            cur[4] = c
            cur[5] += v
    if cur:
        out.append(tuple(cur))
    return out


def merge(old, new):
    d = {b[0]: b for b in old}
    for b in new:
        d[b[0]] = b
    return [d[k] for k in sorted(d)]


def months_back(n, now):
    keys, y, m = [], now.year, now.month
    for _ in range(n):
        keys.append("%04d-%02d" % (y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return sorted(keys)


def load_index():
    path = os.path.join(ROOT, "index.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"updated": 0, "symbols": {}}


def save_index(idx):
    os.makedirs(ROOT, exist_ok=True)
    with open(os.path.join(ROOT, "index.json"), "w") as f:
        json.dump(idx, f, separators=(",", ":"))


class OutOfTime(Exception):
    pass


START = time.time()
BUDGET = 40 * 60


def time_left():
    return BUDGET - (time.time() - START)


def utc_day(ts_or_dt):
    d = ts_or_dt if isinstance(ts_or_dt, datetime) else datetime.fromtimestamp(ts_or_dt, UTC)
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def target_start(now):
    y, m = now.year, now.month - (M5_MONTHS - 1)
    while m <= 0:
        y, m = y - 1, m + 12
    return datetime(y, m, 1, tzinfo=UTC)


def fetch_forward(code, start, now):
    """start se ab tak (din ki files + aaj ke ghante ticks se)."""
    duka = SYMBOLS[code][0]
    raw, fails = [], 0
    today = utc_day(now)
    day = utc_day(start)

    def ticks(h0, h1):
        h = datetime(h0.year, h0.month, h0.day, h0.hour, tzinfo=UTC)
        while h < h1 and time_left() > 0:
            bars = hour_ticks_to_m1(duka, h)
            if bars:
                raw.extend(bars)
            h += timedelta(hours=1)

    while day < today and time_left() > 0:
        if day.weekday() != 5:
            bars = day_candles(duka, day)
            if bars is None:
                fails += 1
                if fails >= 6:
                    return raw, False
            elif bars:
                fails = 0
                raw.extend(bars)
            elif today - day <= timedelta(days=2):
                ticks(max(start, day), day + timedelta(days=1))
        day += timedelta(days=1)
    ticks(max(start, today), datetime(now.year, now.month, now.day, now.hour, tzinfo=UTC))
    return raw, True


def fetch_backward(code, frm, until):
    """frm (pehle se mojood sab se purana din) se peeche, CHUNK_DAYS din tak.
    Lautata hai: raw bars, naya 'from' din (jahan tak mukammal ho gaya)."""
    duka = SYMBOLS[code][0]
    raw, fails = [], 0
    oldest_ok = frm
    day = frm - timedelta(days=1)
    stop = max(until, frm - timedelta(days=CHUNK_DAYS))
    while day >= stop and time_left() > 0:
        if day.weekday() != 5:
            bars = day_candles(duka, day)
            if bars is None:
                fails += 1
                if fails >= 4:
                    break
                day -= timedelta(days=1)
                continue  # ye din chhoot gaya: 'from' isse aage nahi badhega
            if bars:
                raw.extend(bars)
        if fails == 0:
            oldest_ok = day
        day -= timedelta(days=1)
    return raw, oldest_ok


def store(code, info, raw, now):
    """raw points ko asal price bana kar month files mein jodo; info update karo."""
    duka, name, cat, dec, expect = SYMBOLS[code]
    div = info.get("div") or scale_for(raw, expect)
    if not div:
        return info
    raw.sort(key=lambda b: b[0])
    bars = [(b[0], b[1] / div, b[2] / div, b[3] / div, b[4] / div, b[5]) for b in raw]
    keep_m1 = set(months_back(M1_MONTHS, now))
    keep_m5 = set(months_back(M5_MONTHS, now))
    by_month = {}
    for b in bars:
        by_month.setdefault(month_key(b[0]), []).append(b)
    for key, mb in by_month.items():
        if key in keep_m1:
            m1 = merge(read_month(code, "m1", key), mb)
            write_month(code, "m1", key, m1, dec)
            m5 = merge(read_month(code, "m5", key), to_m5(m1))
        else:
            m5 = merge(read_month(code, "m5", key), to_m5(mb))
        if key in keep_m5:
            write_month(code, "m5", key, m5, dec)
    for res, keep in (("m1", keep_m1), ("m5", keep_m5)):
        d = sym_dir(code, res)
        if os.path.isdir(d):
            for fn in os.listdir(d):
                if fn.endswith(".csv") and fn[:-4] not in keep:
                    os.remove(os.path.join(d, fn))

    def listed(res):
        d = sym_dir(code, res)
        return sorted(fn[:-4] for fn in os.listdir(d) if fn.endswith(".csv")) if os.path.isdir(d) else []

    m5_list = listed("m5")
    if not m5_list:
        return info
    recent = []
    for key in m5_list[-2:]:
        recent.extend(read_month(code, "m5", key))
    newest = recent[-1][0]
    price = recent[-1][4]
    ago = [b for b in recent if b[0] <= newest - 86400]
    chg = round((price - ago[-1][4]) / ago[-1][4] * 100, 2) if ago and ago[-1][4] else None
    out = dict(info)
    out.update({"name": name, "cat": cat, "dec": dec, "m1": listed("m1"), "m5": m5_list,
                "last": newest, "price": round(price, dec), "chg": chg, "div": div})
    return out


def step_forward(code, info, now):
    last = info.get("last", 0)
    if last:
        start = datetime.fromtimestamp(last, UTC) - timedelta(hours=2)
    else:
        start = utc_day(now) - timedelta(days=4)  # naya symbol: pehle aakhri kuch din
    raw, ok = fetch_forward(code, start, now)
    if raw:
        info = store(code, info, raw, now)
        if "from" not in info:
            info["from"] = int(utc_day(start).timestamp())
    msg = "%d naye bars%s" % (len(raw), "" if ok else " (kuch downloads fail)")
    return info, msg


def step_backward(code, info, now):
    frm = datetime.fromtimestamp(info["from"], UTC)
    raw, oldest = fetch_backward(code, frm, target_start(now))
    if raw:
        info = store(code, info, raw, now)
    info = dict(info)
    info["from"] = int(oldest.timestamp())
    return info, "purana data ab %s se" % oldest.strftime("%Y-%m-%d")


def needs_back(info, now):
    return "from" in info and info.get("last") and info["from"] > target_start(now).timestamp()


def run_round(idx, codes, fn, now, label):
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fn, c, dict(idx["symbols"].get(c, {})), now): c for c in codes}
        for f in cf.as_completed(futs):
            c = futs[f]
            try:
                info, msg = f.result()
                if info:
                    idx["symbols"][c] = info
                print("%s %s: %s" % (label, c, msg), flush=True)
            except Exception as e:
                ERRORS.append("%s %s" % (c, repr(e)[:200]))
                print("ERROR", c, repr(e)[:200], flush=True)
    save_index(idx)
    r = STATS["req"] or 1
    print("   [%d downloads, %d fail, avg %.1fs, %d min baqi]" % (
        STATS["req"], STATS["fail"], STATS["sec"] / r, max(0, time_left()) // 60), flush=True)


def probe():
    """Shuru mein ek file test karo, taake masla foran log mein nazar aaye."""
    d = datetime.now(UTC) - timedelta(days=3)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    url = "%s/EURUSD/%04d/%02d/%02d/BID_candles_min_1.bi5" % (FEED, d.year, d.month - 1, d.day)
    t0 = time.time()
    raw = http_get(url)
    if raw is None:
        print("TEST: download fail (%s) - phir bhi koshish jaari" % LAST_ERR.get("e"), flush=True)
        return
    data = unlzma(raw)
    print("TEST: %s bytes %d -> %d (%.1fs)" % (url, len(raw), len(data), time.time() - t0), flush=True)
    if len(data) < 24:
        print("TEST: data khaali hai (galat URL ya format?)", flush=True)
        sys.exit(1)


def main():
    global BUDGET
    backfill = "--backfill" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    BUDGET = float(os.environ.get("BUDGET_MIN", "200" if backfill else "40")) * 60
    pick_server()
    probe()
    now = datetime.now(UTC)
    idx = load_index()
    idx["order"] = list(SYMBOLS)
    codes = only or list(SYMBOLS)
    # 1) har symbol ka naya data
    run_round(idx, codes, step_forward, now, "NAYA")
    # 2) waqt bache to purana data, round-robin
    while time_left() > 60:
        todo = [c for c in codes if needs_back(idx["symbols"].get(c, {}), now)]
        if not todo:
            print("Sab symbols ka poora purana data aa gaya.", flush=True)
            break
        before = {c: idx["symbols"][c]["from"] for c in todo}
        run_round(idx, todo, step_backward, now, "PURANA")
        if all(idx["symbols"][c]["from"] == before[c] for c in todo):
            print("Is round mein koi taraqqi nahi hui (downloads fail), agli dafa phir koshish.", flush=True)
            break
    idx["updated"] = int(now.timestamp())
    save_index(idx)
    if ERRORS:
        print("\n%d errors (pehle 20):" % len(ERRORS))
        for e in ERRORS[:20]:
            print("  ", e)


if __name__ == "__main__":
    main()
