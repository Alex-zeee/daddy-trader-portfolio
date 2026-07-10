"""Daddy Trader auto-signal bot v6 — Liquidity to Liquidity.
Rule (Ali ka system, pure price action):
  BUY : price neeche wali liquidity (swing low) SWEEP kare aur wohi candle
        pichli red candle ke OPEN se UPAR close ho (engulf close-back).
        SL sweep wick ke neeche. TP = agla UPAR wala liquidity pool,
        magar sirf tab jab kam az kam 1:2 milta ho.
  SELL: bilkul ulta.
Har 15 min scan. Koi indicator filter nahin.
"""
import json
import urllib.request
from datetime import datetime, timezone, timedelta

import pandas as pd
import yfinance as yf

UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 Chrome/126 Safari/537.36")}

PKT = timezone(timedelta(hours=5))
MIN_RR = 2.0
MAX_SIGNALS = 8
EXPIRE_HOURS = 12
LOOKBACK = 120


def _clean(df):
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if len(df) <= 60:
        return None
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    return df


def _yahoo_direct():
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/XAUUSD%3DX"
           "?interval=15m&range=5d")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    res = data["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame(
        {"Open": q["open"], "High": q["high"],
         "Low": q["low"], "Close": q["close"]},
        index=pd.to_datetime(res["timestamp"], unit="s", utc=True))
    return _clean(df)


def _yfinance_spot():
    df = yf.Ticker("XAUUSD=X").history(period="5d", interval="15m")
    return _clean(df) if df is not None and len(df) else None


def _paxg():
    # Binance ka gold token — spot ke qareeb (backup only)
    url = ("https://api.binance.com/api/v3/klines"
           "?symbol=PAXGUSDT&interval=15m&limit=480")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        rows = json.load(r)
    df = pd.DataFrame(
        {"Open": [float(x[1]) for x in rows],
         "High": [float(x[2]) for x in rows],
         "Low": [float(x[3]) for x in rows],
         "Close": [float(x[4]) for x in rows]},
        index=pd.to_datetime([x[0] for x in rows], unit="ms", utc=True))
    return _clean(df)


def fetch_gold():
    """Returns (df, source_name). Spot pehle, PAXG sirf backup."""
    for name, fn in (("SPOT", _yahoo_direct),
                     ("SPOT", _yfinance_spot),
                     ("PAXG~spot", _paxg)):
        try:
            df = fn()
            if df is not None:
                return df, name
        except Exception as e:
            print("fetch fail", name, str(e)[:120])
    return None, None


def add_indicators(df):
    c = df["Close"]
    df["ema20"] = c.ewm(span=20, adjust=False).mean()
    df["ema50"] = c.ewm(span=50, adjust=False).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, 1e-9)
    df["rsi"] = 100 - 100 / (1 + rs)
    tr = (df["High"] - df["Low"]).combine(
        (df["High"] - c.shift()).abs(), max).combine(
        (df["Low"] - c.shift()).abs(), max)
    df["atr"] = tr.rolling(14).mean()
    return df


def market_bias(df):
    b = df.iloc[-2]
    score = 0
    score += 1 if b["ema20"] > b["ema50"] else -1
    score += 1 if b["Close"] > b["ema20"] else -1
    if b["rsi"] > 55:
        score += 1
    elif b["rsi"] < 45:
        score -= 1
    direction = "BUY" if score >= 2 else "SELL" if score <= -2 else "NEUTRAL"
    return {
        "dir": direction,
        "strength": int(abs(score) / 3 * 100),
        "price": round(float(b["Close"]), 2),
        "rsi": int(b["rsi"]),
        "tf": "M15",
    }


def find_swings(c):
    """Fractal swings: 2-2 neighbours. Returns (highs, lows) as [(idx, price)]."""
    highs, lows = [], []
    H, L = c["High"].values, c["Low"].values
    for i in range(2, len(c) - 2):
        if H[i] >= H[i-1] and H[i] >= H[i-2] and H[i] > H[i+1] and H[i] > H[i+2]:
            highs.append((i, float(H[i])))
        if L[i] <= L[i-1] and L[i] <= L[i-2] and L[i] < L[i+1] and L[i] < L[i+2]:
            lows.append((i, float(L[i])))
    return highs, lows


def liquidity_map(c, price):
    highs, lows = find_swings(c)
    H, L = c["High"].values, c["Low"].values
    above, below = [], []
    for i, p in highs:
        if p > price and max(H[i+3:], default=0) < p:      # abhi tak intact
            above.append(round(p, 2))
    for i, p in lows:
        if p < price and min(L[i+3:], default=1e12) > p:   # abhi tak intact
            below.append(round(p, 2))
    above = sorted(set(above))[:3]
    below = sorted(set(below), reverse=True)[:3]
    return {"above": above, "below": below}


def detect_signal(df):
    c = df.iloc[:-1]                      # sirf closed candles
    if len(c) < 30:
        return None
    b = c.iloc[-1]                        # aakhri closed candle
    a = c.iloc[-2]
    ts = c.index[-1]
    atr = float(b["atr"]) if b["atr"] == b["atr"] else 0
    pad = 0.25 * atr
    highs, lows = find_swings(c.iloc[:-1])   # b se pehle ke swings
    H, L = c["High"].values, c["Low"].values
    n = len(c)

    # BUY: sell-side liquidity sweep + engulf close-back upar
    if b["Close"] > b["Open"] and a["Close"] < a["Open"] and float(b["Close"]) > float(a["Open"]):
        swept = None
        for i, p in lows:
            if i <= n - 5 and float(b["Low"]) < p:
                mids = L[i+3:n-1]
                if len(mids) == 0 or mids.min() > p:      # b se pehle intact tha
                    if swept is None or p > swept:
                        swept = p
        if swept is not None:
            entry = round(float(b["Close"]), 2)
            sl = round(float(b["Low"]) - pad, 2)
            risk = entry - sl
            if risk > 0:
                pools = [p for _, p in highs if p > entry + MIN_RR * risk]
                if pools:
                    tp = round(min(pools), 2)             # nazdeeki pool jo 1:2 de
                    return _sig(ts, "BUY", entry, sl, tp, swept)

    # SELL: buy-side liquidity sweep + engulf close-back neeche
    if b["Close"] < b["Open"] and a["Close"] > a["Open"] and float(b["Close"]) < float(a["Open"]):
        swept = None
        for i, p in highs:
            if i <= n - 5 and float(b["High"]) > p:
                mids = H[i+3:n-1]
                if len(mids) == 0 or mids.max() < p:
                    if swept is None or p < swept:
                        swept = p
        if swept is not None:
            entry = round(float(b["Close"]), 2)
            sl = round(float(b["High"]) + pad, 2)
            risk = sl - entry
            if risk > 0:
                pools = [p for _, p in lows if p < entry - MIN_RR * risk]
                if pools:
                    tp = round(max(pools), 2)
                    return _sig(ts, "SELL", entry, sl, tp, swept)
    return None


def _sig(ts, typ, entry, sl, tp, swept):
    return {
        "ts": ts.isoformat(),
        "date": ts.astimezone(PKT).strftime("%d-%m-%Y %H:%M PKT"),
        "pair": "XAUUSD",
        "type": typ,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "status": "Active",
        "note": ("Auto: liquidity sweep @ " + str(round(swept, 2)) +
                 " + engulf close-back — target next liquidity (min 1:2)"),
    }


def load_existing():
    try:
        with open("signals.json") as f:
            return json.load(f).get("signals", [])
    except Exception:
        return []


def update_statuses(sigs, df):
    now = datetime.now(timezone.utc)
    for s in sigs:
        if s.get("status") != "Active":
            continue
        try:
            t0 = datetime.fromisoformat(s["ts"])
        except Exception:
            continue
        after = df[df.index > t0]
        for _, row in after.iterrows():
            if s["type"] == "BUY":
                if row["Low"] <= s["sl"]:
                    s["status"] = "SL Hit"; break
                if row["High"] >= s["tp"]:
                    s["status"] = "TP Hit"; break
            else:
                if row["High"] >= s["sl"]:
                    s["status"] = "SL Hit"; break
                if row["Low"] <= s["tp"]:
                    s["status"] = "TP Hit"; break
        if s["status"] == "Active" and (now - t0) > timedelta(hours=EXPIRE_HOURS):
            s["status"] = "Expired"


def main():
    sigs = load_existing()
    bias = None
    liq = None
    new_sig = None
    df, src = fetch_gold()
    if df is not None:
        df = add_indicators(df)
        df = df.iloc[-LOOKBACK:]
        update_statuses(sigs, df)
        new_sig = detect_signal(df)
        if new_sig and not any(s.get("ts") == new_sig["ts"] for s in sigs):
            sigs.append(new_sig)
        else:
            new_sig = None
        bias = market_bias(df)
        liq = liquidity_map(df.iloc[:-1], float(df.iloc[-2]["Close"]))
    now = datetime.now(timezone.utc)

    def fresh(s):
        try:
            return (now - datetime.fromisoformat(s["ts"])) < timedelta(hours=24)
        except Exception:
            return False
    sigs = [s for s in sigs if fresh(s)]
    sigs = sigs[-MAX_SIGNALS:]
    out = {
        "updated": now.astimezone(PKT).strftime("%d-%m-%Y %H:%M PKT"),
        "src": src,
        "bias": bias,
        "liq": liq,
        "idea": None,
        "signals": sigs,
    }
    with open("signals.json", "w") as f:
        json.dump(out, f, indent=1)
    if new_sig:
        msg = ("{} {} @ {} | SL {} | TP {} | {}".format(
            new_sig["type"], new_sig["pair"], new_sig["entry"],
            new_sig["sl"], new_sig["tp"], new_sig["note"]))
        with open(".new_signal", "w") as f:
            f.write(msg)
    print("signals:", len(sigs), "| new:", bool(new_sig), "| liq:", liq)


if __name__ == "__main__":
    main()
