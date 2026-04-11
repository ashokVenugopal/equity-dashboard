"""
Request logging middleware.

Follows project_guidelines.md flight recorder pattern:
- Step announcement at start
- Summary at end with duration
- Error logging with context
"""
import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with start announcement and end summary."""

    async def dispatch(self, request: Request, call_next):
        t0 = time.time()
        method = request.method
        path = request.url.path
        query = str(request.url.query) if request.url.query else ""
        path_with_query = f"{path}?{query}" if query else path

        logger.info("%s %s starting...", method, path_with_query)

        try:
            response = await call_next(request)
            elapsed = time.time() - t0
            logger.info(
                "%s %s — %d, %.3fs",
                method, path_with_query, response.status_code, elapsed,
            )
            return response
        except Exception as e:
            elapsed = time.time() - t0
            logger.error(
                "%s %s — FAILED after %.3fs: %s",
                method, path_with_query, elapsed, str(e),
            )
            raise
