"""Daddy Trader — har post ke neeche baqi jagahon ke link (us jagah ka apna link nahi).

  WhatsApp par:  website, Facebook, TikTok
  Facebook par:  WhatsApp channel, website, TikTok
  TikTok par:    Facebook, website, WhatsApp channel
"""
WEBSITE = "https://daddytrader.live"
FACEBOOK = "https://www.facebook.com/profile.php?id=61575801080475"
TIKTOK = "https://www.tiktok.com/@daddytrader_0"
CHANNEL = "https://whatsapp.com/channel/0029Vb8tas7BFLga0KUzOI0A"

_LINE = {
    "website": "🌐 Website: " + WEBSITE,
    "facebook": "📘 Facebook: " + FACEBOOK,
    "tiktok": "🎵 TikTok: " + TIKTOK,
    "channel": "📲 WhatsApp channel: " + CHANNEL,
}
_ORDER = {
    "whatsapp": ("website", "facebook", "tiktok"),
    "facebook": ("channel", "website", "tiktok"),
    "tiktok": ("facebook", "website", "channel"),
}


def footer(platform):
    """Us platform ki post ke neeche lagne wale link (har link alag line par)."""
    return "\n".join(_LINE[k] for k in _ORDER[platform])


def caption(text, platform):
    """Likhai + link. Aakhir mein hashtags (#...) hon to link un se pehle aate hain."""
    lines = text.strip().split("\n")
    tags = []
    while lines and lines[-1].strip().startswith("#"):
        tags.insert(0, lines.pop())
    body = "\n".join(lines).strip()
    parts = [body, footer(platform)] if body else [footer(platform)]
    if tags:
        parts.append("\n".join(tags))
    return "\n\n".join(parts)
