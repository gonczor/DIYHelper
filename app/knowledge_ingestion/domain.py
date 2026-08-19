from pydantic import BaseModel

from app.knowledge.domain import KnowledgeDocument


class CollectionResult(BaseModel):
    documents: list[KnowledgeDocument]
    discovered: int
    failed: int


class IngestionResult(BaseModel):
    artifact_uri: str
    articles_discovered: int
    articles_saved: int
    articles_failed: int
