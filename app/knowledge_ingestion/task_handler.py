from typing import Any

from app.knowledge.domain import KnowledgeSourceName
from app.knowledge_ingestion.service import KnowledgeIngestionService
from app.tasks.handlers import TaskProgress


class CollectionProgressReporter:
    def __init__(self, progress: TaskProgress) -> None:
        self._progress = progress

    async def __call__(self, discovered: int, parsed: int, failed: int) -> None:
        await self._progress.update(
            {
                "articles_discovered": discovered,
                "articles_parsed": parsed,
                "articles_failed": failed,
            }
        )


class KnowledgeIngestionTaskHandler:
    """Adapt persisted task parameters to the ingestion application service."""

    def __init__(self, service: KnowledgeIngestionService) -> None:
        self._service = service

    async def __call__(self, parameters: dict[str, Any], progress: TaskProgress) -> dict[str, Any]:
        result = await self._service.ingest(
            source=KnowledgeSourceName(parameters["source"]),
            target_month=parameters["target_month"],
            on_progress=CollectionProgressReporter(progress),
        )
        return result.model_dump(mode="json")
