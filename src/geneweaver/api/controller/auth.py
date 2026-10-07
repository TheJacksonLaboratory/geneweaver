"""Server-side sign-in for the `/next` UI.

The same confidential authorization-code flow legacy GeneWeaver uses, on FastAPI: the API is
the Auth0 client, holds the client secret, and exchanges the code itself. The browser never
sees a token -- only an encrypted, `HttpOnly` session cookie (`core.session`) -- and every
`/api` endpoint then authenticates it exactly like a bearer token (`Auth0HTTPBearer`).

Flow:

1. `GET /sessions/login?next=/next/analyze` stores `state`, a PKCE verifier and the return path
   in a short-lived encrypted cookie, then redirects to Auth0's `/authorize` with legacy's
   client id and the API audience.
2. `GET /sessions/callback` checks `state`, exchanges the code with the **client secret** (and the
   PKCE verifier), verifies the access token as any request's would be, sets the session
   cookie and returns to the page.
3. `GET /sessions/me` tells the page who is signed in. `GET /sessions/logout` clears the session and
   ends the Auth0 session too.

Off -- every route 404s -- until `AUTH_LOGIN_CLIENT_ID`, `AUTH_LOGIN_CLIENT_SECRET`,
`AUTH_SESSION_KEY` and `AUTH_PUBLIC_URL` are all set.
"""

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, HTTPException, Query, Request, Security, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, SecurityScopes
from jax.apiutils import Response

from geneweaver.api import dependencies as deps
from geneweaver.api.core import session
from geneweaver.api.core.config import settings
from geneweaver.api.schemas.auth import UserInternal

#: `/sessions`, not `/auth`: the JAX API standards (`test_api_standards.py`) want plural
#: resource names, and a signed-in session is the resource these endpoints create and end.
router = APIRouter(prefix="/sessions", tags=["auth"])

#: Where a sign-in returns to when it was not given a page, or was given one it may not use.
DEFAULT_RETURN = "/next/"

#: The token exchange is one server-to-server call; Auth0 answers in well under a second.
TOKEN_REQUEST_TIMEOUT_SECONDS = 10


def _require_login() -> None:
    if not session.login_configured():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sign-in is not configured here.")


def _callback_url() -> str:
    return f"{settings.AUTH_PUBLIC_URL.rstrip('/')}{settings.API_PREFIX}/sessions/callback"


def safe_return_path(path: str | None) -> str:
    """The page to return to after sign-in, refusing anything that leaves this site.

    Only a path on this site is accepted: not a URL, not a protocol-relative `//host`, not a
    backslash form some browsers normalise into one. Otherwise the login endpoint would be an
    open redirect that lends this site's name to a phishing link.
    """
    if (
        not path
        or not path.startswith("/")
        or path.startswith("//")
        or "\\" in path
        or any(ord(char) < 0x20 for char in path)
    ):
        return DEFAULT_RETURN
    return path


def _set_cookie(response: RedirectResponse, name: str, value: str, max_age: int, path: str):
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path=path,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
    )


@router.get("/login")
def login(
    next_path: str | None = Query(None, alias="next", description="Page to return to."),
) -> RedirectResponse:
    """Start sign-in: redirect to Auth0 with legacy's client and the API audience."""
    _require_login()
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.AUTH_LOGIN_CLIENT_ID,
            "redirect_uri": _callback_url(),
            "scope": "openid profile email",
            "audience": settings.AUTH_AUDIENCE,
            "state": state,
            "code_challenge": challenge.decode(),
            "code_challenge_method": "S256",
        }
    )
    response = RedirectResponse(
        f"https://{settings.AUTH_DOMAIN}/authorize?{query}", status.HTTP_302_FOUND
    )
    sealed = session.seal(
        {"state": state, "verifier": verifier, "next": safe_return_path(next_path)}
    )
    _set_cookie(
        response,
        session.STATE_COOKIE,
        sealed,
        session.STATE_MAX_AGE_SECONDS,
        f"{settings.API_PREFIX}/sessions",
    )
    return response


@router.get("/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    """Finish sign-in: check state, exchange the code with the client secret, set the session.

    :raises HTTPException: 400 for a refused, stale or forged sign-in; 502 if Auth0's token
        endpoint fails.
    """
    _require_login()
    if error:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Sign-in was refused: {error_description or error}",
        )
    pending = session.unseal(
        request.cookies.get(session.STATE_COOKIE), session.STATE_MAX_AGE_SECONDS
    )
    if (
        not pending
        or not code
        or not state
        or not secrets.compare_digest(str(pending.get("state", "")), state)
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Sign-in could not be verified (expired or not started here). Try again.",
        )

    try:
        exchanged = requests.post(
            f"https://{settings.AUTH_DOMAIN}/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.AUTH_LOGIN_CLIENT_ID,
                "client_secret": settings.AUTH_LOGIN_CLIENT_SECRET,
                "code": code,
                "redirect_uri": _callback_url(),
                "code_verifier": pending["verifier"],
            },
            timeout=TOKEN_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as err:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="Auth0 could not be reached to finish sign-in."
        ) from err
    if exchanged.status_code != status.HTTP_200_OK:
        # Auth0's error body names the problem (e.g. `invalid_grant`) and holds no secret.
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Auth0 refused the sign-in ({exchanged.status_code}): {exchanged.text[:200]}",
        )
    access_token = exchanged.json().get("access_token")

    # Verified exactly as any request's token is -- signature, issuer, audience, expiry --
    # before it is stored. A token the API would refuse never becomes a session.
    user = await deps.auth.get_user(
        SecurityScopes(), HTTPAuthorizationCredentials(scheme="Bearer", credentials=access_token)
    )
    if user is None:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Auth0 returned no usable token.")

    expires_in = int(exchanged.json().get("expires_in") or session.SESSION_MAX_AGE_SECONDS)
    max_age = min(expires_in, session.SESSION_MAX_AGE_SECONDS)
    response = RedirectResponse(safe_return_path(pending.get("next")), status.HTTP_302_FOUND)
    _set_cookie(
        response,
        session.SESSION_COOKIE,
        session.seal({"access_token": access_token, "expires_at": int(time.time()) + max_age}),
        max_age,
        "/",
    )
    response.delete_cookie(session.STATE_COOKIE, path=f"{settings.API_PREFIX}/sessions")
    return response


@router.get("/me")
def me(user: UserInternal | None = Security(deps.auth.get_user)) -> Response:
    """Who is signed in, for the page header. Never returns the token."""
    return Response(
        object={
            "login_available": session.login_configured(),
            "authenticated": user is not None,
            "email": user.email if user else None,
            "name": user.name if user else None,
        }
    )


@router.get("/logout")
def logout() -> RedirectResponse:
    """Clear the session here and at Auth0, then return to `/next`."""
    _require_login()
    return_to = f"{settings.AUTH_PUBLIC_URL.rstrip('/')}{DEFAULT_RETURN}"
    query = urlencode({"client_id": settings.AUTH_LOGIN_CLIENT_ID, "returnTo": return_to})
    response = RedirectResponse(
        f"https://{settings.AUTH_DOMAIN}/v2/logout?{query}", status.HTTP_302_FOUND
    )
    response.delete_cookie(session.SESSION_COOKIE, path="/")
    return response
