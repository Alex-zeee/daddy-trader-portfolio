"""Daddy Trader — USD news se pehle ka card: sirf "NEWS SELL" ya "NEWS BUY".

Wahi card jo signal ke liye hai (signal-card-bg.jpg). Neeche sirf link (links.py).
Facebook page ke Signals album, WhatsApp channel aur Ali ke number par jata hai.
Chalana: GitHub -> Actions -> "News Post" -> Run workflow -> side: sell ya buy.
Khud dekhna:  python news_post.py test   ->  news-card-test-sell.png / -buy.png
"""
import base64, io, os, sys, time

from PIL import Image, ImageDraw

import links
import signal_card as sc


COLOR = {"BUY": (56, 189, 248), "SELL": (239, 48, 48)}   # BUY aasmani neela, SELL laal


def make(side):
    """side: "SELL" ya "BUY" -> card ki PNG bytes."""
    text = "NEWS " + side
    img = Image.open(sc.BG).convert("RGB")
    d = ImageDraw.Draw(img)
    f = sc.font(52)                      # signal card ki tarah baen taraf, logo se pehle
    w = d.textlength(text, font=f)
    box = d.textbbox((0, 0), text, font=f)
    h = box[3] - box[1]
    dot, gap = 24, 26
    x = sc.X0 + 70
    y = (sc.Y0 + sc.Y1) / 2 - (dot + gap + h) / 2
    cx = x + w / 2
    d.ellipse((cx - dot / 2, y, cx + dot / 2, y + dot), fill=sc.ORANGE)
    d.ellipse((cx - dot / 2 + 5, y + 4, cx + dot / 2 - 9, y + dot / 2 - 2), fill=sc.SHINE)
    d.text((round(x), round(y + dot + gap - box[1])), text, font=f, fill=COLOR[side])
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


def main():
    side = os.environ.get("SIDE", "").strip().upper()
    if side not in ("SELL", "BUY"):
        print("SIDE sell ya buy hona chahiye, mila:", repr(side))
        return 1
    png = make(side)
    import fb_post, wa_post
    if fb_post.TOKEN:
        fb_post.post(png, links.footer("facebook"), album="signals", filename="daddy-trader-news.png")
    else:
        print("facebook token nahi — skip")
    if not wa_post.TOKEN:
        print("whatsapp token nahi — skip")
        return 0
    media = "data:image/png;base64," + base64.b64encode(png).decode()
    targets = [wa_post.CHANNEL] + [n + "@s.whatsapp.net" for n in wa_post.NOTIFY if n.isdigit()]
    for k, to in enumerate(targets):
        if k:
            time.sleep(15)  # WhatsApp spam se bachne ke liye faasla
        who = "channel" if to == wa_post.CHANNEL else "number"
        try:
            wa_post.call("POST", "/messages/image", {"to": to, "media": media, "caption": links.footer("whatsapp")})
            print("whatsapp: posted NEWS", side, "->", who)
        except Exception as e:
            detail = getattr(e, "read", lambda: b"")()[:300]
            print("whatsapp: error ->", who, getattr(e, "code", ""), detail or e)
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["test"]:
        for s in ("SELL", "BUY"):
            open("news-card-test-%s.png" % s.lower(), "wb").write(make(s))
            print("news-card-test-%s.png bana diya" % s.lower())
        sys.exit(0)
    sys.exit(main())
