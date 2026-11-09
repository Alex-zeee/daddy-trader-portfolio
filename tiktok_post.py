"""Daddy Trader — tasveer TikTok par (photo post), Cloudflare worker "daddytrader-tiktok" ke zariye.

GitHub robot apni pehchan GitHub ke OIDC token se karata hai (workflow mein permissions: id-token: write),
is liye yahan koi chabi/password nahi rakhna padta. TikTok ki chabi Cloudflare worker ke paas hai.
Card aap ke TikTok inbox mein draft ban kar jata hai: TikTok notification deta hai, aap khud "Post" dabate hain
(TikTok bina audit ke seedhi public post nahi karne deta).

  python tiktok_post.py test   -> post-now/ folder ki tasveerein TikTok par (test ke liye)
"""
import base64, glob, io, json, os, sys, time, urllib.error, urllib.request

import links

WORKER = "https://daddytrader-tiktok.blankweb1.workers.dev"
AUD = "daddytrader-tiktok"
UA = "Mozilla/5.0 (compatible; DaddyTraderBot/1.0; +https://daddytrader.live)"


def _oidc():
    url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    tok = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not url or not tok:
        return ""
    req = urllib.request.Request(url + "&audience=" + AUD, headers={"authorization": "bearer " + tok, "user-agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["value"]


def jpeg(img):
    """TikTok sirf JPEG/WEBP leta hai, zyada se zyada 1080p."""
    from PIL import Image
    im = Image.open(io.BytesIO(img)).convert("RGB")
    if im.width > 1920 or im.height > 1080:
        im.thumbnail((1920, 1080))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=92, optimize=True)
    return b.getvalue()


def _call(path, payload, jwt):
    req = urllib.request.Request(WORKER + path, data=json.dumps(payload).encode(), method="POST", headers={
        "content-type": "application/json", "authorization": "Bearer " + jwt, "user-agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": "%s %s" % (e.code, e.read()[:300])}


def post(images, title="", description=None):
    """images: PNG/JPEG bytes ki list. description na ho to sirf link (Facebook, website, channel)."""
    try:
        jwt = _oidc()
    except Exception as e:
        print("tiktok: GitHub pehchan nahi mili", e)
        return None
    if not jwt:
        print("tiktok: GitHub id-token nahi (workflow mein permissions: id-token: write chahiye) — skip")
        return None
    if description is None:
        description = links.footer("tiktok")
    try:
        imgs = [base64.b64encode(jpeg(i)).decode() for i in images]
    except Exception as e:
        print("tiktok: tasveer JPEG nahi bani", e)
        return None
    d = _call("/post", {"title": title, "description": description, "images": imgs}, jwt)
    if d.get("ok"):
        print("tiktok: posted (%s) publish_id %s" % (d.get("privacy"), d.get("publish_id")))
    else:
        print("tiktok: error", d.get("error"))
    return d


def status(publish_id):
    try:
        return _call("/status", {"publish_id": publish_id}, _oidc())
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__" and sys.argv[1:2] == ["test"]:
    files = sorted(p for p in glob.glob("post-now/*") if p.lower().endswith((".png", ".jpg", ".jpeg")))
    print(len(files), "tasveer:", ", ".join(os.path.basename(f) for f in files))
    res = post([open(f, "rb").read() for f in files]) if files else None
    if res and res.get("publish_id"):
        for _ in range(8):  # TikTok ko tasveer uthane mein thora waqt lagta hai
            time.sleep(10)
            st = status(res["publish_id"])
            s = (st.get("data") or {}).get("status")
            print("tiktok status:", s or st)
            if s in ("PUBLISH_COMPLETE", "FAILED", "SEND_TO_USER_INBOX"):
                break
