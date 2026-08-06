from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ConversationMessage(BaseModel):
    role: Literal["user", "model"]
    content: str


class QuestionEvent(BaseModel):
    event: Literal["metadata", "text", "done", "error"]
    conversation_id: UUID | None = None
    text: str | None = None
    message: str | None = None
