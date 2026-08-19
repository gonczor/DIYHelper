from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class KnowledgeDocument(BaseModel):
    source: str
    title: str
    url: str
    content: str
    published_at: datetime | None = None


class KnowledgeArticle(KnowledgeDocument):
    id: UUID
    token_count: int | None = None

    def as_reference(self) -> str:
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


class KnowledgeSearchResult(BaseModel):
    search_expression: str
    candidates: list[RankedKnowledgeArticle]
