"""Tests for server-side sign-in (`controller/auth.py`, mounted at `/api/sessions`)."""

from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from cryptography.fernet import Fernet

from geneweaver.api.controller.auth import DEFAULT_RETURN, safe_return_path
from geneweaver.api.core import session
from geneweaver.api.core.config import settings

SITE = "https://geneweaver-dev.jax.org"


@pytest.fixture
def login_settings(monkeypatch):
    """Sign-in configured with legacy's dev client."""
    monkeypatch.setattr(settings, "AUTH_LOGIN_CLIENT_ID", "x9IiBRyt8lS3lsqrz2H6aO1leRBbxyb7")
    monkeypatch.setattr(settings, "AUTH_LOGIN_CLIENT_SECRET", "the-client-secret")
    monkeypatch.setattr(settings, "AUTH_SESSION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "AUTH_PUBLIC_URL", SITE)
    return settings


def _query(location: str) -> dict:
    return {key: values[0] for key, values in parse_qs(urlsplit(location).query).items()}


def _start(client, next_path="/next/analyze"):
    """Begin a sign-in and return (state, sealed state cookie)."""
    response = client.get(
        "/api/sessions/login", params={"next": next_path}, follow_redirects=False
    )
    return _query(response.headers["location"])["state"], response.cookies[session.STATE_COOKIE]


def _token_response(status_code=200, body=None):
    response = Mock(status_code=status_code, text="error body")
    response.json.return_value = body or {"access_token": "access-token", "expires_in": 3600}
    return response


class TestNotConfigured:
    """Without all four settings, sign-in does not exist here."""

    @pytest.mark.parametrize("path", ["login", "callback"])
    def test_routes_404(self, client, path):
        """Nothing redirects to Auth0 from an unconfigured environment."""
        assert client.get(f"/api/sessions/{path}", follow_redirects=False).status_code == 404

    def test_logout_404s(self, client):
        """Including sign-out."""
        response = client.post(
            "/api/sessions/logout", headers={"Origin": SITE}, follow_redirects=False
        )
        assert response.status_code == 404

    def test_me_reports_it(self, client):
        """So the page can hide the button."""
        body = client.get("/api/sessions/me").json()["object"]
        assert body == {
            "login_available": False,
            "authenticated": False,
            "email": None,
            "name": None,
        }


class TestLogin:
    """The redirect to Auth0."""

    def test_redirects_with_legacys_client_and_the_api_audience(self, client, login_settings):
        """Authorization code, with state and PKCE."""
        response = client.get("/api/sessions/login", follow_redirects=False)

        assert response.status_code == 302
        location = response.headers["location"]
        assert location.startswith(f"https://{settings.AUTH_DOMAIN}/authorize?")
        query = _query(location)
        assert query["response_type"] == "code"
        assert query["client_id"] == "x9IiBRyt8lS3lsqrz2H6aO1leRBbxyb7"
        assert query["redirect_uri"] == f"{SITE}/api/sessions/callback"
        assert query["audience"] == settings.AUTH_AUDIENCE
        assert query["code_challenge_method"] == "S256"
        assert query["state"] and query["code_challenge"]
        # The secret goes to Auth0 only from the server, never through the browser.
        assert "the-client-secret" not in location

    def test_keeps_state_verifier_and_return_path_server_sealed(self, client, login_settings):
        """The browser holds them only encrypted, scoped to /api/sessions."""
        state, sealed = _start(client, "/next/analyze")
        pending = session.unseal(sealed, 60)
        assert pending["state"] == state
        assert pending["verifier"]
        assert pending["next"] == "/next/analyze"

    def test_an_offsite_return_path_is_dropped(self, client, login_settings):
        """Not an open redirect."""
        _, sealed = _start(client, "//evil.example/phish")
        assert session.unseal(sealed, 60)["next"] == DEFAULT_RETURN


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/next/analyze", "/next/analyze"),
        ("/next/geneset/1?x=1", "/next/geneset/1?x=1"),
        (None, DEFAULT_RETURN),
        ("", DEFAULT_RETURN),
        ("https://evil.example", DEFAULT_RETURN),
        ("//evil.example", DEFAULT_RETURN),
        ("/\\evil.example", DEFAULT_RETURN),
        ("/next/\nSet-Cookie:x", DEFAULT_RETURN),
    ],
)
def test_safe_return_path(path, expected):
    """Only a path on this site survives."""
    assert safe_return_path(path) == expected


class TestCallback:
    """Code exchange with the client secret, then the session."""

    def test_a_good_sign_in_sets_the_session_and_returns_to_the_page(self, client, login_settings):
        """The full happy path."""
        state, sealed = _start(client, "/next/analyze")
        with (
            patch(
                "geneweaver.api.controller.auth.requests.post", return_value=_token_response()
            ) as post,
            patch(
                "geneweaver.api.controller.auth.deps.auth.get_user",
                new=AsyncMock(return_value=Mock()),
            ) as verify,
        ):
            response = client.get(
                "/api/sessions/callback",
                params={"code": "the-code", "state": state},
                cookies={session.STATE_COOKIE: sealed},
                follow_redirects=False,
            )

        assert response.status_code == 302
        assert response.headers["location"] == "/next/analyze"
        sent = post.call_args.kwargs["data"]
        assert sent["grant_type"] == "authorization_code"
        assert sent["client_secret"] == "the-client-secret"
        assert sent["code"] == "the-code"
        assert sent["redirect_uri"] == f"{SITE}/api/sessions/callback"
        assert sent["code_verifier"] == session.unseal(sealed, 60)["verifier"]
        # Verified like any request's token before it becomes a session.
        assert verify.call_args.args[1].credentials == "access-token"
        cookie = response.cookies[session.SESSION_COOKIE]
        assert session.session_token(cookie) == "access-token"
        set_cookie = response.headers.get_list("set-cookie")
        session_header = next(h for h in set_cookie if h.startswith(session.SESSION_COOKIE))
        assert "HttpOnly" in session_header
        assert "Secure" in session_header
        assert "samesite=lax" in session_header.lower()

    def test_a_mismatched_state_is_refused(self, client, login_settings):
        """CSRF on the login itself: the callback must answer this browser's request."""
        _, sealed = _start(client)
        with patch("geneweaver.api.controller.auth.requests.post") as post:
            response = client.get(
                "/api/sessions/callback",
                params={"code": "c", "state": "someone-elses"},
                cookies={session.STATE_COOKIE: sealed},
                follow_redirects=False,
            )
        assert response.status_code == 400
        post.assert_not_called()

    def test_a_callback_without_a_started_login_is_refused(self, client, login_settings):
        """No state cookie, no exchange."""
        with patch("geneweaver.api.controller.auth.requests.post") as post:
            response = client.get(
                "/api/sessions/callback",
                params={"code": "c", "state": "s"},
                follow_redirects=False,
            )
        assert response.status_code == 400
        post.assert_not_called()

    def test_auth0_refusing_the_code_is_502(self, client, login_settings):
        """An upstream failure, reported with Auth0's own reason."""
        state, sealed = _start(client)
        with patch(
            "geneweaver.api.controller.auth.requests.post",
            return_value=_token_response(status_code=403),
        ):
            response = client.get(
                "/api/sessions/callback",
                params={"code": "c", "state": state},
                cookies={session.STATE_COOKIE: sealed},
                follow_redirects=False,
            )
        assert response.status_code == 502
        assert session.SESSION_COOKIE not in response.cookies

    def test_auth0_unreachable_is_502(self, client, login_settings):
        """No session from a failed exchange."""
        state, sealed = _start(client)
        with patch(
            "geneweaver.api.controller.auth.requests.post",
            side_effect=requests.ConnectionError("down"),
        ):
            response = client.get(
                "/api/sessions/callback",
                params={"code": "c", "state": state},
                cookies={session.STATE_COOKIE: sealed},
                follow_redirects=False,
            )
        assert response.status_code == 502

    def test_a_refusal_from_auth0_is_400(self, client, login_settings):
        """The user declined, or Auth0 refused before issuing a code."""
        response = client.get(
            "/api/sessions/callback",
            params={"error": "access_denied", "error_description": "User cancelled"},
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "User cancelled" in response.json()["detail"]


def test_logout_clears_the_session_here_and_at_auth0(client, login_settings):
    """A POST from this site ends both sessions, and comes back to /next."""
    response = client.post(
        "/api/sessions/logout", headers={"Origin": SITE}, follow_redirects=False
    )

    # 303 so the browser follows to Auth0's logout with a GET.
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith(f"https://{settings.AUTH_DOMAIN}/v2/logout?")
    query = _query(location)
    assert query["client_id"] == "x9IiBRyt8lS3lsqrz2H6aO1leRBbxyb7"
    assert query["returnTo"] == f"{SITE}{DEFAULT_RETURN}"
    cleared = next(
        h for h in response.headers.get_list("set-cookie") if h.startswith(session.SESSION_COOKIE)
    )
    assert "Max-Age=0" in cleared or "expires=" in cleared.lower()


@pytest.mark.parametrize("origin", [None, "https://evil.example", "https://other.jax.org"])
def test_logout_from_elsewhere_is_refused(client, login_settings, origin):
    """Another site cannot sign the user out, here or at Auth0."""
    headers = {"Origin": origin} if origin else {}
    response = client.post("/api/sessions/logout", headers=headers, follow_redirects=False)

    assert response.status_code == 403
    assert "set-cookie" not in response.headers


def test_logout_is_not_a_get(client, login_settings):
    """A link or redirect -- a top-level GET, which SameSite=Lax allows -- cannot sign out."""
    response = client.get("/api/sessions/logout", follow_redirects=False)
    assert response.status_code == 405


@pytest.mark.parametrize("state", ["é", "état", "\u2603"])
def test_a_non_ascii_state_is_a_400_not_a_500(client, login_settings, state):
    """compare_digest raises TypeError on a non-ASCII str; it must be a normal mismatch."""
    _, sealed = _start(client)
    with patch("geneweaver.api.controller.auth.requests.post") as post:
        response = client.get(
            "/api/sessions/callback",
            params={"code": "c", "state": state},
            cookies={session.STATE_COOKIE: sealed},
            follow_redirects=False,
        )
    assert response.status_code == 400
    post.assert_not_called()


def test_me_reports_the_user_and_never_the_token(app, client, login_settings):
    """The page needs a name to show, nothing more."""
    from geneweaver.api import dependencies as deps

    user = Mock(email="user@jax.org", token="secret-token")
    user.name = "A User"
    app.dependency_overrides[deps.auth.get_user] = lambda: user
    try:
        body = client.get("/api/sessions/me").json()["object"]
    finally:
        app.dependency_overrides.pop(deps.auth.get_user, None)

    assert body == {
        "login_available": True,
        "authenticated": True,
        "email": "user@jax.org",
        "name": "A User",
    }
    assert "secret-token" not in str(body)


# --- review follow-ups: every Auth0-side failure is the documented 502 ------------------


def _finish(client, token_response=None, verify=None):
    """Run a callback against a scripted token response and verifier."""
    state, sealed = _start(client)
    with (
        patch(
            "geneweaver.api.controller.auth.requests.post",
            return_value=token_response or _token_response(),
        ),
        patch(
            "geneweaver.api.controller.auth.deps.auth.get_user",
            new=verify or AsyncMock(return_value=Mock()),
        ),
    ):
        return client.get(
            "/api/sessions/callback",
            params={"code": "c", "state": state},
            cookies={session.STATE_COOKIE: sealed},
            follow_redirects=False,
        )


def _raw_token_response(body):
    response = Mock(status_code=200, text="body")
    if isinstance(body, Exception):
        response.json.side_effect = body
    else:
        response.json.return_value = body
    return response


@pytest.mark.parametrize(
    ("body", "why"),
    [
        (ValueError("Expecting value"), "not JSON"),
        (["a", "list"], "not an object"),
        ({"expires_in": 3600}, "no access_token"),
        ({"access_token": "", "expires_in": 3600}, "no access_token"),
        ({"access_token": "t", "expires_in": "soon"}, "expires_in"),
        ({"access_token": "t", "expires_in": 0}, "expires_in"),
        ({"access_token": "t", "expires_in": None}, "expires_in"),
        ({"access_token": "t", "expires_in": True}, "expires_in"),
    ],
)
def test_an_unusable_token_response_is_502_and_no_session(client, login_settings, body, why):
    """A proxy's HTML or a body missing its fields is an upstream fault, not a 500."""
    response = _finish(client, token_response=_raw_token_response(body))

    assert response.status_code == 502
    assert why in response.json()["detail"]
    assert session.SESSION_COOKIE not in response.cookies


@pytest.mark.parametrize("status_code", [401, 403])
def test_a_token_the_api_refuses_is_502_not_the_callers_fault(client, login_settings, status_code):
    """Auth0 handed back a token that fails verification: upstream, not the user's 401/403."""
    from fastapi import HTTPException

    refusing = AsyncMock(side_effect=HTTPException(status_code, detail="bad token"))
    response = _finish(client, verify=refusing)

    assert response.status_code == 502
    assert session.SESSION_COOKIE not in response.cookies


@pytest.mark.asyncio
async def test_the_token_exchange_does_not_block_the_event_loop(login_settings):
    """The callback is async; a synchronous exchange on the loop would stall every request.

    The fake Auth0 call waits for a coroutine that can only run if the loop is free. Run
    inline, it would wait out its timeout and see the coroutine never ran.
    """
    import asyncio
    import threading

    from starlette.requests import Request

    from geneweaver.api.controller import auth

    sealed = session.seal({"state": "s", "verifier": "v", "next": "/next/"})
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/sessions/callback",
            "query_string": b"",
            "headers": [(b"cookie", f"{session.STATE_COOKIE}={sealed}".encode())],
        }
    )
    loop_ran = threading.Event()
    observed = []

    def slow_post(*args, **kwargs):
        observed.append(loop_ran.wait(timeout=2))
        return _token_response()

    async def another_request():
        await asyncio.sleep(0)
        loop_ran.set()

    with (
        patch("geneweaver.api.controller.auth.requests.post", side_effect=slow_post),
        patch(
            "geneweaver.api.controller.auth.deps.auth.get_user",
            new=AsyncMock(return_value=Mock()),
        ),
    ):
        response, _ = await asyncio.gather(
            auth.callback(request, code="c", state="s"), another_request()
        )

    assert observed == [True]
    assert response.status_code == 302
