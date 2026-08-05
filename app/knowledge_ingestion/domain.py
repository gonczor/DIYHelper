from datetime import datetime

from pydantic import BaseModel


class KnowledgeDocument(BaseModel):
    source: str
    source_id: str
    title: str
    url: str
    content: str
    published_at: datetime | None = None


class CollectionResult(BaseModel):
    documents: list[KnowledgeDocument]
    discovered: int
    failed: int


class IngestionResult(BaseModel):
    artifact_uri: str
    articles_discovered: int
    articles_saved: int
    articles_failed: int
