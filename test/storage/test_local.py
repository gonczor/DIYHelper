from pathlib import Path

import pytest

from app.storage.local import LocalStorage


@pytest.mark.asyncio
async def test_save_writes_below_configured_root(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)

    uri = await storage.save("knowledge/hackaday/2026-07.txt", b"article")

    path = tmp_path / "knowledge/hackaday/2026-07.txt"
    assert path.read_bytes() == b"article"
    assert uri == path.resolve().as_uri()


@pytest.mark.asyncio
async def test_save_rejects_paths_outside_storage_root(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)

    with pytest.raises(ValueError, match="relative storage path"):
        await storage.save("../secret.txt", b"nope")
