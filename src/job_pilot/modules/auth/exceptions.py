from __future__ import annotations

from job_pilot.core.exceptions import (
    ConflictError,
    ForbiddenError,
    UnauthorizedError,
    ValidationError,
)
from job_pilot.modules.auth.enums import AuthProvider


class InvalidCredentialsError(UnauthorizedError):
    """Raised when login credentials are invalid."""

    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message=message, code="INVALID_CREDENTIALS")


class AuthIdentityAlreadyExistsError(ConflictError):
    """Raised when registering with an existing email or phone identity."""

    def __init__(self, message: str = "Auth identity is already registered"):
        super().__init__(message=message, code="AUTH_IDENTITY_ALREADY_EXISTS")

    @classmethod
    def from_provider(cls, provider: AuthProvider) -> AuthIdentityAlreadyExistsError:
        if provider == AuthProvider.EMAIL:
            return cls("Email is already registered")
        if provider == AuthProvider.PHONE:
            return cls("Phone is already registered")
        return cls()


class WeakPasswordError(ValidationError):
    """Raised when a password does not meet minimum requirements."""

    def __init__(self, message: str = "Password does not meet requirements"):
        super().__init__(message=message, code="WEAK_PASSWORD")


class UserInactiveError(ForbiddenError):
    """Raised when an inactive user tries to login or refresh."""

    def __init__(self, message: str = "Account is disabled"):
        super().__init__(message=message, code="ACCOUNT_DISABLED")


class TokenError(UnauthorizedError):
    """Base token error."""

    def __init__(self, message: str = "Invalid token", code: str = "INVALID_TOKEN"):
        super().__init__(message=message, code=code)


class TokenExpiredError(TokenError):
    """Raised when a token has expired."""

    def __init__(self, message: str = "Token has expired"):
        super().__init__(message=message, code="TOKEN_EXPIRED")


class InvalidTokenError(TokenError):
    """Raised when a token cannot be decoded or has invalid payload."""

    def __init__(self, message: str = "Invalid token"):
        super().__init__(message=message, code="INVALID_TOKEN")


class InvalidTokenTypeError(TokenError):
    """Raised when a token is valid but not the expected token type."""

    def __init__(self, message: str = "Invalid token type"):
        super().__init__(message=message, code="INVALID_TOKEN_TYPE")
