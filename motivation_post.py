"""Daddy Trader — rozana ek motivation post Facebook page ke "Daddy Trader Motivation" album mein.

Cloudflare ghari (trigger-worker) roz shaam 7:01 baje (Pakistan) motivation.yml chalati hai;
GitHub ka apna schedule backup hai. 12 ghante mein sirf aik post hoti hai.
Har din agla jumla aur agla andaaz; tasveer har dafa nayi banti hai.

Khud chala kar dekhna (post nahi hota):  DRY_RUN=1 python motivation_post.py  ->  motivation-today.jpg
"""
import datetime, os, sys, urllib.parse, urllib.request

import fb_post
import motivation_card
import motivation_content as content

START = datetime.date(2026, 11, 8)  # pehli post ka din
PK = datetime.timezone(datetime.timedelta(hours=5))


def today():
    return datetime.datetime.now(PK).date()


def posted_recently(hours=12):
    """Pichle 12 ghante mein robot ki motivation post album mein ja chuki ho to True (do dafa post na ho).
    Sirf robot ki post ginte hain (caption mein #DaddyTrader), album ki cover tasveer nahi."""
    try:
        aid = fb_post.album_id("motivation")
        url = fb_post.GRAPH + "/" + aid + "/photos?" + urllib.parse.urlencode(
            {"fields": "created_time,name", "limit": 10, "access_token": fb_post.TOKEN})
        now = datetime.datetime.now(datetime.timezone.utc)
        for ph in fb_post._send(urllib.request.Request(url)).get("data", []):
            t = datetime.datetime.strptime(ph["created_time"], "%Y-%m-%dT%H:%M:%S%z")
            if "#DaddyTrader" in ph.get("name", "") and now - t < datetime.timedelta(hours=hours):
                return True
    except Exception as e:
        print("facebook: pichli post check nahi ho saki", e)
    return False


def main():
    n = (today() - START).days
    p = content.POSTS[n % len(content.POSTS)]
    img = motivation_card.make(p, seed=1000 + n)
    with open("motivation-today.jpg", "wb") as fh:
        fh.write(img)
    cap = content.caption(p)
    print("din", n, "| andaaz:", p["style"], "|", p["en"])
    if os.environ.get("DRY_RUN", "") == "1":
        print("DRY_RUN: sirf tasveer bani, post nahi kiya\n" + cap)
        return
    if not fb_post.TOKEN:
        print("facebook token nahi — skip")
        return
    now = datetime.datetime.now(PK)
    # Cloudflare ghari roz 7:01 baje robot chalati hai. GitHub ka apna schedule sirf backup hai,
    # aur wo ghanton late ho sakta hai: raat 12 ke baad chale to post nahi karta.
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and not 18 <= now.hour <= 23:
        print("GitHub schedule late chala (%s) — post nahi kiya" % now.strftime("%H:%M"))
        return
    if posted_recently():
        print("pichle 12 ghante mein motivation post ja chuki hai — dobara nahi")
        return
    fb_post.post(img, cap, album="motivation", filename="daddy-trader-motivation.jpg", ctype="image/jpeg")


if __name__ == "__main__":
    main()
    sys.exit(0)
