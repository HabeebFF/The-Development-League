"""Turning one page view request into a stored row: who (anonymously), what, from where."""

from __future__ import annotations

import hashlib
import hmac
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from .models import PageView

# Crawlers, link previews (WhatsApp, Discord...) and scripts. Real browsers never say these.
BOT = re.compile(
    r"bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp|telegram|headless|lighthouse"
    r"|curl|wget|python|httpclient|okhttp|java/|go-http|axios|node-fetch|monitor|uptime",
    re.I,
)

# Website hosts (ending) and phone app ids (android-app://...) to a source name.
HOSTS = {
    "whatsapp.com": "WhatsApp",
    "wa.me": "WhatsApp",
    "discord.com": "Discord",
    "discordapp.com": "Discord",
    "discord.gg": "Discord",
    "t.co": "X",
    "x.com": "X",
    "twitter.com": "X",
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "fb.me": "Facebook",
    "messenger.com": "Facebook",
    "instagram.com": "Instagram",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "tiktok.com": "TikTok",
    "t.me": "Telegram",
    "telegram.org": "Telegram",
    "reddit.com": "Reddit",
    "snapchat.com": "Snapchat",
    "bing.com": "Bing",
    "duckduckgo.com": "DuckDuckGo",
    "yahoo.com": "Yahoo",
}
APPS = {
    "com.whatsapp": "WhatsApp",
    "com.whatsapp.w4b": "WhatsApp",
    "com.discord": "Discord",
    "org.telegram.messenger": "Telegram",
    "com.instagram.android": "Instagram",
    "com.facebook.katana": "Facebook",
    "com.facebook.orca": "Facebook",
    "com.twitter.android": "X",
    "com.zhiliaoapp.musically": "TikTok",
    "com.google.android.youtube": "YouTube",
    "com.google.android.googlequicksearchbox": "Google",
    "com.google.android.gm": "Gmail",
}
# ?ref=... in a shared link, e.g. https://site/standings?ref=wa
REFS = {name.lower(): name for name in set(HOSTS.values()) | set(APPS.values())}
REFS |= {"wa": "WhatsApp", "twitter": "X", "fb": "Facebook", "ig": "Instagram", "tg": "Telegram"}


def is_bot(user_agent: str) -> bool:
    return not user_agent or bool(BOT.search(user_agent))


def device(ua: str) -> str:
    if re.search(r"iPad|Tablet|PlayBook|Silk|Kindle", ua) or (
        "Android" in ua and "Mobile" not in ua
    ):
        return "tablet"
    if re.search(r"Mobi|iPhone|iPod|Android|Windows Phone", ua):
        return "phone"
    return "desktop"


def browser(ua: str) -> str:
    for pattern, name in (
        (r"Edg(e|A|iOS)?/", "Edge"),
        (r"OPR/|Opera|OPX/", "Opera"),
        (r"SamsungBrowser/", "Samsung Internet"),
        (r"UCBrowser/", "UC Browser"),
        (r"MiuiBrowser/|XiaoMi/", "Mi Browser"),
        (r"FBAN|FBAV|Instagram", "In-app"),
        (r"Firefox/|FxiOS/", "Firefox"),
        (r"Chrome/|CriOS/", "Chrome"),
        (r"Safari/", "Safari"),
    ):
        if re.search(pattern, ua):
            return name
    return "Other"


def operating_system(ua: str) -> str:
    for pattern, name in (
        (r"Android", "Android"),
        (r"iPhone|iPad|iPod", "iOS"),
        (r"Windows", "Windows"),
        (r"CrOS", "ChromeOS"),
        (r"Mac OS X|Macintosh", "macOS"),
        (r"Linux", "Linux"),
    ):
        if re.search(pattern, ua):
            return name
    return "Other"


def source(referrer: str, ref: str, own_host: str) -> str:
    """Where the visit came from; "" means typed in, a bookmark, or an app that hides it."""
    ref = re.sub(r"[^\w .-]", "", ref or "").strip()[:40]
    if ref:
        return REFS.get(ref.lower(), ref.title())
    if not referrer:
        return ""
    parts = urlsplit(referrer.strip())
    if parts.scheme == "android-app":
        return APPS.get(parts.netloc.lower(), parts.netloc[:60])
    host = (parts.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    if not host or host == own_host.lower().split(":")[0]:
        return ""
    if re.match(r"^(.+\.)?google\.[a-z.]+$", host):
        return "Google"
    for suffix, name in HOSTS.items():
        if host == suffix or host.endswith("." + suffix):
            return name
    return host[:60]


def clean_path(path: str) -> str | None:
    path = (path or "").split("?")[0].split("#")[0].strip()
    if not path.startswith("/") or path.startswith("//") or path.startswith("/api/"):
        return None
    path = re.sub(r"/{2,}", "/", path)
    if len(path) > 1:
        path = path.rstrip("/")
    return path[:200]


def client_ip(request) -> str:
    # Caddy (and the Next.js proxy) put the visitor's address first.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")


def visitor_code(ip: str, user_agent: str, day) -> str:
    """Same person, same day: same code. A new day gives a new code; the IP is not kept."""
    message = f"{day.isoformat()}|{ip}|{user_agent}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()[:16]


def audience(user) -> str:
    if not user or not user.is_authenticated:
        return PageView.Audience.GUEST
    if user.is_league_staff:
        return PageView.Audience.STAFF
    if user.memberships.filter(is_active=True).exists():
        return PageView.Audience.MEMBER
    return PageView.Audience.GUEST


def _league_tz():
    return ZoneInfo(settings.ANALYTICS_TIME_ZONE)


def record(request, path: str, referrer: str = "", ref: str = "") -> PageView | None:
    """Store one page view, or nothing for bots and bad paths."""
    ua = request.META.get("HTTP_USER_AGENT", "")[:500]
    path = clean_path(path)
    if path is None or is_bot(ua):
        return None
    return PageView.objects.create(
        path=path,
        visitor=visitor_code(client_ip(request), ua, timezone.localdate(timezone=_league_tz())),
        source=source(referrer, ref, request.get_host()),
        device=device(ua),
        browser=browser(ua),
        os=operating_system(ua),
        audience=audience(request.user),
    )
