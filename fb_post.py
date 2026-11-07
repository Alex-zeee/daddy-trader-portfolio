"""Daddy Trader — signal ka card Facebook page par post karna (Meta Graph API).

wa_post.py har naye signal / TP HIT / SL HIT par ise card ki tasveer aur likhai deta hai.

GitHub Secret (Settings -> Secrets -> Actions):
  FB_PAGE_TOKEN  Daddy Trader page ka Page access token (kabhi expire na hone wala)
Token na ho to ye kuch nahi karta, baqi bot chalta rehta hai.
"""
import json, os, urllib.parse, urllib.request, urllib.error, uuid

GRAPH = "https://graph.facebook.com/v25.0"
TOKEN = os.environ.get("FB_PAGE_TOKEN", "").strip()
# Page token ke saath "me" khud Daddy Trader page hi hota hai
PAGE = os.environ.get("FB_PAGE_ID", "").strip() or "me"


def _send(req):
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read() or b"{}")


def photo(png, message):
    b = uuid.uuid4().hex
    body = b""
    for k, v in (("message", message), ("access_token", TOKEN)):
        body += ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (b, k, v)).encode()
    body += ('--%s\r\nContent-Disposition: form-data; name="source"; filename="daddy-trader-signal.png"\r\n'
             'Content-Type: image/png\r\n\r\n' % b).encode() + png + b"\r\n"
    body += ("--%s--\r\n" % b).encode()
    req = urllib.request.Request(GRAPH + "/" + PAGE + "/photos", data=body, method="POST",
                                 headers={"content-type": "multipart/form-data; boundary=" + b})
    return _send(req)


def text(message):
    data = urllib.parse.urlencode({"message": message, "access_token": TOKEN}).encode()
    return _send(urllib.request.Request(GRAPH + "/" + PAGE + "/feed", data=data, method="POST"))


def post(png, message):
    """Card ke saath post; card na ho ya na jaye to sirf likhai."""
    if not TOKEN:
        return
    message = message.replace("*", "")  # WhatsApp wale bold nishan Facebook par nahi chahiye
    if png:
        try:
            res = photo(png, message)
            print("facebook: posted card", res.get("post_id") or res.get("id"))
            return
        except urllib.error.HTTPError as e:
            print("facebook: card error", e.code, e.read()[:300], "- ab sirf likhai")
        except Exception as e:
            print("facebook: card error", e, "- ab sirf likhai")
    try:
        res = text(message)
        print("facebook: posted", res.get("id"))
    except urllib.error.HTTPError as e:
        print("facebook: error", e.code, e.read()[:300])
    except Exception as e:
        print("facebook: error", e)
