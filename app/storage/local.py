import os
import tempfile
from pathlib import Path, PurePosixPath


class LocalStorage:
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
