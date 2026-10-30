"""
Request-ID middleware and access logging middleware.
"""
from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import get_logger, request_id_var

logger = get_logger("middleware")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Accept or generate a request ID; bind it to contextvar and response header."""

    async def dispatch(self, request: Request, call_next: object) -> Response:
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(req_id)
        try:
            response: Response = await call_next(request)  # type: ignore[arg-type]
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_var.reset(token)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log each request: method, path, status, duration_ms, request_id."""

    async def dispatch(self, request: Request, call_next: object) -> Response:
        start = time.perf_counter()
        response: Response = await call_next(request)  # type: ignore[arg-type]
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "http_request",
            method=request.method,
            path=str(request.url.path),
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response

