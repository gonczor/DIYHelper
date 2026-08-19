from collections.abc import AsyncIterable

import httpx
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from google import genai
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Database
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.service import KnowledgeSelectionService, TokenCounter
from app.knowledge_ingestion.service import KnowledgeIngestionService
from app.knowledge_ingestion.sources.base import KnowledgeSource
from app.knowledge_ingestion.sources.hackaday import HackadaySource
from app.knowledge_ingestion.task_handler import KnowledgeIngestionTaskHandler
from app.questions.gemini import GeminiGateway, GeminiGatewayProtocol
from app.questions.repository import ConversationRepository
from app.questions.service import QuestionService
from app.settings import Settings
from app.storage.base import Storage
from app.storage.gcs import GCSStorage
from app.storage.local import LocalStorage
from app.tasks.executor import TaskExecutor
from app.tasks.handlers import TaskHandler
from app.tasks.repository import TaskRepository


class ApplicationProvider(Provider):
    def __init__(
        self,
        settings: Settings,
        storage: Storage | None = None,
        sources: dict[str, KnowledgeSource] | None = None,
        gemini_client: genai.Client | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._storage = storage
        self._sources = sources
        self._gemini_client = gemini_client

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

    @provide(scope=Scope.APP)
    async def gemini_client(self, settings: Settings) -> AsyncIterable[genai.Client]:
        client = self._gemini_client
        if client is None:
            if settings.gemini_api_key is None:
                raise RuntimeError("GEMINI_API_KEY is required to answer questions")
            client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
        yield client
        await client.aio.aclose()

    @provide(scope=Scope.APP)
    def gemini_gateway(self, client: genai.Client) -> GeminiGatewayProtocol:
        return GeminiGateway(client)

    @provide(scope=Scope.REQUEST)
    def token_counter(self, gemini: GeminiGatewayProtocol) -> TokenCounter:
        return gemini

    @provide(scope=Scope.REQUEST)
    def knowledge_selection_service(
        self,
        repository: KnowledgeRepository,
        token_counter: TokenCounter,
        settings: Settings,
    ) -> KnowledgeSelectionService:
        return KnowledgeSelectionService(
            repository,
            token_counter,
            candidate_limit=settings.knowledge_search_candidate_limit,
            article_limit=settings.knowledge_article_limit,
            token_budget=settings.knowledge_token_budget,
        )

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

    task_repository = provide(TaskRepository, scope=Scope.REQUEST)
    conversation_repository = provide(ConversationRepository, scope=Scope.REQUEST)
    knowledge_repository = provide(KnowledgeRepository, scope=Scope.REQUEST)
    question_service = provide(QuestionService, scope=Scope.REQUEST)
    ingestion_service = provide(KnowledgeIngestionService, scope=Scope.REQUEST)
    ingestion_task_handler = provide(KnowledgeIngestionTaskHandler, scope=Scope.REQUEST)
    task_executor = provide(TaskExecutor, scope=Scope.REQUEST)


def create_container(
    settings: Settings,
    *,
    storage: Storage | None = None,
    sources: dict[str, KnowledgeSource] | None = None,
    gemini_client: genai.Client | None = None,
) -> AsyncContainer:
    return make_async_container(ApplicationProvider(settings, storage, sources, gemini_client))
