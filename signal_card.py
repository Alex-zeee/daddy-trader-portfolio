"""Daddy Trader — har naye signal ki tasveer (card) banana.

signal-card-bg.jpg (khaali card) par signal ki likhai safed, bold aur saaf likhi jaati hai.
Naye signal, TP HIT aur SL HIT — teeno ke liye yehi card.
Nateeja PNG bytes, jo wa_post.py WhatsApp par bhejta hai.

Khud chala kar dekhna:  python signal_card.py   ->  signal-card-test.png
"""
import glob, io, os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
BG = os.path.join(HERE, "signal-card-bg.jpg")
X0, Y0, X1, Y1 = 188, 196, 1012, 692          # saamne wale kaale card ki hadd
ORANGE, SHINE, WHITE = (245, 140, 20), (255, 200, 130), (255, 255, 255)


def font(size):
    paths = ["/usr/share/fonts/opentype/inter/Inter-Bold.otf"]
    paths += glob.glob("/usr/share/fonts/**/Inter*Bold.[ot]tf", recursive=True)
    paths += ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def money(v):
    try:
        return "{:,.2f}".format(float(v))
    except Exception:
        return str(v)


def pair_name(p):
    p = str(p or "XAUUSD").upper()
    return p[:3] + "/" + p[3:] if len(p) == 6 else p


def rr(s):
    try:
        e, sl, tp = float(s["entry"]), float(s["sl"]), float(s["tp"])
        return "1:{:g}".format(round(abs(tp - e) / abs(e - sl), 1))
    except Exception:
        return ""


def make(sig, kind="new"):
    """Signal (signals.json wali ek entry) se card ki PNG bytes.
    kind: "new" naya signal, "tp" take profit poora hua, "sl" stop loss laga."""
    img = Image.open(BG).convert("RGB")
    d = ImageDraw.Draw(img)
    f_pair, f_line = font(35), font(33)

    pair = pair_name(sig.get("pair"))
    title = "{} {}".format(pair, str(sig.get("type", "")).upper()).strip()
    status = []
    if kind == "tp":
        status = ["TP HIT"]
        lines = ["Entry: " + money(sig.get("entry")), "Take profit: " + money(sig.get("tp"))]
        if rr(sig):
            lines.append("Risk : reward " + rr(sig))
    elif kind == "sl":
        status = ["SL HIT"]
        lines = ["Entry: " + money(sig.get("entry")), "Stop loss: " + money(sig.get("sl"))]
    else:
        lines = [
            "Entry: " + money(sig.get("entry")),
            "Stop loss: " + money(sig.get("sl")),
            "Take profit: " + money(sig.get("tp")),
        ]
        if rr(sig):
            lines.append("Risk : reward " + rr(sig))

    rows = [("dot", "", None, 40), ("pair", title, f_pair, 58)]
    rows += [("line", t, f_pair, 58) for t in status]
    rows += [("line", t, f_line, 46) for t in lines]
    block = sum(r[3] for r in rows) - 6
    y = (Y0 + Y1) / 2 - block / 2
    left = X0 + 70
    dot = 24

    # narangi nuqta pair ke doosre hisse ke beech wale harf ke upar (XAU/USD mein "S")
    if "/" in pair:
        a, b = pair.split("/", 1)
        mid = len(b) // 2
        cx = left + d.textlength(a + "/" + b[:mid], font=f_pair) + d.textlength(b[mid], font=f_pair) / 2
    else:
        cx = left + d.textlength(pair, font=f_pair) / 2

    for kind, t, f, h in rows:
        if kind == "dot":
            x, cy = cx - dot / 2, y + dot / 2
            d.ellipse((x, cy - dot / 2, x + dot, cy + dot / 2), fill=ORANGE)
            d.ellipse((x + 5, cy - dot / 2 + 4, x + dot - 9, cy - 2), fill=SHINE)
        else:
            d.text((round(left), round(y)), t, font=f, fill=WHITE)
        y += h

    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


if __name__ == "__main__":
    demo = {"pair": "XAUUSD", "type": "BUY", "entry": 4060.20, "sl": 4054.00, "tp": 4078.80}
    for k in ("new", "tp", "sl"):
        name = "signal-card-test.png" if k == "new" else "signal-card-test-%s.png" % k
        with open(name, "wb") as fh:
            fh.write(make(demo, k))
        print(name, "bana diya")
