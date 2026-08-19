from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class KnowledgeSourceName(StrEnum):
    HACKADAY = "hackaday"


class KnowledgeDocument(BaseModel):
    source: KnowledgeSourceName
    title: str
    url: str
    content: str
    published_at: datetime | None = None


class KnowledgeArticle(BaseModel):
    id: UUID
    source: KnowledgeSourceName
    title: str
    url: str
    content: str
    published_at: datetime | None = None
    token_count: int | None = None

    def as_reference(self) -> str:
        """Format a complete article as untrusted reference context for the model prompt."""
        published_at = self.published_at.isoformat() if self.published_at else ""
        return "\n".join(
            (
                "===== DOCUMENT =====",
                f"source: {self.source}",
                f"url: {self.url}",
                f"title: {self.title}",
                f"published_at: {published_at}",
                "",
                self.content.strip(),
            )
        )


class RankedKnowledgeArticle(BaseModel):
    article: KnowledgeArticle
    rank: float
