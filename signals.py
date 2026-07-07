"""Daddy Trader auto-signal bot.
Har run par: XAUUSD H1 data utha kar Engulfing pattern check karta hai,
naya signal signals.json mein likhta hai, aur purane Active signals
ka TP/SL status update karta hai. GitHub Actions se har 30 min chalta hai.
"""
import json
from datetime import datetime, timezone, timedelta

import yfinance as yf

PKT = timezone(timedelta(hours=5))
RR = 2.0          # risk : reward = 1 : 2
MAX_SIGNALS = 12  # itne aakhri signals website par rehte hain


def fetch_gold():
    for sym in ("XAUUSD=X", "GC=F"):
        try:
            df = yf.Ticker(sym).history(period="5d", interval="1h")
            if df is not None and len(df) > 10:
                df = df.dropna(subset=["Open", "High", "Low", "Close"])
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC")
                else:
                    df.index = df.index.tz_convert("UTC")
                return df
        except Exception as e:
            print("fetch fail", sym, e)
    return None


def load_existing():
    try:
        with open("signals.json") as f:
            return json.load(f).get("signals", [])
    except Exception:
        return []


def update_statuses(sigs, df):
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


def detect_new(sigs, df):
    if len(df) < 3:
        return
    a, b = df.iloc[-3], df.iloc[-2]      # b = aakhri closed candle
    ts = df.index[-2]
    bull = (b["Close"] > b["Open"] and a["Close"] < a["Open"]
            and b["Close"] >= a["Open"] and b["Open"] <= a["Close"])
    bear = (b["Close"] < b["Open"] and a["Close"] > a["Open"]
            and b["Close"] <= a["Open"] and b["Open"] >= a["Close"])
    if not (bull or bear):
        return
    entry = round(float(b["Close"]), 2)
    if bull:
        sl = round(float(min(a["Low"], b["Low"])), 2)
        risk = entry - sl
        tp = round(entry + RR * risk, 2)
        typ = "BUY"
    else:
        sl = round(float(max(a["High"], b["High"])), 2)
        risk = sl - entry
        tp = round(entry - RR * risk, 2)
        typ = "SELL"
    if risk <= 0:
        return
    key = ts.isoformat()
    if any(s.get("ts") == key for s in sigs):
        return  # yeh signal pehle se mojood hai
    sigs.append({
        "ts": key,
        "date": ts.astimezone(PKT).strftime("%d-%m-%Y %H:%M PKT"),
        "pair": "XAUUSD",
        "type": typ,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "status": "Active",
        "note": "Auto: H1 Engulfing detected",
    })


def main():
    sigs = load_existing()
    df = fetch_gold()
    if df is not None:
        update_statuses(sigs, df)
        detect_new(sigs, df)
    sigs = sigs[-MAX_SIGNALS:]
    out = {
        "updated": datetime.now(timezone.utc).astimezone(PKT).strftime("%d-%m-%Y %H:%M PKT"),
        "signals": sigs,
    }
    with open("signals.json", "w") as f:
        json.dump(out, f, indent=1)
    print("total signals:", len(sigs))


if __name__ == "__main__":
    main()
