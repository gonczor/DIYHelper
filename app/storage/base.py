from typing import Protocol


class Storage(Protocol):
    async def save(
        self,
        path: str,
        content: bytes,
        *,
        content_type: str | None = None,
    ) -> str: ...
