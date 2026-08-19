import logging
import re
from uuid import UUID

import httpx
import structlog
from fastapi import FastAPI

from app.observability.config import LogRenderer, configure_logging
from app.observability.request_logging import RequestLoggingMiddleware
from app.tasks.models import Task

logger = structlog.get_logger(__name__)


async def logged_endpoint() -> dict[str, str]:
    logger.info("inside endpoint")
    return {"status": "ok"}


def test_task_request_id_can_be_null_for_non_http_execution() -> None:
    task = Task(type="maintenance", parameters={}, request_id=None)

    assert task.request_id is None


async def test_logs_one_completed_request_and_propagates_request_id(capsys) -> None:
    configure_logging()
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    app.get("/logged")(logged_endpoint)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/logged")

    assert response.status_code == 200
    logs = capsys.readouterr().out.splitlines()
    endpoint_log = next(line for line in logs if ": inside endpoint " in line)
    request_log = next(line for line in logs if ": request completed " in line)

    assert sum(": request completed " in line for line in logs) == 1
    assert re.match(r"INFO - \d{4}-\d{2}-\d{2}T.*Z: request completed ", request_log)
    request_id = re.search(r"request_id=([0-9a-f-]+)", request_log)
    assert request_id is not None
    UUID(request_id.group(1))
    assert "method=GET" in request_log
    assert "path=/logged" in request_log
    assert "client_ip=127.0.0.1" in request_log
    assert "client_port=123" in request_log
    assert "http_version=1.1" in request_log
    assert f"request_id={request_id.group(1)}" in endpoint_log
    assert "status_code=200" in request_log
    assert re.search(r"latency_ms=\d+(\.\d+)?", request_log)


def test_configure_logging_disables_only_uvicorn_access_logs() -> None:
    configure_logging()

    assert logging.getLogger("uvicorn.access").disabled is True
    assert logging.getLogger("uvicorn.error").disabled is False


def test_log_renderer_defaults_timestamp_to_current_utc_time() -> None:
    rendered = LogRenderer()(None, "info", {"event": "message", "level": "info"})

    assert re.match(r"INFO - \d{4}-\d{2}-\d{2}T.*\+00:00: message$", rendered)
