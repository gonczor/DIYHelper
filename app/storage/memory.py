from app.storage.base import Storage


class MemoryStorage(Storage):
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    async def save(
        self,
        path: str,
        content: bytes,
        *,
        content_type: str | None = None,
    ) -> str:
        del content_type
        self.files[path] = content
        return f"memory://{path}"

    async def load(self, path: str) -> bytes:
        return self.files[path]

    async def list_items(self, prefix: str) -> list[str]:
        return sorted(path for path in self.files if path.startswith(prefix))
