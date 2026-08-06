from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AskQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4_000)
    sources: list[str] | None = None
    conversation_id: UUID | None = None

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped

    @field_validator("sources")
    @classmethod
    def normalize_sources(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = list(
            dict.fromkeys(source.strip().lower() for source in value if source.strip())
        )
        return normalized
