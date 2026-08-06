import time
from uuid import uuid4

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.observability.context import (
    bind_request_id,
    clear_observability_context,
)

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        clear_observability_context()
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        with bind_request_id(request_id):
            await logger.ainfo(
                "request",
                method=scope["method"],
                path=scope["path"],
            )
            started_at = time.perf_counter()
            response_send = ResponseSend(send)
            try:
                await self._app(scope, receive, response_send)
            except Exception:
                await logger.aexception(
                    "response",
                    status_code=response_send.status_code or 500,
                    latency_ms=_latency_ms(started_at),
                )
                raise
            await logger.ainfo(
                "response",
                status_code=response_send.status_code,
                latency_ms=_latency_ms(started_at),
            )


class ResponseSend:
    def __init__(self, send: Send) -> None:
        self._send = send
        self.status_code: int | None = None

    async def __call__(self, message: Message) -> None:
        if message["type"] == "http.response.start":
            self.status_code = message["status"]
        await self._send(message)


def _latency_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1_000, 2)
