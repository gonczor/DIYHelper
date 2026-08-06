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


@pytest.mark.asyncio
async def test_load_and_list_saved_artifacts(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    await storage.save("knowledge/hackaday/2026-07.txt", b"july")
    await storage.save("knowledge/hackaday/2026-06.txt", b"june")
    await storage.save("knowledge/other/2026-07.txt", b"other")

    paths = await storage.list_items("knowledge/hackaday/")

    assert paths == [
        "knowledge/hackaday/2026-06.txt",
        "knowledge/hackaday/2026-07.txt",
    ]
    assert await storage.load(paths[1]) == b"july"
