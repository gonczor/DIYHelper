import re
from calendar import monthrange
from datetime import UTC, datetime

from app.knowledge.domain import KnowledgeDocument
from app.knowledge.repository import KnowledgeRepository
from app.knowledge_ingestion.domain import IngestionResult
from app.knowledge_ingestion.sources.base import CollectionProgressCallback, KnowledgeSource
from app.storage.base import Storage


class KnowledgeIngestionService:
    def __init__(
        self,
        sources: dict[str, KnowledgeSource],
        storage: Storage,
        repository: KnowledgeRepository,
    ) -> None:
        self._sources = sources
        self._storage = storage
        self._repository = repository

    async def ingest(
        self,
        source: str,
        target_month: str,
        on_progress: CollectionProgressCallback | None = None,
    ) -> IngestionResult:
        connector = self._sources.get(source)
        if connector is None:
            raise ValueError(f"unknown knowledge source: {source}")

        start, end = _month_bounds(target_month)
        collection = await connector.collect(start, end, on_progress)
        if not collection.documents:
            raise RuntimeError(f"no documents collected for {source} in {target_month}")

        content = _serialize(collection.documents).encode()
        path = f"knowledge/{source}/{target_month}.txt"
        artifact_uri = await self._storage.save(
            path, content, content_type="text/plain; charset=utf-8"
        )
        await self._repository.upsert_documents(collection.documents)
        return IngestionResult(
            artifact_uri=artifact_uri,
            articles_discovered=collection.discovered,
            articles_saved=len(collection.documents),
            articles_failed=collection.failed,
        )


def _month_bounds(target_month: str) -> tuple[datetime, datetime]:
    if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", target_month) is None:
        raise ValueError("target_month must use YYYY-MM format")
    try:
        year_text, month_text = target_month.split("-", maxsplit=1)
        year, month = int(year_text), int(month_text)
        monthrange(year, month)
    except (ValueError, TypeError) as error:
        raise ValueError("target_month must use YYYY-MM format") from error

    start = datetime(year, month, 1, tzinfo=UTC)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(year, month + 1, 1, tzinfo=UTC)
    return start, end


def _serialize(documents: list[KnowledgeDocument]) -> str:
    ordered = sorted(
        documents,
        key=lambda item: (item.published_at or datetime.min.replace(tzinfo=UTC), item.url),
    )
    sections = []
    for document in ordered:
        published_at = document.published_at.isoformat() if document.published_at else ""
        sections.append(
            "\n".join(
                (
                    "===== DOCUMENT =====",
                    f"source: {document.source}",
                    f"url: {document.url}",
                    f"title: {document.title}",
                    f"published_at: {published_at}",
                    "",
                    document.content.strip(),
                )
            )
        )
    return "\n\n".join(sections) + "\n"
