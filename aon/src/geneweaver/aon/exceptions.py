"""
All of the exceptions created for this service
"""

## Errors relating the application functionality


class GwOrthoNormError(Exception):
    pass


## Errors relating to authentication and authorization


class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


class JWTDecodeError(AuthError):
    pass
