from typing import Protocol


class Storage(Protocol):
    async def save(
        self,
        path: str,
        content: bytes,
        *,
        content_type: str | None = None,
    ) -> str: ...

    async def load(self, path: str) -> bytes: ...

    async def list_items(self, prefix: str) -> list[str]: ...
