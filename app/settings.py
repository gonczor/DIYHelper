from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import PositiveInt, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    auth_header: SecretStr
    gemini_api_key: SecretStr | None = None
    db_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/diyhelper"

    storage_backend: Literal["local", "gcs"] = "local"
    local_storage_root: Path = PROJECT_ROOT / "data"
    gcs_storage_bucket: str | None = None
    gcs_storage_prefix: str = ""

    knowledge_request_delay_seconds: float = 1.0
    knowledge_request_timeout_seconds: float = 30.0
    knowledge_search_candidate_limit: PositiveInt = 20
    knowledge_article_limit: PositiveInt = 5
    knowledge_token_budget: PositiveInt = 50_000

    @field_validator("local_storage_root")
    @classmethod
    def resolve_local_storage_root(cls, value: Path) -> Path:
        return value if value.is_absolute() else PROJECT_ROOT / value

    @model_validator(mode="after")
    def validate_storage(self) -> "Settings":
        if self.storage_backend == "gcs" and not self.gcs_storage_bucket:
            raise ValueError("GCS_STORAGE_BUCKET is required when STORAGE_BACKEND=gcs")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # populated from the environment
