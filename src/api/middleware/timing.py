import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.core.logger import logger


class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.debug(
            f"{request.method} {request.url.path} → {response.status_code} ({duration_ms}ms)"
        )
        response.headers["x-duration-ms"] = str(duration_ms)
        return response
