import os
import tempfile
from pathlib import Path, PurePosixPath

from app.storage.base import Storage


class LocalStorage(Storage):
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    async def save(
        self,
        path: str,
        content: bytes,
        *,
        content_type: str | None = None,
    ) -> str:
        del content_type
        relative = PurePosixPath(path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("path must be a relative storage path")

        destination = self._root.joinpath(*relative.parts)
        self._write_atomically(destination, content)
        return destination.as_uri()

    async def load(self, path: str) -> bytes:
        return self._resolve(path).read_bytes()

    async def list_items(self, prefix: str) -> list[str]:
        directory = self._resolve(prefix)
        if not directory.exists():
            return []
        return sorted(
            path.relative_to(self._root).as_posix()
            for path in directory.rglob("*")
            if path.is_file()
        )

    def _resolve(self, path: str) -> Path:
        relative = PurePosixPath(path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("path must be a relative storage path")
        return self._root.joinpath(*relative.parts)

    @staticmethod
    def _write_atomically(destination: Path, content: bytes) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(dir=destination.parent)
        try:
            with os.fdopen(file_descriptor, "wb") as temporary_file:
                temporary_file.write(content)
            os.replace(temporary_name, destination)
        except BaseException:
            Path(temporary_name).unlink(missing_ok=True)
            raise
