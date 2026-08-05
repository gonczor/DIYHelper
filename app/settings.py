from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    auth_header: SecretStr
    db_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/diyhelper"

    storage_backend: Literal["local", "gcs"] = "local"
    local_storage_root: Path = Path("data")
    gcs_storage_bucket: str | None = None
    gcs_storage_prefix: str = ""

    knowledge_request_delay_seconds: float = 1.0
    knowledge_request_timeout_seconds: float = 30.0

    @model_validator(mode="after")
    def validate_storage(self) -> "Settings":
        if self.storage_backend == "gcs" and not self.gcs_storage_bucket:
            raise ValueError("GCS_STORAGE_BUCKET is required when STORAGE_BACKEND=gcs")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # populated from the environment
