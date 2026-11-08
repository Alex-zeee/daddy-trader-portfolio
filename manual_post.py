"""Daddy Trader — haath se aik post: post-now/ folder ki tasveerein + post-now/caption.txt

Facebook page ke "Daddy Trader Signals" album, WhatsApp channel aur Ali ke number par jati hai.
Chalana: GitHub -> Actions -> "Manual Post" -> Run workflow.
Likhai (caption) pehli tasveer ke saath jati hai; baqi tasveerein us ke baad.
Haath wali post mein link khud nahi lagte; jo likhai caption.txt mein ho wahi jati hai.
"""
import base64, glob, os, sys, time

import fb_post
import wa_post

DIR = "post-now"


def kind(path):
    return "image/png" if path.lower().endswith(".png") else "image/jpeg"


def main():
    imgs = sorted(p for p in glob.glob(DIR + "/*") if p.lower().endswith((".png", ".jpg", ".jpeg")))
    if not imgs:
        print("post-now folder mein koi tasveer nahi")
        return
    cap_file = os.path.join(DIR, "caption.txt")
    cap = open(cap_file, encoding="utf-8").read().strip() if os.path.exists(cap_file) else ""
    data = [(os.path.basename(p), kind(p), open(p, "rb").read()) for p in imgs]
    print(len(data), "tasveer:", ", ".join(n for n, _, _ in data), "| likhai:", len(cap), "harf")

    if os.environ.get("FACEBOOK", "yes").strip().lower() == "yes":
        if not fb_post.TOKEN:
            print("facebook token nahi — skip")
        for i, (name, ctype, img) in enumerate(data if fb_post.TOKEN else []):
            fb_post.post(img, cap if i == 0 else "", album="signals", filename=name, ctype=ctype)

    if os.environ.get("WHATSAPP", "yes").strip().lower() == "yes":
        if not wa_post.TOKEN:
            print("whatsapp token nahi — skip")
            return
        targets = [wa_post.CHANNEL] + [n + "@s.whatsapp.net" for n in wa_post.NOTIFY if n.isdigit()]
        first = True
        for to in targets:
            who = "channel" if to == wa_post.CHANNEL else "number"
            for i, (name, ctype, img) in enumerate(data):
                if not first:
                    time.sleep(15)  # WhatsApp spam se bachne ke liye faasla
                first = False
                body = {"to": to, "media": "data:%s;base64,%s" % (ctype, base64.b64encode(img).decode())}
                if i == 0 and cap:
                    body["caption"] = cap
                try:
                    wa_post.call("POST", "/messages/image", body)
                    print("whatsapp: posted", name, "->", who)
                except Exception as e:
                    detail = getattr(e, "read", lambda: b"")()[:300]
                    print("whatsapp: error", name, "->", who, getattr(e, "code", ""), detail or e)


if __name__ == "__main__":
    main()
    sys.exit(0)
