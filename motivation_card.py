"""Daddy Trader — rozana motivation post ki tasveer khud banana (koi bahar ki tasveer nahi).

Paanch andaaz (style) hain; har din agla andaaz aur agla jumla. Sab kuch code se banta hai,
is liye har tasveer apni aur nayi hoti hai.
"""
import io, math, os, random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

W, H = 1080, 1350
HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "logo.png")

GYRE = "/usr/share/texmf/fonts/opentype/public/tex-gyre/"
INTER = "/usr/share/fonts/opentype/inter/"
FONTS = {
    "serif": [GYRE + "texgyrepagella-regular.otf", "/usr/share/fonts/truetype/crosextra/Caladea-Regular.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"],
    "serif_b": [GYRE + "texgyrepagella-bold.otf", "/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"],
    "black": [INTER + "InterDisplay-Black.otf", INTER + "Inter-Black.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "xbold": [INTER + "InterDisplay-ExtraBold.otf", INTER + "Inter-ExtraBold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "bold": [INTER + "Inter-Bold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "semi": [INTER + "Inter-SemiBold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "med": [INTER + "Inter-Medium.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "reg": [INTER + "Inter-Regular.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}


def F(kind, size):
    for p in FONTS[kind]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


# ---------------- chhote auzaar ----------------
def noise_bg(top, bottom, seed, grain=3.0):
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, H)[:, None, None]
    a = np.array(top, float)[None, None, :] * (1 - t) + np.array(bottom, float)[None, None, :] * t
    a = np.repeat(a, W, axis=1)
    a += rng.normal(0, grain, (H, W, 1))
    return a


def vignette(a, strength=0.55):
    y, x = np.mgrid[0:H, 0:W]
    d = np.sqrt(((x - W / 2) / (W * 0.75)) ** 2 + ((y - H / 2) / (H * 0.7)) ** 2)
    return a * (1 - strength * np.clip(d, 0, 1)[..., None] ** 2)


def radial(a, cx, cy, r, color, amt):
    y, x = np.mgrid[0:H, 0:W]
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / r
    g = np.clip(1 - d, 0, 1) ** 2
    return a + g[..., None] * np.array(color, float)[None, None, :] * amt


def to_img(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def add_glow(base, layer, radius, amount=1.0):
    """layer (RGBA) ko dhundla kar ke roshni ki tarah jor do, phir saaf layer upar."""
    glow = layer.filter(ImageFilter.GaussianBlur(radius))
    b = np.array(base, float)
    g = np.array(glow, float)
    b += g[..., :3] * (g[..., 3:] / 255.0) * amount
    out = to_img(b)
    out.paste(layer, (0, 0), layer)
    return out


def text_w(t, f, track=0):
    return sum(f.getlength(c) for c in t) + track * max(len(t) - 1, 0)


def draw_tracked(d, xy, t, f, fill, track=0, anchor="l"):
    x, y = xy
    tw = text_w(t, f, track)
    if anchor == "c":
        x -= tw / 2
    elif anchor == "r":
        x -= tw
    for c in t:
        d.text((round(x), round(y)), c, font=f, fill=fill)
        x += f.getlength(c) + track
    return tw


def gradient_text(size, t, f, colors, track=0, anchor="c", xy=(0, 0), vertical=True):
    """Rang-badalti likhai ki RGBA layer."""
    mask = Image.new("L", size, 0)
    draw_tracked(ImageDraw.Draw(mask), xy, t, f, 255, track, anchor)
    w, h = size
    if vertical:
        bb = mask.getbbox() or (0, 0, w, h)
        t0, t1 = bb[1], max(bb[3], bb[1] + 1)
        tt = np.clip((np.arange(h) - t0) / (t1 - t0), 0, 1)[:, None]
        tt = np.repeat(tt, w, 1)
    else:
        bb = mask.getbbox() or (0, 0, w, h)
        t0, t1 = bb[0], max(bb[2], bb[0] + 1)
        tt = np.clip((np.arange(w) - t0) / (t1 - t0), 0, 1)[None, :]
        tt = np.repeat(tt, h, 0)
    col = np.zeros((h, w, 3))
    n = len(colors) - 1
    for i in range(n):
        lo, hi = i / n, (i + 1) / n
        m = (tt >= lo) & (tt <= hi)
        k = ((tt - lo) / (hi - lo))[..., None]
        c = np.array(colors[i], float) * (1 - k) + np.array(colors[i + 1], float) * k
        col = np.where(m[..., None], c, col)
    rgba = np.dstack([col, np.array(mask)]).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def candles(rng, n, x0, x1, y_start, y_end, vol, curve=1.0):
    """Upar jaati hui candles (khud bani hui)."""
    xs = np.linspace(x0, x1, n)
    trend = y_start + (y_end - y_start) * np.linspace(0, 1, n) ** curve
    o = trend[0]
    out = []
    for i in range(n):
        c = trend[i] + rng.normal(0, vol)
        if i % 9 in (5, 6):
            c += vol * 1.4  # thori si wapsi (pullback)
        hi = min(o, c) - abs(rng.normal(0, vol * 0.8))
        lo = max(o, c) + abs(rng.normal(0, vol * 0.8))
        out.append((xs[i], o, c, hi, lo))
        o = c
    return out


def brand(img, color=(214, 178, 94), y=None, dark=False):
    """Neeche chhota sa logo + DADDY TRADER + website."""
    d = ImageDraw.Draw(img)
    y = y or H - 92
    f1, f2 = F("semi", 22), F("med", 18)
    label = "DADDY TRADER"
    tw = text_w(label, f1, 6)
    lw = 0
    if os.path.exists(LOGO):
        lg = Image.open(LOGO).convert("RGBA")
        lh = 44
        lw = round(lg.width * lh / lg.height)
        lg = lg.resize((lw, lh), Image.LANCZOS)
        a = np.array(lg)
        a[..., :3] = color
        lg = Image.fromarray(a)
        x = W / 2 - (lw + 14 + tw) / 2
        img.paste(lg, (round(x), y - 12), lg)
        draw_tracked(d, (x + lw + 14, y), label, f1, color, 6)
    else:
        draw_tracked(d, (W / 2, y), label, f1, color, 6, "c")
    sub = (150, 150, 150) if not dark else (90, 90, 90)
    draw_tracked(d, (W / 2, y + 38), "daddytrader.live", f2, sub, 2, "c")
    return img


def mountains(a, rng, base_y, peak_x, peak_y, color, rim=None, rim_amt=0.0):
    """Pahar ka saya (midpoint displacement)."""
    n = 257
    xs = np.linspace(0, W, n)
    prof = np.full(n, float(base_y))
    # bara pahar
    prof = np.minimum(prof, peak_y + np.abs(xs - peak_x) * 0.95)
    # chhoti chotiyaan
    for _ in range(4):
        px, ph = rng.uniform(0, W), rng.uniform(base_y - 260, base_y - 80)
        prof = np.minimum(prof, ph + np.abs(xs - px) * rng.uniform(0.7, 1.2))
    # khurdura kinara
    rough = np.zeros(n)
    step, amp = 128, 40.0
    while step >= 1:
        for i in range(0, n - 1, step):
            j = i + step
            if j < n:
                m = (i + j) // 2
                rough[m] = (rough[i] + rough[j]) / 2 + rng.normal(0, amp)
        step //= 2
        amp *= 0.55
    prof = np.minimum(prof + rough * 0.6, base_y + 40)
    ridge = np.interp(np.arange(W), xs, prof)
    yy = np.arange(H)[:, None]
    m = yy >= ridge[None, :]
    a = np.where(m[..., None], np.array(color, float)[None, None, :] + a * 0.08, a)
    if rim is not None:
        edge = np.exp(-((yy - ridge[None, :]) / 3.0) ** 2) * (yy >= ridge[None, :] - 2)
        a = a + edge[..., None] * np.array(rim, float)[None, None, :] * rim_amt
    return a, ridge


# ---------------- 1) Gold Ascent ----------------
def style_gold(q, seed):
    rng = np.random.default_rng(seed)
    a = noise_bg((6, 5, 4), (2, 2, 2), seed, 2.2)
    a = radial(a, W * 0.62, H * 0.45, 760, (60, 42, 12), 0.55)
    # chaand
    mx, my, mr = W * 0.5, H * 0.79, 175
    y, x = np.mgrid[0:H, 0:W]
    dd = np.sqrt((x - mx) ** 2 + (y - my) ** 2)
    tex = np.array(Image.fromarray((rng.random((90, 90)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), float) / 255
    moon = (dd < mr) * (0.35 + 0.25 * tex)
    a += moon[..., None] * np.array([70, 60, 42])[None, None, :]
    a += (np.exp(-((dd - mr) / 6) ** 2) * 40)[..., None] * np.array([0.9, 0.75, 0.45])[None, None, :]
    a, ridge = mountains(a, rng, H - 250, W * 0.5, H * 0.73, (8, 7, 6), rim=(210, 170, 90), rim_amt=0.55)
    # paani ki chamak
    wy = H - 210
    shimmer = (np.arange(H)[:, None] > wy) * (rng.random((H, W)) > 0.985) * np.clip(1 - np.abs(np.arange(W)[None, :] - mx) / 420, 0, 1)
    a += shimmer[..., None] * np.array([180, 140, 70])[None, None, :] * 0.8
    img = to_img(vignette(a, 0.5))

    # candles
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cs = candles(rng, 58, 40, W - 40, H * 0.86, H * 0.17, 15, curve=1.9)
    for i, (cx, o, c, hi, lo) in enumerate(cs):
        al = int(70 + 185 * (i / len(cs)) ** 1.3)
        gold = (236, 196, 110, al)
        d.line([(cx, hi), (cx, lo)], fill=(220, 180, 100, int(al * 0.7)), width=2)
        top, bot = min(o, c), max(o, c)
        if bot - top < 4:
            bot = top + 4
        if c < o:  # upar wali (bullish)
            d.rectangle([cx - 6, top, cx + 6, bot], fill=gold)
        else:
            d.rectangle([cx - 6, top, cx + 6, bot], outline=gold, width=2)
    # moving average line
    pts = [(cx, (o + c) / 2 + 70) for cx, o, c, hi, lo in cs]
    sm = [pts[0]]
    for p in pts[1:]:
        sm.append((p[0], sm[-1][1] * 0.82 + p[1] * 0.18))
    d.line(sm, fill=(230, 190, 110, 95), width=2)
    img = add_glow(img, layer, 9, 0.9)

    # likhai
    words = q["lines"]
    size = 66
    while size > 40 and max(text_w(w.upper(), F("serif", size), size * 0.39) for w in words) > 700:
        size -= 2
    f = F("serif", size)
    top = 230
    for i, wd in enumerate(words):
        lay = gradient_text((W, H), wd.upper(), f, [(255, 232, 170), (214, 170, 82), (160, 118, 44)], track=round(size * 0.39),
                            anchor="c", xy=(W / 2 - 60, top + i * 110))
        img = add_glow(img, lay, 6, 0.5)
    # sunehri lakeer
    ly = top + len(words) * 110 + 26
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    for k in range(170):
        al = int(255 * (1 - abs(k - 85) / 85) ** 1.5)
        ld.line([(W / 2 - 60 - 170 + k * 2, ly), (W / 2 - 60 - 168 + k * 2, ly)], fill=(240, 200, 120, al), width=2)
    ld.ellipse([W / 2 - 66, ly - 4, W / 2 - 54, ly + 4], fill=(255, 230, 170, 255))
    img = add_glow(img, lay, 5, 1.2)
    return brand(img)


# ---------------- 2) Red Target ----------------
RED = (226, 30, 44)


def target(d, cx, cy, r, color, width=3):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=width)
    d.ellipse([cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55], outline=color, width=max(2, width - 1))
    d.ellipse([cx - r * 0.16, cy - r * 0.16, cx + r * 0.16, cy + r * 0.16], fill=color)
    d.line([(cx - r * 1.45, cy), (cx - r * 0.3, cy)], fill=color, width=max(2, width - 1))
    d.line([(cx + r * 0.3, cy), (cx + r * 1.45, cy)], fill=color, width=max(2, width - 1))
    d.line([(cx, cy - r * 1.45), (cx, cy - r * 0.3)], fill=color, width=max(2, width - 1))
    d.line([(cx, cy + r * 0.3), (cx, cy + r * 1.45)], fill=color, width=max(2, width - 1))


def style_target(q, seed):
    rng = np.random.default_rng(seed)
    a = noise_bg((10, 10, 11), (3, 3, 4), seed, 2.0)
    a = radial(a, W / 2, H * 0.33, 520, (40, 40, 44), 0.6)
    img = to_img(vignette(a, 0.6))

    # scope + chart
    cx, cy, R = W / 2, H * 0.33, 250
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    # andar ka chart (safed/grey candles)
    cs = candles(rng, 26, cx - 200, cx + 200, cy + 120, cy - 120, 11)
    for i, (x, o, c, hi, lo) in enumerate(cs):
        dist = math.hypot(x - cx, (o + c) / 2 - cy)
        if dist > R - 20:
            continue
        col = (235, 235, 235, 230) if c < o else (130, 130, 135, 230)
        d.line([(x, hi), (x, lo)], fill=col, width=2)
        d.rectangle([x - 5, min(o, c), x + 5, max(o, c) + 2], fill=col)
    # dial ki lakeerein
    for k in range(60):
        ang = k * math.pi / 30
        r0 = R + (6 if k % 5 else 0)
        r1 = R + 20
        d.line([(cx + r0 * math.cos(ang), cy + r0 * math.sin(ang)), (cx + r1 * math.cos(ang), cy + r1 * math.sin(ang))],
               fill=(200, 200, 205, 160 if k % 5 else 230), width=2)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(210, 210, 215, 200), width=3)
    img = add_glow(img, lay, 4, 0.35)
    red = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    target(ImageDraw.Draw(red), cx, cy, 64, RED + (255,), 4)
    img = add_glow(img, red, 14, 1.4)

    # bara lafz, "O" ki jagah nishana
    word = q["word"].upper()
    f = F("black", 150)
    tw = text_w(word, f, 4)
    x = W / 2 - tw / 2
    ty = H * 0.615
    d = ImageDraw.Draw(img)
    redl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(redl)
    asc = f.getbbox("H")
    capc = ty + (asc[1] + asc[3]) / 2
    used_o = False
    for ch in word:
        cw = f.getlength(ch)
        if ch == "O" and not used_o:
            target(rd, x + cw / 2, capc, cw * 0.36, RED + (255,), 6)
            used_o = True
        else:
            d.text((round(x), round(ty)), ch, font=f, fill=(242, 242, 242))
        x += cw + 4
    img = add_glow(img, redl, 10, 1.2)
    d = ImageDraw.Draw(img)
    # beech ki line + chhota lafz
    fy = ty + asc[3] + 40
    fm = F("med", 34)
    mid = q["mid"].upper()
    mw = text_w(mid, fm, 12)
    draw_tracked(d, (W / 2, fy), mid, fm, (225, 225, 225), 12, "c")
    d.line([(W / 2 - mw / 2 - 160, fy + 21), (W / 2 - mw / 2 - 30, fy + 21)], fill=(200, 200, 200), width=2)
    d.line([(W / 2 + mw / 2 + 30, fy + 21), (W / 2 + mw / 2 + 160, fy + 21)], fill=(200, 200, 200), width=2)
    fr = F("bold", 58)
    draw_tracked(d, (W / 2, fy + 70), q["end"].upper(), fr, RED, 14, "c")
    return brand(img, color=(200, 200, 200))


# ---------------- 3) Neon Acrostic ----------------
def ribbon(lay, rng, pts_fn, c0, c1, strands=70, width=2):
    d = ImageDraw.Draw(lay)
    for s in range(strands):
        off = rng.normal(0, 1)
        pts = []
        for t in np.linspace(0, 1, 160):
            x, y = pts_fn(t, off)
            pts.append((x, y))
        for i in range(len(pts) - 1):
            t = i / (len(pts) - 1)
            col = tuple(int(c0[k] * (1 - t) + c1[k] * t) for k in range(3))
            al = int(150 * math.sin(math.pi * t) ** 0.8 * (0.35 + 0.65 * math.exp(-off * off)))
            d.line([pts[i], pts[i + 1]], fill=col + (al,), width=width)


def style_neon(q, seed):
    rng = np.random.default_rng(seed)
    a = noise_bg((6, 8, 12), (2, 3, 5), seed, 2.0)
    img = to_img(vignette(a, 0.4))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ORG, CY, GR = (255, 150, 30), (40, 200, 230), (40, 230, 150)
    ribbon(lay, rng, lambda t, o: (120 + 760 * t + 30 * o, -60 + 700 * t + 90 * math.sin(t * 4 + o * 0.3) + 18 * o), ORG, CY)
    ribbon(lay, rng, lambda t, o: (980 - 520 * t + 30 * o, 640 + 760 * t + 70 * math.sin(t * 5 + o * 0.4) + 16 * o), CY, GR)
    img = add_glow(img, lay, 10, 1.6)
    # chingariyan
    sp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sp)
    for _ in range(260):
        x, y = rng.uniform(80, W - 60), rng.uniform(40, H - 120)
        t = y / H
        col = tuple(int(ORG[k] * (1 - t) + GR[k] * t) for k in range(3))
        r = rng.uniform(0.6, 2.0)
        sd.ellipse([x - r, y - r, x + r, y + r], fill=col + (int(rng.uniform(60, 200)),))
    img = add_glow(img, sp, 3, 0.8)

    # likhai ke peeche halka andhera, taake lakeerein likhai par na chadhein
    pa = np.array(img, float)
    yy, xx = np.mgrid[0:H, 0:W]
    dx = np.clip(np.maximum(200 - xx, xx - 880) / 120, 0, 1)
    dy = np.clip(np.maximum(280 - yy, yy - 1080) / 120, 0, 1)
    k = 1 - np.maximum(dx, dy)
    pa = pa * (1 - 0.72 * k[..., None]) + 4 * k[..., None]
    img = to_img(pa)
    word = q["word"].upper()
    f = F("black", 170 if len(word) <= 5 else 136)
    lay = gradient_text((W, H), word, f, [ORG, (255, 196, 70), CY, GR], track=6, anchor="c", xy=(W / 2, 300), vertical=False)
    img = add_glow(img, lay, 14, 0.7)
    d = ImageDraw.Draw(img)
    rows = q["rows"]
    fl, fw = F("black", 64), F("med", 38)
    y0 = 560
    for i, (letter, wd) in enumerate(rows):
        t = i / max(len(rows) - 1, 1)
        col = tuple(int((ORG if t < .5 else CY)[k] * (1 - (t * 2 % 1 if t < 1 else 1)) + (CY if t < .5 else GR)[k] * (t * 2 % 1 if t < 1 else 1)) for k in range(3))
        y = y0 + i * 92
        d.text((250, y), letter, font=fl, fill=col)
        d.line([(320, y + 12), (320, y + 66)], fill=(200, 200, 210), width=2)
        draw_tracked(d, (348, y + 16), wd.upper(), fw, (236, 238, 242), 8)
    fs = F("semi", 28)
    parts = q["tag"]
    cols = [CY, ORG, CY, GR, ORG, CY]
    tws = [text_w(p, fs, 6) for p in parts]
    total = sum(tws) + 26 * (len(parts) - 1)
    x = W / 2 - total / 2
    ty = y0 + len(rows) * 92 + 50
    for p, c, w in zip(parts, cols, tws):
        draw_tracked(d, (x, ty), p, fs, c, 6)
        x += w + 26
    return brand(img, color=(210, 214, 222))


# ---------------- 4) Mono Reflection ----------------
def style_mono(q, seed):
    rng = np.random.default_rng(seed)
    a = noise_bg((22, 22, 23), (6, 6, 7), seed, 2.4)
    a = radial(a, W * 0.5, H * 0.52, 640, (40, 40, 42), 0.7)
    img = to_img(vignette(a, 0.55))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    base = H * 0.62
    cs = candles(rng, 74, 30, W - 30, base, base - 210, 14)
    # beech mein lehar (pehle neeche, phir upar)
    for i, (x, o, c, hi, lo) in enumerate(cs):
        d.line([(x, hi), (x, lo)], fill=(240, 240, 240, 220), width=2)
        d.rectangle([x - 4, min(o, c), x + 4, max(o, c) + 2], fill=(245, 245, 245, 235) if c < o else (150, 150, 150, 220))
        vh = abs(rng.normal(30, 18))
        d.rectangle([x - 3, base + 70 - vh, x + 3, base + 70], fill=(200, 200, 200, 110))
    sharp = lay
    # focus: kinare dhundle
    blur = lay.filter(ImageFilter.GaussianBlur(5))
    xx = np.abs(np.arange(W) - W * 0.56) / (W * 0.5)
    m = np.clip(xx * 1.6 - 0.25, 0, 1)
    mix = (np.array(sharp, float) * (1 - m[None, :, None]) + np.array(blur, float) * m[None, :, None]).astype(np.uint8)
    lay = Image.fromarray(mix, "RGBA")
    img = add_glow(img, lay, 7, 0.55)
    # aks (reflection)
    refl = lay.crop((0, int(base - 260), W, int(base + 72))).transpose(Image.FLIP_TOP_BOTTOM).filter(ImageFilter.GaussianBlur(3))
    ra = np.array(refl, float)
    fade = np.linspace(0.42, 0, ra.shape[0])[:, None]
    ra[..., 3] *= fade
    refl = Image.fromarray(ra.astype(np.uint8), "RGBA")
    img.paste(refl, (0, int(base + 74)), refl)
    d = ImageDraw.Draw(img)
    d.line([(0, base + 73), (W, base + 73)], fill=(70, 70, 72), width=1)

    # quote upar
    f = F("serif", 64)
    lines = q["lines"]
    y = 200
    for ln in lines:
        d.text((W / 2, y), ln, font=f, fill=(244, 244, 244), anchor="mt")
        y += 82
    d.line([(W / 2 - 40, y + 26), (W / 2 + 40, y + 26)], fill=(180, 180, 180), width=2)
    return brand(img, color=(200, 200, 200))


# ---------------- 5) Summit Path ----------------
def style_summit(q, seed):
    rng = np.random.default_rng(seed)
    a = noise_bg((14, 16, 14), (4, 5, 4), seed, 2.4)
    cx, cy, rr = W * 0.5, H * 0.56, 300
    y, x = np.mgrid[0:H, 0:W]
    dd = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    a += (np.clip(1 - dd / rr, 0, 1) ** 1.4)[..., None] * np.array([150, 150, 130])[None, None, :] * 0.55
    ring = np.exp(-((dd - rr - 28) / 22) ** 2)
    a = a * (1 - 0.5 * ring[..., None]) + ring[..., None] * 26
    a, ridge = mountains(a, rng, H - 230, cx, cy + 10, (9, 10, 9), rim=(160, 170, 150), rim_amt=0.35)
    img = to_img(vignette(a, 0.5))
    # chamakti pagdandi choti tak
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    GREEN = (190, 240, 60)
    pts = [(cx - 40, H - 150)]
    yy = H - 150
    k = 0
    while yy > cy + 30:
        yy -= rng.uniform(40, 70)
        xx = cx + (70 if k % 2 == 0 else -60) * max(0.0, (yy - cy) / (H - cy)) ** 1.2
        pts.append((xx, yy))
        k += 1
    pts.append((cx, ridge[int(cx)] + 4))
    d.line(pts, fill=GREEN + (255,), width=3)
    # daayen taraf candles
    cs = candles(rng, 24, W * 0.62, W - 50, H * 0.62, H * 0.25, 13)
    for x2, o, c, hi, lo in cs:
        col = GREEN + (235,) if c < o else (235, 240, 225, 200)
        d.line([(x2, hi), (x2, lo)], fill=col, width=2)
        d.rectangle([x2 - 5, min(o, c), x2 + 5, max(o, c) + 2], fill=col)
    d.ellipse([cs[-1][0] - 6, cs[-1][2] - 6, cs[-1][0] + 6, cs[-1][2] + 6], fill=(255, 255, 200, 255))
    img = add_glow(img, lay, 9, 1.4)
    d = ImageDraw.Draw(img)
    f = F("xbold", 96)
    y = 150
    for wd in q["lines"]:
        d.text((80, y), wd.upper(), font=f, fill=(238, 238, 232))
        y += 104
    d.line([(84, y + 26), (164, y + 26)], fill=GREEN, width=4)
    fs = F("semi", 30)
    for i, ln in enumerate(q["sub"]):
        draw_tracked(d, (84, y + 52 + i * 42), ln.upper(), fs, GREEN, 4)
    return brand(img, color=(206, 210, 200))


STYLES = {"gold": style_gold, "target": style_target, "neon": style_neon, "mono": style_mono, "summit": style_summit}


def make(q, seed=1):
    img = STYLES[q["style"]](q, seed)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=94, subsampling=0, optimize=True)
    return out.getvalue()
