from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.knowledge.domain import KnowledgeSourceName, StoredKnowledgeReference


class AskQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4_000)
    sources: list[KnowledgeSourceName] | None = None
    conversation_id: UUID | None = None

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped

    @field_validator("sources", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, list):
            return value
        normalized: list[object] = []
        for source in value:
            if isinstance(source, str):
                source = source.strip().lower()
                if not source:
                    continue
            if source not in normalized:
                normalized.append(source)
        return normalized


class ConversationMessageResponse(BaseModel):
    role: Literal["user", "model"]
    content: str
    references: list[StoredKnowledgeReference] = Field(default_factory=list)


class ConversationSummaryResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    messages: list[ConversationMessageResponse]
    created_at: datetime
    updated_at: datetime
