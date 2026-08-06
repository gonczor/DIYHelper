from uuid import uuid4

import httpx
import pytest

from app.main import create_app
from app.settings import Settings

PROTECTED_REQUESTS = (
    (
        "POST",
        "/knowledge-ingestion/tasks",
        {"source": "hackaday", "target_month": "2026-07"},
    ),
    ("GET", f"/tasks/{uuid4()}", None),
    ("POST", "/questions", {"question": "What is an ESP32?", "sources": []}),
)


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED_REQUESTS)
@pytest.mark.parametrize("headers", ({}, {"X-Auth-Token": "incorrect-secret"}))
async def test_protected_endpoints_reject_unauthenticated_requests(
    method: str,
    path: str,
    body: dict[str, object] | None,
    headers: dict[str, str],
) -> None:
    app = create_app(Settings(_env_file=None, auth_header="correct-secret"))

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.request(method, path, json=body, headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid authentication token"}


async def test_health_endpoint_is_public() -> None:
    app = create_app(Settings(_env_file=None, auth_header="correct-secret"))

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")

    assert response.status_code == 200
