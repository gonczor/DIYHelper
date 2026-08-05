from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.knowledge_ingestion.service import _month_bounds


class CreateIngestionTaskRequest(BaseModel):
    source: Literal["hackaday"] = "hackaday"
    target_month: str | None = Field(default=None, examples=["2026-07"])

    @field_validator("target_month")
    @classmethod
    def validate_target_month(cls, value: str | None) -> str | None:
        if value is not None:
            _month_bounds(value)
        return value

    def resolved_target_month(self) -> str:
        if self.target_month is not None:
            return self.target_month
        today = datetime.now(UTC)
        previous_month_last_day = (today.replace(day=1) - timedelta(days=1)).date()
        return previous_month_last_day.strftime("%Y-%m")
