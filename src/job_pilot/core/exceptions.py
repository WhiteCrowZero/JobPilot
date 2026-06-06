from __future__ import annotations

from typing import cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette import status


class AppError(Exception):
    def __init__(self, message: str, code: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND"):
        super().__init__(message=message, code=code, status_code=status.HTTP_404_NOT_FOUND)


class ConflictError(AppError):
    def __init__(self, message: str = "Resource conflict", code: str = "CONFLICT"):
        super().__init__(message=message, code=code, status_code=status.HTTP_409_CONFLICT)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden", code: str = "FORBIDDEN"):
        super().__init__(message=message, code=code, status_code=status.HTTP_403_FORBIDDEN)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized", code: str = "UNAUTHORIZED"):
        super().__init__(message=message, code=code, status_code=status.HTTP_401_UNAUTHORIZED)


class BadRequestError(AppError):
    def __init__(self, message: str = "Bad request", code: str = "BAD_REQUEST"):
        super().__init__(message=message, code=code, status_code=status.HTTP_400_BAD_REQUEST)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation error", code: str = "VALIDATION_ERROR"):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )


class ResourceUnavailableError(AppError):
    def __init__(
        self,
        message: str = "Resource unavailable",
        code: str = "RESOURCE_UNAVAILABLE",
    ):
        super().__init__(
            message=message, code=code, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


async def app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    app_error = cast(AppError, exc)
    return JSONResponse(
        status_code=app_error.status_code,
        content={"detail": app_error.message, "code": app_error.code},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
