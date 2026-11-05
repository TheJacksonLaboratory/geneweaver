"""Who an ABBA run is for, carried through AsyncTask so it cannot be forged.

ABBA's matching gene sets include the caller's private ones -- those shared with a group the
caller belongs to -- so the worker has to know who the caller is. AsyncTask does not tell
it: a run's owner stays in AsyncTask's own database and the workflow receives only the
submitted values. And a signed-in user can submit values to AsyncTask directly, so a bare
`user_id` in the request would let anyone search as anyone.

So the API signs the user id, and the worker accepts only a signature it can verify. The key
is derived from the database password, which the API and the tool worker already share
through the `geneweaver-db` Secret: no new secret to provision per environment, and anyone
who holds it can read every gene set directly anyway. A domain-separation label keeps the
derived key from being useful for anything else, and rotating the password rotates it.

A request with no identity searches public gene sets only. One whose signature does not
verify is refused rather than downgraded, so a key mismatch between the API and the worker
shows up as a failed run instead of silently missing private gene sets.
"""

import hashlib
import hmac

#: Changing this invalidates every signature in flight, so version it rather than edit it.
_LABEL = b"geneweaver-tools abba identity v1"

#: The public audience: no private gene sets.
PUBLIC_USER_ID = 0


def _key(secret: str) -> bytes:
    return hmac.new(secret.encode(), _LABEL, hashlib.sha256).digest()


def _signature(user_id: int, secret: str) -> str:
    return hmac.new(_key(secret), str(user_id).encode(), hashlib.sha256).hexdigest()


def sign(user_id: int, secret: str) -> dict:
    """The identity block the API sends beside the input."""
    return {"user_id": user_id, "signature": _signature(user_id, secret)}


def verified_user_id(identity: object, secret: str | None) -> int:
    """The user to search as: the signed one, or the public audience if none was sent.

    :raises ValueError: If an identity was sent but is malformed, cannot be checked because
        this worker has no key, or does not verify.
    """
    if identity is None:
        return PUBLIC_USER_ID
    if not isinstance(identity, dict):
        raise ValueError("identity must be an object with user_id and signature.")
    user_id, signature = identity.get("user_id"), identity.get("signature")
    if not isinstance(user_id, int) or isinstance(user_id, bool) or not isinstance(signature, str):
        raise ValueError("identity must carry an integer user_id and a signature.")
    if not secret:
        raise ValueError(
            "The run carries a signed identity, but this worker has no DB_PASSWORD to check "
            "it with."
        )
    if not hmac.compare_digest(signature, _signature(user_id, secret)):
        raise ValueError(
            "The run's identity signature does not verify. Was it submitted other than "
            "through the GeneWeaver API, or do the API and worker use different databases?"
        )
    return user_id
