import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from fastapi import FastAPI

from app.container import create_container
from app.knowledge_ingestion.api import router as knowledge_ingestion_router
from app.knowledge_ingestion.sources.base import KnowledgeSource
from app.logging_config import configure_logging
from app.settings import Settings, get_settings
from app.storage.base import Storage
from app.tasks.api import router as tasks_router


def create_app(
    settings: Settings | None = None,
    *,
    storage: Storage | None = None,
    sources: dict[str, KnowledgeSource] | None = None,
) -> FastAPI:
    configure_logging()
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = create_container(resolved_settings, storage=storage, sources=sources)
        app.state.settings = resolved_settings
        app.state.container = container
        yield
        await container.close()

    application = FastAPI(title="DIY Helper", lifespan=lifespan)
    application.include_router(knowledge_ingestion_router)
    application.include_router(tasks_router)

    @application.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
