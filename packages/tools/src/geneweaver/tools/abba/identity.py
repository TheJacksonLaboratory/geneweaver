"""Who an ABBA run is for, carried through AsyncTask so it cannot be forged or replayed.

ABBA's matching gene sets include the caller's private ones -- those shared with a group the
caller belongs to -- so the worker has to know who the caller is. AsyncTask does not tell
it: a run's owner stays in AsyncTask's own database and the workflow receives only the
submitted values. And a signed-in user can submit values to AsyncTask directly, so a bare
`user_id` in the request would let anyone search as anyone.

So the API signs the user id, and the worker accepts only a signature it can verify. The
signature covers more than the user (v2):

- **the search's input**, as a digest: a signed identity copied out of one run's stored
  values (by anyone who can read them) cannot be attached to a different search;
- **an expiry**, `TTL_SECONDS` after signing: it cannot be replayed indefinitely either. A run
  starts within seconds of submission; the margin covers queueing and activity retries.

The key comes from `ABBA_IDENTITY_SECRET` where it is set, on the API and the tool worker
alike, and otherwise from the database password the two already share through the
`geneweaver-db` Secret. A dedicated secret decouples rotating the database password from
in-flight runs, and keeps the password from minting identities; the fallback keeps an
environment working until that secret is provisioned. A domain-separation label keeps the
derived key from being useful for anything else.

A request with no identity searches public gene sets only. One whose signature does not
verify, has expired, or was made for another input is refused rather than downgraded, so a
key mismatch between the API and the worker shows up as a failed run instead of silently
missing private gene sets.
"""

import hashlib
import hmac
import json
import os
import time
from typing import Any

#: Changing this invalidates every signature in flight, so version it rather than edit it.
_LABEL = b"geneweaver-tools abba identity v2"

#: The public audience: no private gene sets.
PUBLIC_USER_ID = 0

#: How long a signed identity stays valid after the API signs it.
TTL_SECONDS = 6 * 60 * 60


def signing_secret(environ: dict[str, str] | None = None) -> str | None:
    """The key material: `ABBA_IDENTITY_SECRET`, else the shared `DB_PASSWORD`."""
    environ = os.environ if environ is None else environ
    return environ.get("ABBA_IDENTITY_SECRET") or environ.get("DB_PASSWORD") or None


def input_digest(tool_input: dict[str, Any]) -> str:
    """The search input, canonically: sorted keys, compact, as JSON survives AsyncTask."""
    canonical = json.dumps(tool_input, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _key(secret: str) -> bytes:
    return hmac.new(secret.encode(), _LABEL, hashlib.sha256).digest()


def _signature(user_id: int, expires: int, digest: str, secret: str) -> str:
    message = f"{user_id}|{expires}|{digest}".encode()
    return hmac.new(_key(secret), message, hashlib.sha256).hexdigest()


def sign(user_id: int, secret: str, tool_input: dict[str, Any], now: float | None = None) -> dict:
    """The identity block the API sends beside ``tool_input``, valid for `TTL_SECONDS`."""
    expires = int((time.time() if now is None else now) + TTL_SECONDS)
    digest = input_digest(tool_input)
    return {
        "user_id": user_id,
        "expires": expires,
        "signature": _signature(user_id, expires, digest, secret),
    }


def verified_user_id(
    identity: object,
    secret: str | None,
    tool_input: dict[str, Any] | None,
    now: float | None = None,
) -> int:
    """The user to search as: the signed one, or the public audience if none was sent.

    :param tool_input: The input the run carries; the signature must have been made for it.
    :raises ValueError: If an identity was sent but is malformed, has expired, was signed for
        another input, cannot be checked because this worker has no key, or does not verify.
    """
    if identity is None:
        return PUBLIC_USER_ID
    if not isinstance(identity, dict):
        raise ValueError("identity must be an object with user_id, expires and signature.")
    user_id = identity.get("user_id")
    expires = identity.get("expires")
    signature = identity.get("signature")
    if (
        not isinstance(user_id, int)
        or isinstance(user_id, bool)
        or not isinstance(expires, int)
        or isinstance(expires, bool)
        or not isinstance(signature, str)
    ):
        raise ValueError("identity must carry an integer user_id and expires, and a signature.")
    if not secret:
        raise ValueError(
            "The run carries a signed identity, but this worker has no ABBA_IDENTITY_SECRET "
            "or DB_PASSWORD to check it with."
        )
    expected = _signature(user_id, expires, input_digest(tool_input or {}), secret)
    if not hmac.compare_digest(signature, expected):
        raise ValueError(
            "The run's identity signature does not verify for this search. Was it submitted "
            "other than through the GeneWeaver API, copied from another run, or do the API "
            "and worker use different keys?"
        )
    if (time.time() if now is None else now) > expires:
        raise ValueError("The run's identity has expired; submit the search again.")
    return user_id
