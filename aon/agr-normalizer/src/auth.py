import requests
import logging

from jose import jwt
from functools import wraps
from flask import request, current_app, _request_ctx_stack

from src.exceptions import AuthError, JWTDecodeError

LOGGER = logging.getLogger(__name__)

AUTHORIZATIONS = {
    'Access': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization'
    }
}


def get_token_auth_header():
    """
    Obtains the Access Token from the Authorization Header
    """
    auth = request.headers.get("Authorization", None)
    if not auth:
        raise AuthError({"code": "authorization_header_missing",
                         "description":
                             "Authorization header is expected"}, 401)

    parts = auth.split()

    if parts[0].lower() != "bearer":
        raise AuthError({"code": "invalid_header",
                         "description":
                             "Authorization header must start with"
                             " Bearer"}, 401)
    elif len(parts) == 1:
        raise AuthError({"code": "invalid_header",
                         "description": "Token not found"}, 401)
    elif len(parts) > 2:
        raise AuthError({"code": "invalid_header",
                         "description":
                             "Authorization header must be"
                             " Bearer token"}, 401)

    token = parts[1]
    return token


def get_decode_key_from_auth0(header):
    """
    Load public key from auth0 to decode the jwt
    :param header: The unverified token header to check the KID against
    :return: The RSA_KEY used to decode/verify the token
    """

    uri = f"https://{current_app.config['AUTH_DOMAIN']}/.well-known/jwks.json"
    jwks = requests.get(uri).json()
    rsa_key = None
    if header.get("kid"):
        for key in jwks["keys"]:
            if key["kid"] == header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
    if rsa_key is None:
        LOGGER.warning("Token used with no matching decode key.")
        LOGGER.warning(f"This key was NOT issued by {current_app.config['AUTH_DOMAIN']}!")
        LOGGER.warning(f"Token header: {header}")
        raise JWTDecodeError("No matching decode key")
    return rsa_key


def requires_auth(f):
    """Determines if the Access Token is valid"""

    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_auth_header()
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = get_decode_key_from_auth0(unverified_header)

        if rsa_key:
            try:
                payload = jwt.decode(
                    token,
                    rsa_key,
                    algorithms=current_app.config['AUTH_ALGORITHMS'],
                    audience=current_app.config['AUTH_AUDIENCE'],
                    issuer="https://" + current_app.config['AUTH_DOMAIN'] + "/"
                )
            except jwt.ExpiredSignatureError:
                raise AuthError({"code": "token_expired",
                                 "description": "token is expired"}, 401)
            except jwt.JWTClaimsError:
                raise AuthError({"code": "invalid_claims",
                                 "description":
                                     "incorrect claims,"
                                     "please check the audience and issuer"}, 401)
            except Exception:
                raise AuthError({"code": "invalid_header",
                                 "description":
                                     "Unable to parse authentication"
                                     " token."}, 401)

            _request_ctx_stack.top.current_user = payload
            return f(*args, **kwargs)
        raise AuthError({"code": "invalid_header",
                         "description": "Unable to find appropriate key"}, 401)

    return decorated


def requires_auth_scopes(required_scopes=None, strategy=any):
    """
    Determines if the required scopes are present in the Access Token according to the strategy. This decorator also
    applies the `requires_auth` decorator and is in fact equivalent to it if no required scopes are set in the decorator.
    The strategy determines how to evaluate an iterable of bools relfecting if each required scope is found in the token.
    e.g. @required_auth_scopes(['read:messages', 'read:profile', 'write:profile'], strategy=any)
    required_scopes: (list): The scopes required to access the resource
    strategy: (function(iterable)): Strategy for checking the scopes against the token
    """

    def wrapper(f):

        @wraps(f)
        @requires_auth
        def check_scopes(*args, **kwargs):
            token = get_token_auth_header()
            unverified_claims = jwt.get_unverified_claims(token)
            if unverified_claims.get("scope"):
                token_scopes = unverified_claims["scope"].split()
                if strategy(elem in token_scopes for elem in required_scopes):
                    return f(*args, **kwargs)
            raise AuthError({"code": "missing_scopes",
                             "description": "Token does not contain the required scopes to access this resource"}, 401)

        return check_scopes

    return wrapper
