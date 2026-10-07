"""The browser session behind server-side sign-in.

After `controller/auth.py` completes the Auth0 authorization-code exchange, the user's access
token is kept in a cookie, **encrypted** with `AUTH_SESSION_KEY` (Fernet: AES-128-CBC plus an
HMAC, so it is unreadable and tamper-evident) and `HttpOnly`, so page scripts never see it.
Every request then authenticates exactly as a bearer-token request does: `Auth0HTTPBearer`
takes the token out of the cookie when there is no `Authorization` header, and the token is
verified against Auth0's keys on every request as before. The cookie adds no trust of its own;
it only carries a token the API would accept anyway.

Stateless by design: the API runs as several replicas with no shared session store, and an
encrypted cookie needs none.
"""

import json
import time
from typing import Any
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken

from geneweaver.api.core.config import settings

#: Holds the encrypted access token. Scoped to the whole site: `/next` pages read
#: `/api/sessions/me`, and every `/api` call authenticates with it.
SESSION_COOKIE = "gw_session"

#: Holds the login attempt's `state`, PKCE verifier and return path between the redirect to
#: Auth0 and the callback. Scoped to `/api/sessions` and short-lived.
STATE_COOKIE = "gw_auth_state"
STATE_MAX_AGE_SECONDS = 600

#: Ceiling on a session regardless of the token's own expiry.
SESSION_MAX_AGE_SECONDS = 12 * 60 * 60


def login_configured() -> bool:
    """Whether this environment offers server-side sign-in at all."""
    return all(
        (
            settings.AUTH_LOGIN_CLIENT_ID,
            settings.AUTH_LOGIN_CLIENT_SECRET,
            settings.AUTH_SESSION_KEY,
            settings.AUTH_PUBLIC_URL,
        )
    )


def _fernet() -> Fernet:
    return Fernet(settings.AUTH_SESSION_KEY.encode())


def seal(data: dict[str, Any]) -> str:
    """Encrypt and sign `data` for a cookie."""
    return _fernet().encrypt(json.dumps(data, separators=(",", ":")).encode()).decode()


def unseal(value: str | None, max_age: int) -> dict[str, Any] | None:
    """Decrypt a cookie written by `seal`, or None if absent, forged, stale or unusable.

    Never raises: an unreadable cookie is the same as no cookie, so a rotated key or a
    tampered value simply signs the user out.
    """
    if not value or not settings.AUTH_SESSION_KEY:
        return None
    try:
        data = json.loads(_fernet().decrypt(value.encode(), ttl=max_age))
    except (InvalidToken, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def session_token(cookie: str | None) -> str | None:
    """The access token held in a session cookie, if it is valid and unexpired."""
    data = unseal(cookie, SESSION_MAX_AGE_SECONDS)
    if not data or not isinstance(data.get("access_token"), str):
        return None
    expires_at = data.get("expires_at")
    if isinstance(expires_at, (int, float)) and expires_at <= time.time():
        return None
    return data["access_token"]


def public_origin() -> str | None:
    """`AUTH_PUBLIC_URL` reduced to scheme://host[:port], for comparing with `Origin`."""
    if not settings.AUTH_PUBLIC_URL:
        return None
    parts = urlsplit(settings.AUTH_PUBLIC_URL)
    return f"{parts.scheme}://{parts.netloc}"
