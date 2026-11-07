"""Daddy Trader — tasveer aur likhai Facebook page ke sahi album mein post karna (Meta Graph API).

- wa_post.py: har naye signal / TP HIT / SL HIT ka card  -> "Daddy Trader Signals" album
- motivation_post.py: rozana ki motivation tasveer        -> "Daddy Trader Motivation" album
Album mein daali tasveer page ki timeline par bhi nazar aati hai.

GitHub Secret (Settings -> Secrets -> Actions):
  FB_PAGE_TOKEN  Daddy Trader page ka Page access token (kabhi expire na hone wala)
Token na ho to ye kuch nahi karta, baqi bot chalta rehta hai.
"""
import json, os, urllib.parse, urllib.request, urllib.error, uuid

GRAPH = "https://graph.facebook.com/v25.0"
TOKEN = os.environ.get("FB_PAGE_TOKEN", "").strip()
# Page token ke saath "me" khud Daddy Trader page hi hota hai
PAGE = os.environ.get("FB_PAGE_ID", "").strip() or "me"

# album ka naam (page par jo likha hai) aur us ki ID (naam na mile to ye)
ALBUMS = {
    "signals": ("Daddy Trader Signals", "122201334686860036"),
    "motivation": ("Daddy Trader Motivation", "122201334482860036"),
}


def _send(req):
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read() or b"{}")


def album_id(kind):
    name, fallback = ALBUMS[kind]
    try:
        url = GRAPH + "/" + PAGE + "/albums?" + urllib.parse.urlencode(
            {"fields": "id,name", "limit": 100, "access_token": TOKEN})
        for a in _send(urllib.request.Request(url)).get("data", []):
            if str(a.get("name", "")).strip().lower() == name.lower():
                return a["id"]
    except Exception as e:
        print("facebook: album list nahi mili", e)
    return fallback


def photo(img, message, target, filename, ctype):
    b = uuid.uuid4().hex
    body = b""
    # album mein "caption", page par "message" — dono bhej dete hain
    for k, v in (("caption", message), ("message", message), ("access_token", TOKEN)):
        body += ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (b, k, v)).encode()
    body += ('--%s\r\nContent-Disposition: form-data; name="source"; filename="%s"\r\n'
             'Content-Type: %s\r\n\r\n' % (b, filename, ctype)).encode() + img + b"\r\n"
    body += ("--%s--\r\n" % b).encode()
    req = urllib.request.Request(GRAPH + "/" + target + "/photos", data=body, method="POST",
                                 headers={"content-type": "multipart/form-data; boundary=" + b})
    return _send(req)


def text(message):
    data = urllib.parse.urlencode({"message": message, "access_token": TOKEN}).encode()
    return _send(urllib.request.Request(GRAPH + "/" + PAGE + "/feed", data=data, method="POST"))


def _err(e):
    if isinstance(e, urllib.error.HTTPError):
        return "%s %s" % (e.code, e.read()[:300])
    return str(e)


def post(img, message, album="signals", filename="daddy-trader-signal.png", ctype="image/png"):
    """Tasveer album mein; album na chale to page par; tasveer na jaye to sirf likhai."""
    if not TOKEN:
        return
    message = message.replace("*", "")  # WhatsApp wale bold nishan Facebook par nahi chahiye
    if img:
        targets = ([album_id(album)] if album in ALBUMS else []) + [PAGE]
        for t in targets:
            try:
                res = photo(img, message, t, filename, ctype)
                print("facebook: posted", "album " + album if t != PAGE else "page", res.get("post_id") or res.get("id"))
                return
            except Exception as e:
                print("facebook: tasveer error (%s):" % ("album" if t != PAGE else "page"), _err(e))
    try:
        res = text(message)
        print("facebook: posted text", res.get("id"))
    except Exception as e:
        print("facebook: error", _err(e))
