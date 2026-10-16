"""Checking a Google sign-in ("Continue with Google").

The browser gets an ID token from Google's own sign-in button and sends it here. Google's
tokeninfo endpoint checks its signature and expiry for us (no extra library needed), and we
check it was made for our client ID and that Google has verified the email address.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"
ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


class GoogleError(Exception):
    """The token was refused; ``str()`` is safe to show."""


def fetch_tokeninfo(credential: str) -> dict:
    url = f"{TOKENINFO}?{urllib.parse.urlencode({'id_token': credential})}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310 (fixed https URL)
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise GoogleError("Google didn't accept this sign-in. Try again.") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise GoogleError("Couldn't reach Google. Try again in a moment.") from exc


def verify(credential: str) -> dict:
    """The checked identity: ``{"email", "name", "sub"}``."""
    if not settings.GOOGLE_CLIENT_ID:
        raise GoogleError("Google sign-in isn't set up on this site.")
    if not isinstance(credential, str) or not 20 <= len(credential) <= 4096:
        raise GoogleError("Google didn't accept this sign-in. Try again.")
    info = fetch_tokeninfo(credential)
    if info.get("aud") != settings.GOOGLE_CLIENT_ID or info.get("iss") not in ISSUERS:
        raise GoogleError("Google didn't accept this sign-in. Try again.")
    if str(info.get("email_verified")).lower() != "true" or not info.get("email"):
        raise GoogleError("Your Google account's email isn't verified yet.")
    return {
        "email": info["email"].strip().lower(),
        "name": (info.get("name") or "").strip(),
        "sub": info.get("sub", ""),
    }
