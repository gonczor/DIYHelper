from typing import Any

import pytest
from sqlalchemy import inspect
from sqlalchemy.engine import Connection

from app.db import Database


@pytest.mark.asyncio
async def test_conversations_updated_at_is_indexed(clean_database: str) -> None:
    database = Database(clean_database)
    async with database.engine.connect() as connection:
        indexes = await connection.run_sync(_conversation_indexes)
    await database.close()

    assert any(index["name"] == "ix_conversations_updated_at" for index in indexes)


def _conversation_indexes(connection: Connection) -> list[dict[str, Any]]:
    return inspect(connection).get_indexes("conversations")
