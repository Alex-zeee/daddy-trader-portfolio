"""Daddy Trader — ICT signal engine (Gold, M5).

Ye file M5 candles par ICT models dhoondti hai. Live bot (signals.py) aur
backtest dono isi ko istemal karte hain, taake jo test mein dikhe wahi live chale.

Sessions (New York time, DST khud sambhalta hai):
  Asia     20:00-24:00   (PKT ~05:00-09:00)
  London   02:00-05:00   (PKT ~11:00-14:00)
  New York 07:00-11:00   (PKT ~16:00-20:00)
Inke bahar koi signal nahi.

Models:
  2022   : external liquidity sweep (PDH/PDL ya pichla session high/low)
           -> MSS (structure toote, displacement ke saath) -> FVG mein entry
  M1     : H1 FVG (HTF POI) ko tap -> BOS -> M5 FVG mein entry
  M3     : 2022/M1 jaisa, magar FVG OTE zone (62%-79%) ke andar ho
  UNICORN: breaker block aur FVG overlap -> overlap mein entry
  SB     : Silver Bullet — 03-04 ya 10-11 NY ki window mein bana FVG
  TS     : Turtle Soup — PDH/PDL/session level ka false breakout, close wapas andar
SL hamesha sweep/swing ke peeche. TP agli liquidity (kam az kam 1:2), warna 1:2.
"""
from bisect import bisect_left
from datetime import timedelta

import numpy as np
import pandas as pd

NY = "America/New_York"
SESSIONS = {"asia": (20, 24), "london": (2, 5), "ny": (7, 11)}
SB_WINDOWS = [(3, 4), (10, 11)]
MODELS = ("2022", "M1", "M3", "UNICORN", "SB", "TS")
MODEL_NAMES = {
    "2022": "ICT 2022 Model",
    "M1": "Model 1 (HTF POI + BOS + FVG)",
    "M3": "Model 3 (MSS + FVG + OTE)",
    "UNICORN": "Unicorn (Breaker + FVG)",
    "SB": "Silver Bullet",
    "TS": "Turtle Soup",
}

P = {
    "min_rr": 2.0,
    "max_rr": 6.0,
    "sweep_life": 24,      # sweep ke baad MSS ke liye kitni candles (2 ghante)
    "fill_life": 12,       # FVG entry ka intezar (1 ghanta)
    "fvg_min_atr": 0.15,
    "disp_atr": 1.0,       # displacement candle body >= ATR
    "pad_atr": 0.15,       # SL ke peeche thori jagah
    "min_risk": 1.5,       # $ — is se chhota SL spread mein kat jata hai
    "max_risk_atr": 6.0,
}


def session_of(h):
    for name, (a, b) in SESSIONS.items():
        if a <= h < b:
            return name
    return None


def prepare(df):
    """df: index UTC, columns Open High Low Close. Extra columns banata hai."""
    d = df[["Open", "High", "Low", "Close"]].astype(float).copy()
    ny = d.index.tz_convert(NY)
    h = ny.hour + ny.minute / 60.0
    d["nyh"] = h
    d["sess"] = pd.Series([session_of(x) or "" for x in h], index=d.index, dtype=object)
    d["sb"] = [any(a <= x < b for a, b in SB_WINDOWS) for x in h]
    # trading day: 18:00 NY se shuru
    d["tday"] = (ny - pd.Timedelta(hours=18)).date
    pc = d["Close"].shift()
    tr = np.maximum(d["High"] - d["Low"], np.maximum((d["High"] - pc).abs(), (d["Low"] - pc).abs()))
    d["atr"] = tr.rolling(14, min_periods=5).mean()
    return d


class Levels:
    """Liquidity levels jo bar i par maloom hain (sirf maazi ka data)."""

    def __init__(self, d):
        self.d = d
        H, L = d["High"].values, d["Low"].values
        n = len(d)
        # previous day high/low
        days = d["tday"].values
        uniq = list(dict.fromkeys(days))
        dh = d.groupby("tday")["High"].max()
        dl = d.groupby("tday")["Low"].min()
        prev = {uniq[k]: uniq[k - 1] for k in range(1, len(uniq))}
        self.pdh = np.array([dh[prev[x]] if x in prev else np.nan for x in days])
        self.pdl = np.array([dl[prev[x]] if x in prev else np.nan for x in days])
        # completed sessions: (end_idx, name, high, low)
        self.sessions = []
        sess = d["sess"].values
        start = None
        for i in range(n + 1):
            s = sess[i] if i < n else None
            if start is not None and (s != sess[start] or (i < n and days[i] != days[start])):
                self.sessions.append((i - 1, sess[start], H[start:i].max(), L[start:i].min(), start))
                start = None
            if start is None and s and i < n:
                start = i
        self.sess_end = [x[0] for x in self.sessions]
        # M5 fractal swings (k=2), confirm index = j+2
        self.sh, self.sl = [], []
        for j in range(2, n - 2):
            if H[j] >= H[j - 1] and H[j] >= H[j - 2] and H[j] > H[j + 1] and H[j] > H[j + 2]:
                self.sh.append(j)
            if L[j] <= L[j - 1] and L[j] <= L[j - 2] and L[j] < L[j + 1] and L[j] < L[j + 2]:
                self.sl.append(j)
        # M15 swings (k=2 on 15m) for draw-on-liquidity targets
        self.big_sh, self.big_sl = self._htf_swings(3)
        # H1 FVGs: (created_idx, dir, lo, hi)
        self.h1fvg = self._h1_fvgs()

    def _htf_swings(self, m):
        d = self.d
        H, L = d["High"].values, d["Low"].values
        n = len(d)
        g = np.arange(n) // m
        hh = pd.Series(H).groupby(g).max().values
        ll = pd.Series(L).groupby(g).min().values
        sh, sl = [], []
        for j in range(2, len(hh) - 2):
            conf = min((j + 3) * m - 1, n - 1)   # 2 aur HTF candles baad confirm
            if hh[j] >= hh[j - 1] and hh[j] >= hh[j - 2] and hh[j] > hh[j + 1] and hh[j] > hh[j + 2]:
                sh.append((conf, hh[j], j * m))
            if ll[j] <= ll[j - 1] and ll[j] <= ll[j - 2] and ll[j] < ll[j + 1] and ll[j] < ll[j + 2]:
                sl.append((conf, ll[j], j * m))
        return sh, sl

    def _h1_fvgs(self):
        d = self.d
        hr = d.index.floor("1h")
        grp = pd.Series(np.arange(len(d)), index=d.index).groupby(hr)
        first = grp.min().values
        last = grp.max().values
        H = d["High"].groupby(hr).max().values
        L = d["Low"].groupby(hr).min().values
        out = []
        for k in range(2, len(H)):
            conf = last[k]
            if L[k] > H[k - 2]:
                out.append((conf, "bull", H[k - 2], L[k]))
            if H[k] < L[k - 2]:
                out.append((conf, "bear", H[k], L[k - 2]))
        return out

    def external(self, i, side):
        """i se pehle ki external liquidity: PDH/PDL + 30 ghante ke andar ke sessions."""
        out = []
        if side == "high":
            if self.pdh[i] == self.pdh[i]:
                out.append((self.pdh[i], "PDH", None))
        else:
            if self.pdl[i] == self.pdl[i]:
                out.append((self.pdl[i], "PDL", None))
        t = self.d.index[i]
        k = bisect_left(self.sess_end, i)
        for end, name, hi, lo, st in self.sessions[max(0, k - 8):k]:
            if t - self.d.index[end] > timedelta(hours=30):
                continue
            out.append(((hi if side == "high" else lo), name.upper() + (" High" if side == "high" else " Low"), end))
        return out

    def targets(self, i, direction, entry):
        """Opposite liquidity pools jo abhi tak intact hain."""
        d = self.d
        H, L = d["High"].values, d["Low"].values
        pools = []
        if direction == "SELL":
            for p, name, end in self.external(i, "low"):
                pools.append(p)
            for conf, p, j in self.big_sl:
                if conf < i and i - conf < 600 and L[conf + 1:i + 1].min(initial=1e18) > p:
                    pools.append(p)
            pools = sorted(x for x in pools if x < entry)[::-1]
        else:
            for p, name, end in self.external(i, "high"):
                pools.append(p)
            for conf, p, j in self.big_sh:
                if conf < i and i - conf < 600 and H[conf + 1:i + 1].max(initial=-1e18) < p:
                    pools.append(p)
            pools = sorted(x for x in pools if x > entry)
        return pools


def pick_tp(lv, i, direction, entry, sl):
    risk = abs(entry - sl)
    for p in lv.targets(i, direction, entry):
        rr = abs(p - entry) / risk
        if rr >= P["min_rr"]:
            if rr <= P["max_rr"]:
                return round(p, 2), "liquidity"
            break
    tp = entry - P["min_rr"] * risk if direction == "SELL" else entry + P["min_rr"] * risk
    return round(tp, 2), "1:2"


def find_fvg(d, a, b, direction, atr):
    """[a, b] candles ke beech sab se bara FVG. Returns (lo, hi, j) ya None."""
    H, L = d["High"].values, d["Low"].values
    best = None
    for j in range(max(a, 1), b):
        if j + 1 > b:
            break
        if direction == "SELL":
            lo, hi = H[j + 1], L[j - 1]
        else:
            lo, hi = H[j - 1], L[j + 1]
        size = hi - lo
        if size > P["fvg_min_atr"] * atr and (best is None or size > best[1] - best[0]):
            best = (lo, hi, j)
    return best


def run(df, models=MODELS, start=0):
    """Saari candles par chalta hai aur signals ki list deta hai.
    Har signal: dict(model, type, entry, sl, tp, i_signal, why)."""
    d = prepare(df)
    lv = Levels(d)
    O, H, L, C = (d[k].values for k in ("Open", "High", "Low", "Close"))
    ATR, SESS, SB = d["atr"].values, d["sess"].values, d["sb"].values
    n = len(d)
    sweeps = []      # active sweep events
    pend = []        # pending FVG entries
    used = set()     # levels jo sweep ho chuke (dobara nahi)
    out = []
    sh_ptr = sl_ptr = 0
    conf_sh, conf_sl = [], []   # confirmed swing indexes till now

    def add_pend(base, **kw):
        e, sl = kw["entry"], base["sl"]
        g = e - P["min_rr"] * (sl - e) if base["dir"] == "SELL" else e + P["min_rr"] * (e - sl)
        x = dict(base, **kw)
        x["tp_guard"] = g
        pend.append(x)

    def emit(model, direction, entry, sl, i, why, ctx=None):
        risk = abs(entry - sl)
        atr = ATR[i]
        if risk < P["min_risk"] or risk > P["max_risk_atr"] * atr:
            return
        tp, tpk = pick_tp(lv, i, direction, entry, sl)
        out.append({"model": model, "type": direction, "entry": round(entry, 2),
                    "sl": round(sl, 2), "tp": tp, "tpk": tpk, "i": i,
                    "ts": d.index[i], "why": why, "ctx": ctx or {}})

    for i in range(20, n):
        atr = ATR[i]
        if atr != atr or atr <= 0:
            continue
        while sh_ptr < len(lv.sh) and lv.sh[sh_ptr] + 2 <= i:
            conf_sh.append(lv.sh[sh_ptr]); sh_ptr += 1
        while sl_ptr < len(lv.sl) and lv.sl[sl_ptr] + 2 <= i:
            conf_sl.append(lv.sl[sl_ptr]); sl_ptr += 1
        insess = bool(SESS[i])
        pad = P["pad_atr"] * atr

        # ---- 1) pending FVG entries fill hue? ----
        keep = []
        for s in pend:
            if i <= s["made"]:
                keep.append(s); continue
            dirn = s["dir"]
            filled = H[i] >= s["entry"] if dirn == "SELL" else L[i] <= s["entry"]
            if filled:
                if i >= start and SESS[i]:
                    emit(s["model"], dirn, s["entry"], s["sl"], i, s["why"], s.get("ctx"))
                continue
            ran = L[i] <= s["tp_guard"] if dirn == "SELL" else H[i] >= s["tp_guard"]
            if ran:
                continue                          # bina retrace ke 1:2 tak chala gaya: miss
            if i - s["made"] < s["life"]:
                keep.append(s)
        pend = keep

        if not insess:
            sweeps = [w for w in sweeps if i - w["bar"] <= P["sweep_life"]]
            continue

        # ---- 2) naye sweeps (external liquidity + H1 POI) ----
        for side, dirn in (("high", "SELL"), ("low", "BUY")):
            for p, name, end in lv.external(i, side):
                key = (round(p, 2), side)
                if key in used:
                    continue
                prev_ok = (H[i - 1] < p) if side == "high" else (L[i - 1] > p)
                hit = (H[i] > p) if side == "high" else (L[i] < p)
                if hit and prev_ok:
                    used.add(key)
                    sweeps.append({"dir": dirn, "lvl": p, "name": name, "bar": i,
                                   "ext": H[i] if side == "high" else L[i], "kind": "ext", "ts_done": False})
        for conf, fd, lo, hi in lv.h1fvg:
            if conf >= i or i - conf > 72 * 12:
                continue
            key = ("h1", conf, fd)
            if key in used:
                continue
            if fd == "bear" and H[i] >= lo and H[i - 1] < lo:
                used.add(key)
                sweeps.append({"dir": "SELL", "lvl": lo, "name": "H1 FVG", "bar": i, "ext": H[i], "kind": "poi"})
            if fd == "bull" and L[i] <= hi and L[i - 1] > hi:
                used.add(key)
                sweeps.append({"dir": "BUY", "lvl": hi, "name": "H1 FVG", "bar": i, "ext": L[i], "kind": "poi"})

        # ---- 3) har active sweep: extreme update, Turtle Soup, MSS ----
        keep = []
        for w in sweeps:
            if i - w["bar"] > P["sweep_life"]:
                continue
            dirn = w["dir"]
            if i > w["bar"]:
                if dirn == "SELL" and H[i] > w["ext"]:
                    w["ext"] = H[i]; w["ext_bar"] = i
                if dirn == "BUY" and L[i] < w["ext"]:
                    w["ext"] = L[i]; w["ext_bar"] = i
            eb = w.get("ext_bar", w["bar"])
            # Turtle Soup: 3 candles ke andar close wapas level ke andar
            if w["kind"] == "ext" and "TS" in models and not w.get("ts_done") and i - w["bar"] <= 3:
                back = C[i] < w["lvl"] if dirn == "SELL" else C[i] > w["lvl"]
                if back:
                    w["ts_done"] = True
                    sl = w["ext"] + pad if dirn == "SELL" else w["ext"] - pad
                    if i >= start:
                        emit("TS", dirn, C[i], sl, i, "False breakout of " + w["name"],
                             {"lvl": w["lvl"], "lvl_name": w["name"], "sweep_i": w["bar"],
                              "ext": w["ext"], "ext_i": w.get("ext_bar", w["bar"])})
            # MSS: sweep se pehle wala swing toote, displacement ke saath
            ref = None
            if "ref" not in w:
                lst = conf_sl if dirn == "SELL" else conf_sh
                k = bisect_left(lst, w["bar"]) - 1
                while k >= 0 and w["bar"] - lst[k] < 150:
                    j = lst[k]
                    if (dirn == "SELL" and L[j] < w["ext"]) or (dirn == "BUY" and H[j] > w["ext"]):
                        ref = j
                        break
                    k -= 1
                w["ref"] = ref
            ref = w["ref"]
            if dirn == "SELL":
                broke = ref is not None and C[i] < L[ref]
            else:
                broke = ref is not None and C[i] > H[ref]
            if not broke:
                keep.append(w); continue
            body = np.abs(C[eb:i + 1] - O[eb:i + 1]).max()
            if body < P["disp_atr"] * atr:
                continue                          # displacement nahi: setup khatam
            fvg = find_fvg(d, eb + 1, i, dirn, atr)
            if fvg is None:
                continue
            lo, hi, fj = fvg
            ext = w["ext"]
            leg_end = L[eb:i + 1].min() if dirn == "SELL" else H[eb:i + 1].max()
            rng = abs(ext - leg_end)
            sl = ext + pad if dirn == "SELL" else ext - pad
            ctx = {"lvl": w["lvl"], "lvl_name": w["name"], "sweep_i": w["bar"], "ext": ext, "ext_i": eb,
                   "ref_i": ref, "ref_px": (L[ref] if dirn == "SELL" else H[ref]), "mss_i": i,
                   "fvg": [lo, hi, fj]}
            base = {"dir": dirn, "sl": sl, "made": i, "life": P["fill_life"], "ctx": ctx}
            why = "{} swept -> MSS -> FVG".format(w["name"])
            entry = lo if dirn == "SELL" else hi      # FVG ka qareebi kinara
            if w["kind"] == "ext" and "2022" in models:
                add_pend(base, model="2022", entry=entry, why=why)
            if w["kind"] == "poi" and "M1" in models:
                add_pend(base, model="M1", entry=entry, why="H1 FVG tap -> BOS -> FVG")
            if "M3" in models and rng > 0:
                if dirn == "SELL":
                    z_lo, z_hi = leg_end + 0.62 * rng, leg_end + 0.79 * rng
                else:
                    z_lo, z_hi = ext + 0.21 * rng, ext + 0.38 * rng
                o_lo, o_hi = max(lo, z_lo), min(hi, z_hi)
                if o_lo < o_hi:
                    e3 = o_lo if dirn == "SELL" else o_hi
                    add_pend(base, model="M3", entry=e3, why=why + " in OTE",
                             ctx=dict(ctx, ote=[z_lo, z_hi]))
            if "UNICORN" in models:
                # breaker: toote hue swing ka order block (aakhri ulti candle)
                k = ref
                if dirn == "SELL":
                    while k > 0 and not (C[k] < O[k]):
                        k -= 1
                else:
                    while k > 0 and not (C[k] > O[k]):
                        k -= 1
                b_lo, b_hi = L[k], H[k]
                o_lo, o_hi = max(lo, b_lo), min(hi, b_hi)
                if o_lo < o_hi:
                    eu = o_lo if dirn == "SELL" else o_hi
                    add_pend(base, model="UNICORN", entry=eu, why="Breaker + FVG overlap",
                             ctx=dict(ctx, brk=[b_lo, b_hi, k]))
        sweeps = keep

        # ---- 4) Silver Bullet: window mein naya FVG ----
        if "SB" in models and SB[i] and SB[i - 1] and i >= 3:
            j = i - 1
            for dirn in ("SELL", "BUY"):
                if dirn == "SELL":
                    lo, hi = H[j + 1], L[j - 1]
                    disp = C[j] < O[j] and (O[j] - C[j]) >= P["disp_atr"] * atr
                else:
                    lo, hi = H[j - 1], L[j + 1]
                    disp = C[j] > O[j] and (C[j] - O[j]) >= P["disp_atr"] * atr
                if disp and hi - lo > P["fvg_min_atr"] * atr:
                    if dirn == "SELL":
                        sl = H[max(0, j - 6):j + 1].max() + pad
                        entry = lo
                    else:
                        sl = L[max(0, j - 6):j + 1].min() - pad
                        entry = hi
                    add_pend({"dir": dirn, "sl": sl, "made": i, "life": 8,
                              "ctx": {"fvg": [lo, hi, j], "sb_i": i}},
                             model="SB", entry=entry, why="Silver Bullet FVG")
    return out, d


def simulate(sigs, d, spread=0.30, expire_h=12, one_at_a_time=True):
    """Har signal ka nateeja M5 candles par (conservative):
    ek candle mein SL aur TP dono -> SL; entry wali candle SL tak gayi -> SL.
    Spread har trade se kaat diya jata hai."""
    H, L, C = d["High"].values, d["Low"].values, d["Close"].values
    n = len(d)
    res = []
    busy_until = {}
    for s in sigs:
        key = s["model"] if one_at_a_time else id(s)
        if busy_until.get(key, -1) >= s["i"]:
            continue
        risk = abs(s["entry"] - s["sl"])
        buy = s["type"] == "BUY"
        status, j_end = None, None
        end = min(n - 1, s["i"] + expire_h * 12)
        for j in range(s["i"], end + 1):
            hit_sl = L[j] <= s["sl"] if buy else H[j] >= s["sl"]
            hit_tp = (H[j] >= s["tp"] if buy else L[j] <= s["tp"]) and j > s["i"]
            if hit_sl:
                status, j_end = "SL", j; break
            if hit_tp:
                status, j_end = "TP", j; break
        if status is None:
            status, j_end = "EXP", end
        if status == "SL":
            r = -1.0
        elif status == "TP":
            r = abs(s["tp"] - s["entry"]) / risk
        else:
            r = ((C[end] - s["entry"]) if buy else (s["entry"] - C[end])) / risk
        r -= spread / risk
        busy_until[key] = j_end
        res.append(dict(s, status=status, r=r, j_end=j_end))
    return res
