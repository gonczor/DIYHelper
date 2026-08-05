from collections.abc import AsyncIterable

import httpx
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from app.db import Database
from app.knowledge_ingestion.service import KnowledgeIngestionService
from app.knowledge_ingestion.sources.base import KnowledgeSource
from app.knowledge_ingestion.sources.hackaday import HackadaySource
from app.knowledge_ingestion.task_handler import KnowledgeIngestionTaskHandler
from app.settings import Settings
from app.storage.base import Storage
from app.storage.gcs import GCSStorage
from app.storage.local import LocalStorage
from app.tasks.executor import TaskExecutor, get_task_logger
from app.tasks.handlers import TaskHandler
from app.tasks.repository import TaskRepository


class ApplicationProvider(Provider):
    def __init__(
        self,
        settings: Settings,
        storage: Storage | None = None,
        sources: dict[str, KnowledgeSource] | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._storage = storage
        self._sources = sources

    @provide(scope=Scope.APP)
    def settings(self) -> Settings:
        return self._settings

    @provide(scope=Scope.APP)
    async def database(self, settings: Settings) -> AsyncIterable[Database]:
        database = Database(settings.db_url)
        yield database
        await database.close()

    @provide(scope=Scope.APP)
    def storage(self, settings: Settings) -> Storage:
        if self._storage is not None:
            return self._storage
        if settings.storage_backend == "gcs":
            assert settings.gcs_storage_bucket is not None
            return GCSStorage(settings.gcs_storage_bucket, settings.gcs_storage_prefix)
        return LocalStorage(settings.local_storage_root)

    @provide(scope=Scope.REQUEST)
    async def session(self, database: Database) -> AsyncIterable[AsyncSession]:
        async with database.sessions() as session:
            yield session

    @provide(scope=Scope.REQUEST)
    async def http_client(self, settings: Settings) -> AsyncIterable[httpx.AsyncClient]:
        async with httpx.AsyncClient(
            timeout=settings.knowledge_request_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "DIYHelper/0.1 knowledge collector"},
        ) as client:
            yield client

    @provide(scope=Scope.REQUEST)
    def sources(self, client: httpx.AsyncClient, settings: Settings) -> dict[str, KnowledgeSource]:
        if self._sources is not None:
            return self._sources
        return {
            "hackaday": HackadaySource(
                client,
                request_delay_seconds=settings.knowledge_request_delay_seconds,
            )
        }

    @provide(scope=Scope.REQUEST)
    def task_handlers(self, ingestion: KnowledgeIngestionTaskHandler) -> dict[str, TaskHandler]:
        return {"knowledge_ingestion": ingestion}

    @provide(scope=Scope.APP)
    def task_logger(self) -> FilteringBoundLogger:
        return get_task_logger()

    task_repository = provide(TaskRepository, scope=Scope.REQUEST)
    ingestion_service = provide(KnowledgeIngestionService, scope=Scope.REQUEST)
    ingestion_task_handler = provide(KnowledgeIngestionTaskHandler, scope=Scope.REQUEST)
    task_executor = provide(TaskExecutor, scope=Scope.REQUEST)


def create_container(
    settings: Settings,
    *,
    storage: Storage | None = None,
    sources: dict[str, KnowledgeSource] | None = None,
) -> AsyncContainer:
    return make_async_container(ApplicationProvider(settings, storage, sources))
