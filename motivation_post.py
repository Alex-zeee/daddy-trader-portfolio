"""Daddy Trader — rozana ek motivation post Facebook page ke "Daddy Trader Motivation" album mein.

GitHub Actions (motivation.yml) ise roz shaam ~7 baje (Pakistan) chalata hai.
Har din agla jumla aur agla andaaz; tasveer har dafa nayi banti hai.

Khud chala kar dekhna (post nahi hota):  DRY_RUN=1 python motivation_post.py  ->  motivation-today.jpg
"""
import datetime, os, sys

import fb_post
import motivation_card
import motivation_content as content

START = datetime.date(2026, 11, 8)  # pehli post ka din
PK = datetime.timezone(datetime.timedelta(hours=5))


def today():
    return datetime.datetime.now(PK).date()


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
    fb_post.post(img, cap, album="motivation", filename="daddy-trader-motivation.jpg", ctype="image/jpeg")


if __name__ == "__main__":
    main()
    sys.exit(0)
