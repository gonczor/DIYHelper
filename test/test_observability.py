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
    await logger.ainfo("inside endpoint")
    return {"status": "ok"}


def test_task_request_id_can_be_null_for_non_http_execution() -> None:
    task = Task(type="maintenance", parameters={}, request_id=None)

    assert task.request_id is None


async def test_logs_request_response_and_propagates_request_id(capsys) -> None:
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
    request_log = next(line for line in logs if ": request " in line)
    endpoint_log = next(line for line in logs if ": inside endpoint " in line)
    response_log = next(line for line in logs if ": response " in line)

    assert re.match(r"INFO - \d{4}-\d{2}-\d{2}T.*Z: request ", request_log)
    request_id = re.search(r"request_id=([0-9a-f-]+)", request_log)
    assert request_id is not None
    UUID(request_id.group(1))
    assert "method=GET" in request_log
    assert "path=/logged" in request_log
    assert f"request_id={request_id.group(1)}" in endpoint_log
    assert f"request_id={request_id.group(1)}" in response_log
    assert "status_code=200" in response_log
    assert re.search(r"latency_ms=\d+(\.\d+)?", response_log)


def test_log_renderer_defaults_timestamp_to_current_utc_time() -> None:
    rendered = LogRenderer()(None, "info", {"event": "message", "level": "info"})

    assert re.match(r"INFO - \d{4}-\d{2}-\d{2}T.*\+00:00: message$", rendered)
