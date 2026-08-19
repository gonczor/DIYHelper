from datetime import UTC, datetime

import httpx
import pytest

from app.db import Database
from app.main import create_app
from app.questions.models import Conversation
from app.settings import Settings


@pytest.mark.asyncio
async def test_lists_conversations_newest_first_and_requires_authentication(
    clean_database: str,
) -> None:
    database = Database(clean_database)
    async with database.sessions() as session:
        older = Conversation(
            messages=[{"role": "user", "content": "How do I solder an LED?"}],
            created_at=datetime(2026, 8, 18, tzinfo=UTC),
            updated_at=datetime(2026, 8, 18, tzinfo=UTC),
        )
        newer = Conversation(
            messages=[{"role": "user", "content": "Which ESP32 board should I use?"}],
            created_at=datetime(2026, 8, 19, tzinfo=UTC),
            updated_at=datetime(2026, 8, 19, tzinfo=UTC),
        )
        session.add_all([older, newer])
        await session.commit()

    app = create_app(Settings(_env_file=None, auth_header="secret", db_url=clean_database))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/conversations", headers={"X-Auth-Token": "secret"})
            unauthorized = await client.get("/conversations")

    await database.close()
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(newer.id), str(older.id)]
    assert response.json()[0]["title"] == "Which ESP32 board should I use?"
    assert unauthorized.status_code == 401


@pytest.mark.asyncio
async def test_gets_conversation_messages_and_requires_authentication(
    clean_database: str,
) -> None:
    database = Database(clean_database)
    async with database.sessions() as session:
        conversation = Conversation(
            messages=[
                {"role": "user", "content": "What is flux?"},
                {"role": "model", "content": "Flux helps solder flow."},
            ]
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)

    app = create_app(Settings(_env_file=None, auth_header="secret", db_url=clean_database))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/conversations/{conversation.id}", headers={"X-Auth-Token": "secret"}
            )
            unauthorized = await client.get(f"/conversations/{conversation.id}")

    await database.close()
    assert response.status_code == 200
    assert response.json()["messages"] == conversation.messages
    assert unauthorized.status_code == 401


@pytest.mark.asyncio
async def test_deletes_conversation_and_requires_authentication(clean_database: str) -> None:
    database = Database(clean_database)
    async with database.sessions() as session:
        conversation = Conversation(messages=[])
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        conversation_id = conversation.id

    app = create_app(Settings(_env_file=None, auth_header="secret", db_url=clean_database))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            unauthorized = await client.delete(f"/conversations/{conversation_id}")
            response = await client.delete(
                f"/conversations/{conversation_id}", headers={"X-Auth-Token": "secret"}
            )
            missing = await client.get(
                f"/conversations/{conversation_id}", headers={"X-Auth-Token": "secret"}
            )

    await database.close()
    assert unauthorized.status_code == 401
    assert response.status_code == 204
    assert missing.status_code == 404
    assert missing.json() == {"detail": "conversation not found"}
