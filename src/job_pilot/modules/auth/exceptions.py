from __future__ import annotations


class AuthError(Exception):
    """Base auth service error."""


class InvalidCredentialsError(AuthError):
    """Raised when login credentials are invalid."""


class UserAlreadyExistsError(AuthError):
    """Raised when registering with an existing email."""


class WeakPasswordError(AuthError):
    """Raised when a password does not meet minimum requirements."""


class UserInactiveError(AuthError):
    """Raised when an inactive user tries to login or refresh."""


class TokenError(Exception):
    """Base token error."""


class TokenExpiredError(TokenError):
    """Raised when a token has expired."""


class InvalidTokenError(TokenError):
    """Raised when a token cannot be decoded or has invalid payload."""


class InvalidTokenTypeError(TokenError):
    """Raised when a token is valid but not the expected token type."""
