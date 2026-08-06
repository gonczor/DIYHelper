import asyncio
import os
import re
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.db import Base, Database
from app.questions import models as question_models  # noqa: F401 - populate metadata
from app.tasks import models  # noqa: F401 - populate metadata for cleanup


@pytest.fixture(scope="module")
def vcr_config() -> dict:
    return {
        "cassette_library_dir": str(Path(__file__).parent / "cassettes"),
        "filter_headers": ["user-agent"],
        "record_mode": "once",
    }


@pytest.fixture(scope="session")
def test_database_url() -> str:
    database_url = os.getenv(
        "TEST_DB_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/diyhelper_test",
    )
    url = make_url(database_url)
    database_name = url.database or ""
    if re.fullmatch(r"[A-Za-z0-9_]+_test", database_name) is None:
        raise RuntimeError(
            "TEST_DB_URL database name must contain only letters, numbers, underscores "
            "and end in '_test'"
        )

    admin_url = url.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )

    async def recreate_database() -> None:
        connection = await asyncpg.connect(admin_url)
        try:
            await connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                database_name,
            )
            await connection.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
            await connection.execute(f'CREATE DATABASE "{database_name}"')
        finally:
            await connection.close()

    async def drop_database() -> None:
        connection = await asyncpg.connect(admin_url)
        try:
            await connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                database_name,
            )
            await connection.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
        finally:
            await connection.close()

    asyncio.run(recreate_database())
    alembic_config = Config("alembic.ini")
    alembic_config.attributes["database_url"] = database_url
    command.upgrade(alembic_config, "head")
    yield database_url
    asyncio.run(drop_database())


@pytest_asyncio.fixture
async def clean_database(test_database_url: str):
    yield test_database_url

    database = Database(test_database_url)
    async with database.engine.begin() as connection:
        table_names = ", ".join(
            f'"{table.name}"' for table in reversed(Base.metadata.sorted_tables)
        )
        if table_names:
            await connection.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
    await database.close()
