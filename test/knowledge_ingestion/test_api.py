from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select

from app.db import Database
from app.knowledge.models import KnowledgeArticleRecord
from app.knowledge_ingestion.domain import CollectionResult, KnowledgeDocument
from app.main import create_app
from app.settings import Settings
from app.storage.memory import MemoryStorage
from app.tasks.models import Task
from app.tasks.types import TaskStatus


class StubHackadaySource:
    async def collect(self, start: datetime, end: datetime, on_progress=None) -> CollectionResult:
        if on_progress is not None:
            await on_progress(1, 1, 0)
        return CollectionResult(
            documents=[
                KnowledgeDocument(
                    source="hackaday",
                    title="Recorded article",
                    url="https://hackaday.com/recorded-article/",
                    content="An integration-test article.",
                    published_at=datetime(2026, 7, 1, tzinfo=UTC),
                )
            ],
            discovered=1,
            failed=0,
        )


@pytest.mark.asyncio
async def test_create_task_runs_ingestion_and_persists_result(clean_database: str) -> None:
    storage = MemoryStorage()
    settings = Settings(
        _env_file=None,
        auth_header="integration-secret",
        db_url=clean_database,
        knowledge_request_delay_seconds=0,
    )
    app = create_app(settings, storage=storage, sources={"hackaday": StubHackadaySource()})

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/knowledge-ingestion/tasks",
                headers={"X-Auth-Token": "integration-secret"},
                json={"source": "hackaday", "target_month": "2026-07"},
            )
            task_id = response.json()["id"]
            status_response = await client.get(
                f"/tasks/{task_id}",
                headers={"X-Auth-Token": "integration-secret"},
            )

    assert response.status_code == 202
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "SUCCEEDED"
    assert status_response.json()["details"] == {
        "articles_discovered": 1,
        "articles_parsed": 1,
        "articles_failed": 0,
    }
    assert "knowledge/hackaday/2026-07.txt" in storage.files

    database = Database(clean_database)
    async with database.sessions() as session:
        persisted_task = await session.scalar(select(Task).where(Task.id == task_id))
        article = await session.scalar(select(KnowledgeArticleRecord))
    await database.close()

    assert persisted_task is not None
    assert article is not None
    assert article.url == "https://hackaday.com/recorded-article/"
    assert persisted_task.status is TaskStatus.SUCCEEDED
    assert persisted_task.request_id is not None
    UUID(persisted_task.request_id)
    assert persisted_task.details == {
        "articles_discovered": 1,
        "articles_parsed": 1,
        "articles_failed": 0,
    }
    assert persisted_task.result == {
        "artifact_uri": "memory://knowledge/hackaday/2026-07.txt",
        "articles_discovered": 1,
        "articles_saved": 1,
        "articles_failed": 0,
    }


@pytest.mark.asyncio
async def test_task_not_found_is_handled_by_the_application(clean_database: str) -> None:
    app = create_app(
        Settings(_env_file=None, auth_header="integration-secret", db_url=clean_database)
    )

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/tasks/{uuid4()}", headers={"X-Auth-Token": "integration-secret"}
            )

    assert response.status_code == 404
    assert response.json() == {"detail": "task not found"}


@pytest.mark.asyncio
async def test_active_ingestion_task_is_handled_by_the_application(
    clean_database: str,
) -> None:
    database = Database(clean_database)
    async with database.sessions() as session:
        session.add(
            Task(
                type="knowledge_ingestion",
                status=TaskStatus.PENDING,
                parameters={"source": "hackaday", "target_month": "2026-07"},
            )
        )
        await session.commit()
    await database.close()
    app = create_app(
        Settings(_env_file=None, auth_header="integration-secret", db_url=clean_database)
    )

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/knowledge-ingestion/tasks",
                headers={"X-Auth-Token": "integration-secret"},
                json={"source": "hackaday", "target_month": "2026-07"},
            )

    assert response.status_code == 409
    assert response.json() == {"detail": "an active hackaday task already exists for 2026-07"}
