"""Turning one page view request into a stored row: who (anonymously), what, from where."""

from __future__ import annotations

import hashlib
import hmac
import re
import uuid
from datetime import timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import models
from django.utils import timezone

from .models import Action, PageView

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
        user=request.user if request.user and request.user.is_authenticated else None,
        audience=audience(request.user),
    )


# -- After the page opened: time on page and actions ---------------------------------------

MAX_SECONDS = 60 * 60  # a page left open all night is not an hour of reading
MAX_ACTIONS_PER_VIEW = 300
REPORT_WINDOW = timedelta(hours=24)


def view_for(key) -> PageView | None:
    """The page view a browser reports on, if the key is real and recent."""
    try:
        key = uuid.UUID(str(key))
    except ValueError:
        return None
    since = timezone.now() - REPORT_WINDOW
    return PageView.objects.filter(key=key, created_at__gte=since).first()


def report_time(view: PageView, seconds) -> None:
    """The browser sends the total time so far; keep the largest (pings can arrive late)."""
    try:
        seconds = min(MAX_SECONDS, max(0, int(seconds)))
    except (TypeError, ValueError):
        return
    PageView.objects.filter(pk=view.pk).filter(
        models.Q(duration_s__isnull=True) | models.Q(duration_s__lt=seconds)
    ).update(duration_s=seconds)


def _text(value, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


# What a save or sign-in to the API was, by its first path part.
API_NOUNS = {
    "uploads": "match files",
    "matches": "a match",
    "teams": "a team",
    "seasons": "a season",
    "stages": "a stage",
    "match-days": "a match day",
    "players": "a player",
    "cards": "player cards",
    "maps": "a map",
    "coach": "coach settings",
    "pp": "Protection Points",
    "ratings": "ratings",
    "invites": "an invite",
    "me": "their profile",
    "groups": "a group",
    "player-claims": "a player claim",
    "rosters": "a roster",
    "scoring-rules": "scoring rules",
    "staff": "staff access",
    "team-aliases": "a team name spelling",
}
API_VERBS = {"POST": "Saved", "PUT": "Saved", "PATCH": "Edited", "DELETE": "Deleted"}


def api_action_name(method: str, path: str, ok: bool) -> str | None:
    """A readable name for a change the site made through the API, or None to skip it."""
    method = (method or "").upper()
    path = _text(path, 120).split("?")[0].strip("/")
    if method not in API_VERBS or not path or path.startswith(("analytics", "auth/csrf")):
        return None
    if path == "auth/refresh":
        return None
    if path == "auth/login":
        return "Signed in" if ok else "Sign-in failed"
    if path == "auth/logout":
        return "Signed out"
    if path.startswith("auth/password-reset"):
        return "Asked to reset password" if ok else "Password reset failed"
    if path.startswith("invites/") and method == "POST":
        return "Accepted an invite" if ok else "Invite failed"
    if path == "me/link-uid":
        return "Linked their game ID" if ok else "Game ID link failed"
    parts = [p for p in path.split("/") if p and p != "admin"]
    noun = API_NOUNS.get(parts[0] if parts else "", parts[0] if parts else "something")
    name = f"{API_VERBS[method]} {noun}"
    return name if ok else f"{name} (failed)"


def add_action(view: PageView, data: dict):
    """Store one thing done on a page. ``data`` is either {name, detail} from a click or
    pick, or {api: {method, path, ok}} for a change the page made."""
    if view.actions.count() >= MAX_ACTIONS_PER_VIEW:
        return None
    api = data.get("api")
    if isinstance(api, dict):
        name = api_action_name(api.get("method"), api.get("path"), bool(api.get("ok")))
        detail = _text(api.get("path"), 120).split("?")[0]
    else:
        name = _text(data.get("name"), 80)
        detail = _text(data.get("detail"), 120)
    if not name:
        return None
    return Action.objects.create(view=view, name=name, detail=detail)
