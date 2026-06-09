from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """记录统一格式的 HTTP 请求日志。

    这里替代 uvicorn access log：控制台只显示简洁 message，文件 JSONL 里保留
    request_id、method、path、status_code、duration_ms 等结构化字段。
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        skip_paths: Iterable[str] | None = None,
        request_id_header: str = "X-Request-ID",
    ) -> None:
        super().__init__(app)
        self.skip_paths = frozenset(skip_paths or ())
        self.request_id_header = request_id_header

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        if self._should_skip(request.url.path):
            return await call_next(request)

        request_id = _get_or_create_request_id(
            request=request,
            header_name=self.request_id_header,
        )
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = _elapsed_ms(started_at)
            logger.exception(
                "HTTP request failed: %s %s -> 500 %.2fms",
                request.method,
                request.url.path,
                duration_ms,
                extra=_build_request_extra(
                    request=request,
                    request_id=request_id,
                    status_code=500,
                    duration_ms=duration_ms,
                ),
            )
            raise

        duration_ms = _elapsed_ms(started_at)
        response.headers[self.request_id_header] = request_id
        _log_completed_request(
            request=request,
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    def _should_skip(self, path: str) -> bool:
        return path in self.skip_paths


def _log_completed_request(
    *,
    request: Request,
    request_id: str,
    status_code: int,
    duration_ms: float,
) -> None:
    level = _level_for_status_code(status_code)
    logger.log(
        level,
        "HTTP request completed: %s %s -> %s %.2fms",
        request.method,
        request.url.path,
        status_code,
        duration_ms,
        extra=_build_request_extra(
            request=request,
            request_id=request_id,
            status_code=status_code,
            duration_ms=duration_ms,
        ),
    )


def _build_request_extra(
    *,
    request: Request,
    request_id: str,
    status_code: int,
    duration_ms: float,
) -> dict[str, object]:
    return {
        "event": "http_request",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "client_ip": _get_client_ip(request),
        "user_agent": request.headers.get("user-agent"),
    }


def _level_for_status_code(status_code: int) -> int:
    if status_code >= 500:
        return logging.ERROR
    if status_code >= 400:
        return logging.WARNING
    return logging.INFO


def _get_or_create_request_id(*, request: Request, header_name: str) -> str:
    request_id = request.headers.get(header_name)
    if request_id is not None and request_id.strip():
        return request_id.strip()[:128]
    return str(uuid4())


def _get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip() or None
    if request.client is None:
        return None
    return request.client.host


def _elapsed_ms(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1000
