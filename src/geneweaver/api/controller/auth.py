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
3. `GET /sessions/me` tells the page who is signed in. `POST /sessions/logout`, from this site
   only, clears the session and ends the Auth0 session too.

Until `AUTH_LOGIN_CLIENT_ID`, `AUTH_LOGIN_CLIENT_SECRET`, `AUTH_SESSION_KEY` and
`AUTH_PUBLIC_URL` are all set, `/login`, `/callback` and `/logout` answer 404. `/me` stays
available and reports `login_available: false`, so the page knows to offer no sign-in.
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
from starlette.concurrency import run_in_threadpool

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


def _bad_token_response(why: str) -> HTTPException:
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY, detail=f"Auth0's token response was unusable: {why}."
    )


def _exchange_code(code: str, verifier: str) -> tuple[str, int]:
    """Exchange the authorization code for an access token, with the client secret.

    Synchronous on purpose (`requests`), so the async callback runs it in a worker thread.
    The response is parsed once and its shape checked, so anything other than a usable
    token -- a refusal, an outage, a proxy's HTML, a body missing its fields -- is the
    documented 502 rather than a 500 from a decoding or type error.

    :return: The access token and its lifetime in seconds.
    :raises HTTPException: 502 for every way the exchange can fail.
    """
    try:
        exchanged = requests.post(
            f"https://{settings.AUTH_DOMAIN}/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.AUTH_LOGIN_CLIENT_ID,
                "client_secret": settings.AUTH_LOGIN_CLIENT_SECRET,
                "code": code,
                "redirect_uri": _callback_url(),
                "code_verifier": verifier,
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
    try:
        body = exchanged.json()
    except ValueError as err:
        raise _bad_token_response("not JSON") from err
    if not isinstance(body, dict):
        raise _bad_token_response("not an object")
    access_token = body.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise _bad_token_response("no access_token")
    expires_in = body.get("expires_in", session.SESSION_MAX_AGE_SECONDS)
    if isinstance(expires_in, bool) or not isinstance(expires_in, int) or expires_in <= 0:
        raise _bad_token_response(f"expires_in is {expires_in!r}, not a positive integer")
    return access_token, expires_in


@router.get("/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    """Finish sign-in: check state, exchange the code with the client secret, set the session.

    :raises HTTPException: 400 for a refused, stale or forged sign-in; 502 for anything wrong
        on Auth0's side -- unreachable, refusing the code, or returning an unusable token.
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
        # As bytes: `compare_digest` raises TypeError on a non-ASCII str, which turned a
        # forged `state=%C3%A9` into a 500 instead of this 400.
        or not secrets.compare_digest(
            str(pending.get("state", "")).encode("utf-8"), state.encode("utf-8")
        )
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Sign-in could not be verified (expired or not started here). Try again.",
        )

    # Off the event loop: `requests` is synchronous, and this route is async (it awaits the
    # token verification). Run inline, a slow Auth0 would stall every other request on this
    # worker for up to the timeout.
    access_token, expires_in = await run_in_threadpool(_exchange_code, code, pending["verifier"])

    # Verified exactly as any request's token is -- signature, issuer, audience, expiry --
    # before it is stored. A token the API would refuse never becomes a session, and that
    # refusal is Auth0 handing back something unusable: an upstream fault (502), not the
    # caller's 401/403.
    try:
        user = await deps.auth.get_user(
            SecurityScopes(),
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=access_token),
        )
    except (HTTPException, KeyError, ValueError, TypeError) as err:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="Auth0 returned a token this API cannot use."
        ) from err
    if user is None:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Auth0 returned no usable token.")

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


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    """Clear the session here and at Auth0, then return to `/next`.

    A POST from this site only. As a GET, any other site could sign the user out -- ending
    their Auth0 session too -- just by linking or redirecting here, since `SameSite=Lax`
    allows top-level GET navigations and nothing else would have stopped it. The page posts
    a form, which carries this site's `Origin`; anything else is refused.

    303, so the browser follows to Auth0's logout with a GET.

    :raises HTTPException: 403 if the request does not come from this site.
    """
    _require_login()
    if request.headers.get("Origin") != session.public_origin():
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Sign-out must be requested from this site."
        )
    return_to = f"{settings.AUTH_PUBLIC_URL.rstrip('/')}{DEFAULT_RETURN}"
    query = urlencode({"client_id": settings.AUTH_LOGIN_CLIENT_ID, "returnTo": return_to})
    response = RedirectResponse(
        f"https://{settings.AUTH_DOMAIN}/v2/logout?{query}", status.HTTP_303_SEE_OTHER
    )
    response.delete_cookie(session.SESSION_COOKIE, path="/")
    return response
