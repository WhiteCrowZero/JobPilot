class AppError(Exception):
    """Base application exception."""

    def __init__(self, message: str, code: str = "APP_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message=message, code="NOT_FOUND")


class BusinessError(AppError):
    """Raised when business rules reject an operation."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="BUSINESS_ERROR")
