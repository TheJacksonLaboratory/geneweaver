"""Tests for the sign-in session cookie and the bearer-or-cookie credential source."""

from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from geneweaver.api.core import session
from geneweaver.api.core.config import settings
from geneweaver.api.core.security import Auth0HTTPBearer

SITE = "https://geneweaver-dev.jax.org"


@pytest.fixture
def login_settings(monkeypatch):
    """Sign-in fully configured, with a fresh session key."""
    monkeypatch.setattr(settings, "AUTH_LOGIN_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "AUTH_LOGIN_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(settings, "AUTH_SESSION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "AUTH_PUBLIC_URL", SITE)
    return settings


class TestSealing:
    """The cookie is unreadable and tamper-evident; anything wrong reads as signed out."""

    def test_round_trip(self, login_settings):
        """What is sealed comes back."""
        assert session.unseal(session.seal({"a": 1}), 60) == {"a": 1}

    def test_the_cookie_does_not_reveal_its_contents(self, login_settings):
        """Encrypted, not merely signed: the token is not readable from the cookie."""
        assert "secret-token" not in session.seal({"access_token": "secret-token"})

    def test_a_tampered_cookie_is_no_session(self, login_settings):
        """A modified value fails its HMAC."""
        sealed = session.seal({"a": 1})
        tampered = sealed[:-4] + ("AAAA" if not sealed.endswith("AAAA") else "BBBB")
        assert session.unseal(tampered, 60) is None

    def test_a_rotated_key_signs_everyone_out(self, login_settings, monkeypatch):
        """Cookies sealed under the old key are no longer readable."""
        sealed = session.seal({"a": 1})
        monkeypatch.setattr(settings, "AUTH_SESSION_KEY", Fernet.generate_key().decode())
        assert session.unseal(sealed, 60) is None

    def test_a_stale_cookie_is_no_session(self, login_settings):
        """Older than its maximum age."""
        assert session.unseal(session.seal({"a": 1}), -1) is None

    def test_absent_or_unconfigured_is_no_session(self, login_settings, monkeypatch):
        """No cookie, or no key to read it with."""
        assert session.unseal(None, 60) is None
        sealed = session.seal({"a": 1})
        monkeypatch.setattr(settings, "AUTH_SESSION_KEY", None)
        assert session.unseal(sealed, 60) is None


class TestSessionToken:
    """Only a sealed, unexpired access token counts."""

    def test_returns_the_token(self, login_settings):
        """A current session yields its token."""
        sealed = session.seal({"access_token": "tok", "expires_at": 4_102_444_800})
        assert session.session_token(sealed) == "tok"

    def test_an_expired_session_is_none(self, login_settings):
        """Past the token's own expiry."""
        sealed = session.seal({"access_token": "tok", "expires_at": 1})
        assert session.session_token(sealed) is None

    def test_a_session_without_a_token_is_none(self, login_settings):
        """A state cookie, say, is not a session."""
        assert session.session_token(session.seal({"state": "x"})) is None


def test_login_needs_all_four_settings(login_settings, monkeypatch):
    """Any one missing turns sign-in off."""
    assert session.login_configured()
    for name in (
        "AUTH_LOGIN_CLIENT_ID",
        "AUTH_LOGIN_CLIENT_SECRET",
        "AUTH_SESSION_KEY",
        "AUTH_PUBLIC_URL",
    ):
        with patch.object(settings, name, None):
            assert not session.login_configured(), name


def test_public_origin_drops_the_path(login_settings, monkeypatch):
    """`Origin` has no path, so the comparison must not either."""
    monkeypatch.setattr(settings, "AUTH_PUBLIC_URL", SITE + "/next/")
    assert session.public_origin() == SITE


# --- Auth0HTTPBearer: header, else session cookie; CSRF guard on cookie writes ----


@pytest.fixture
def probe(login_settings):
    """A one-route app that reports which credentials the dependency produced."""
    app = FastAPI()

    @app.api_route("/probe", methods=["GET", "POST"])
    async def endpoint(creds=Depends(Auth0HTTPBearer(auto_error=False))):  # noqa: B008
        return {"token": creds.credentials if creds else None}

    return TestClient(app)


def _cookie(token="cookie-token"):
    return {
        session.SESSION_COOKIE: session.seal({"access_token": token, "expires_at": 4_102_444_800})
    }


class TestCredentialSource:
    """Every endpoint gets the session for free, without weakening bearer auth."""

    def test_no_credentials_is_anonymous(self, probe):
        """Neither header nor cookie."""
        assert probe.get("/probe").json() == {"token": None}

    def test_the_cookie_authenticates_a_read(self, probe):
        """A GET needs no Origin."""
        assert probe.get("/probe", cookies=_cookie()).json() == {"token": "cookie-token"}

    def test_a_header_wins_over_the_cookie(self, probe):
        """Explicit credentials are never overridden by ambient ones."""
        response = probe.get(
            "/probe", cookies=_cookie(), headers={"Authorization": "Bearer header-token"}
        )
        assert response.json() == {"token": "header-token"}

    def test_a_forged_cookie_is_anonymous(self, probe):
        """Not an error: just not signed in."""
        response = probe.get("/probe", cookies={session.SESSION_COOKIE: "forged"})
        assert response.json() == {"token": None}

    def test_a_same_site_write_is_allowed(self, probe):
        """The page's own POSTs carry this site's Origin."""
        response = probe.post("/probe", cookies=_cookie(), headers={"Origin": SITE})
        assert response.json() == {"token": "cookie-token"}

    @pytest.mark.parametrize("origin", [None, "https://evil.example", SITE + ".evil.example"])
    def test_a_cross_site_write_is_refused(self, probe, origin):
        """CSRF: a cookie-authenticated write must come from this site."""
        headers = {"Origin": origin} if origin else {}
        response = probe.post("/probe", cookies=_cookie(), headers=headers)
        assert response.status_code == 403

    def test_a_same_site_read_with_an_origin_is_allowed(self, probe):
        """Some browsers send Origin on same-origin GETs too."""
        response = probe.get("/probe", cookies=_cookie(), headers={"Origin": SITE})
        assert response.json() == {"token": "cookie-token"}

    @pytest.mark.parametrize("origin", ["https://other.jax.org", "https://evil.example"])
    def test_a_cross_origin_read_does_not_get_the_session(self, probe, origin):
        """A foreign Origin's read runs anonymously, whatever cookie it carries.

        Credentialed CORS is allowed from *.jax.org, and sibling hosts are same-site, so the
        cookie arrives; it must not authenticate a read another site can see.
        """
        response = probe.get("/probe", cookies=_cookie(), headers={"Origin": origin})
        assert response.status_code == 200
        assert response.json() == {"token": None}

    def test_a_cross_origin_bearer_read_is_unaffected(self, probe):
        """A header is explicit; another site's app holding its own token may still call."""
        response = probe.get(
            "/probe",
            headers={"Origin": "https://other.jax.org", "Authorization": "Bearer theirs"},
        )
        assert response.json() == {"token": "theirs"}

    def test_a_bearer_write_needs_no_origin(self, probe):
        """Another site cannot attach a header, so the guard does not apply."""
        response = probe.post("/probe", headers={"Authorization": "Bearer header-token"})
        assert response.json() == {"token": "header-token"}
