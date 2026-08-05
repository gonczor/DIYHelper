from typing import Any

from app.knowledge_ingestion.service import KnowledgeIngestionService
from app.tasks.handlers import TaskProgress


class KnowledgeIngestionTaskHandler:
    """Adapt persisted task parameters to the ingestion application service."""

    def __init__(self, service: KnowledgeIngestionService) -> None:
        self._service = service

    async def __call__(self, parameters: dict[str, Any], progress: TaskProgress) -> dict[str, Any]:
        async def report(discovered: int, parsed: int, failed: int) -> None:
            await progress.update(
                {
                    "articles_discovered": discovered,
                    "articles_parsed": parsed,
                    "articles_failed": failed,
                }
            )

        result = await self._service.ingest(
            source=parameters["source"],
            target_month=parameters["target_month"],
            on_progress=report,
        )
        return result.model_dump(mode="json")
