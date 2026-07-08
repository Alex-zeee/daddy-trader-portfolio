"""Daddy Trader auto-signal bot v3.
- M15 candles par pattern scan (har 15 min run)
- Market Bias har run par update
- Purane Active signals 12 ghante baad Expired
- Naye signal par .new_signal file banti hai (ntfy push ke liye)
"""
import json
from datetime import datetime, timezone, timedelta

import yfinance as yf

PKT = timezone(timedelta(hours=5))
RR = 2.0
MAX_SIGNALS = 8
EXPIRE_HOURS = 12


def fetch_gold():
    for sym in ("XAUUSD=X", "GC=F"):
        try:
            df = yf.Ticker(sym).history(period="5d", interval="15m")
            if df is not None and len(df) > 60:
                df = df.dropna(subset=["Open", "High", "Low", "Close"])
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC")
                else:
                    df.index = df.index.tz_convert("UTC")
                return df
        except Exception as e:
            print("fetch fail", sym, e)
    return None


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


def detect_new(sigs, df):
    a, b = df.iloc[-3], df.iloc[-2]
    ts = df.index[-2]
    atr = float(b["atr"]) if b["atr"] == b["atr"] else 0
    rng = float(b["High"] - b["Low"]) or 1e-9
    body = abs(float(b["Close"] - b["Open"]))
    up_wick = float(b["High"] - max(b["Close"], b["Open"]))
    dn_wick = float(min(b["Close"], b["Open"]) - b["Low"])

    bull_eng = (b["Close"] > b["Open"] and a["Close"] < a["Open"]
                and b["Close"] >= a["Open"] and b["Open"] <= a["Close"])
    bear_eng = (b["Close"] < b["Open"] and a["Close"] > a["Open"]
                and b["Close"] <= a["Open"] and b["Open"] >= a["Close"])
    hammer = dn_wick >= 2 * body and (b["High"] - b["Close"]) / rng <= 0.35
    star = up_wick >= 2 * body and (b["Close"] - b["Low"]) / rng <= 0.35

    trend_up = b["ema20"] > b["ema50"] and b["rsi"] > 45
    trend_dn = b["ema20"] < b["ema50"] and b["rsi"] < 55

    pattern = None
    typ = None
    if (bull_eng or hammer) and trend_up:
        pattern = "Bullish Engulfing" if bull_eng else "Hammer Pin Bar"
        typ = "BUY"
    elif (bear_eng or star) and trend_dn:
        pattern = "Bearish Engulfing" if bear_eng else "Shooting Star"
        typ = "SELL"
    if not pattern:
        return None

    entry = round(float(b["Close"]), 2)
    pad = 0.25 * atr
    if typ == "BUY":
        sl = round(float(min(a["Low"], b["Low"])) - pad, 2)
        risk = entry - sl
        tp = round(entry + RR * risk, 2)
    else:
        sl = round(float(max(a["High"], b["High"])) + pad, 2)
        risk = sl - entry
        tp = round(entry - RR * risk, 2)
    if risk <= 0:
        return None
    key = ts.isoformat()
    if any(s.get("ts") == key for s in sigs):
        return None
    sig = {
        "ts": key,
        "date": ts.astimezone(PKT).strftime("%d-%m-%Y %H:%M PKT"),
        "pair": "XAUUSD",
        "type": typ,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "status": "Active",
        "note": "Auto: M15 " + pattern + " + trend filter",
    }
    sigs.append(sig)
    return sig


def main():
    sigs = load_existing()
    bias = None
    new_sig = None
    df = fetch_gold()
    if df is not None:
        df = add_indicators(df)
        update_statuses(sigs, df)
        new_sig = detect_new(sigs, df)
        bias = market_bias(df)
    # 24 ghante se purane signals hata do (board hamesha fresh rahe)
    now = datetime.now(timezone.utc)
    def fresh(s):
        try:
            return (now - datetime.fromisoformat(s["ts"])) < timedelta(hours=24)
        except Exception:
            return False
    sigs = [s for s in sigs if fresh(s)]
    sigs = sigs[-MAX_SIGNALS:]
    out = {
        "updated": datetime.now(timezone.utc).astimezone(PKT).strftime("%d-%m-%Y %H:%M PKT"),
        "bias": bias,
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
    print("signals:", len(sigs), "| new:", bool(new_sig), "| bias:", bias)


if __name__ == "__main__":
    main()
