from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import datetime

from app.knowledge_ingestion.domain import CollectionResult

CollectionProgressCallback = Callable[[int, int, int], Awaitable[None]]


class KnowledgeSource(ABC):
    """Base contract for gathering normalized documents from one source."""

    @abstractmethod
    async def collect(
        self,
        start: datetime,
        end: datetime,
        on_progress: CollectionProgressCallback | None = None,
    ) -> CollectionResult:
        raise NotImplementedError
