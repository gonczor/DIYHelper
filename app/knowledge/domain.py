from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeSourceName(StrEnum):
    HACKADAY = "hackaday"


class KnowledgeDocument(BaseModel):
    source: KnowledgeSourceName
    title: str
    url: str
    content: str
    published_at: datetime | None = None
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class KnowledgeArticle(BaseModel):
    id: UUID
    source: KnowledgeSourceName
    title: str
    url: str
    content: str
    published_at: datetime | None = None
    token_count: int | None = None
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

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
                f"categories: {', '.join(self.categories)}",
                f"tags: {', '.join(self.tags)}",
                "",
                self.content.strip(),
            )
        )


class StoredKnowledgeReference(BaseModel):
    source: KnowledgeSourceName
    url: str


class KnowledgeReference(StoredKnowledgeReference):
    title: str | None = None
    content: str | None = None
    published_at: datetime | None = None
    token_count: int | None = None

    def as_reference(self) -> str:
        """Format available evidence or retain a locator for a deleted article."""
        if self.content is None:
            return f"Reference URL (document unavailable): {self.url}"
        published_at = self.published_at.isoformat() if self.published_at else ""
        return "\n".join(
            (
                "===== DOCUMENT =====",
                f"source: {self.source}",
                f"url: {self.url}",
                f"title: {self.title or ''}",
                f"published_at: {published_at}",
                "",
                self.content.strip(),
            )
        )


class RankedKnowledgeArticle(BaseModel):
    article: KnowledgeArticle
    rank: float
