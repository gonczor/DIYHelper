from pathlib import Path

import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_local_storage_is_the_default(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, auth_header="test-secret", local_storage_root=tmp_path)

    assert settings.storage_backend == "local"
    assert settings.local_storage_root == tmp_path


def test_relative_local_storage_root_resolves_from_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    settings = Settings(
        _env_file=None,
        auth_header="test-secret",
        local_storage_root="data",
    )

    assert settings.local_storage_root == Path(__file__).resolve().parent.parent / "data"


def test_gcs_storage_requires_a_bucket() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, auth_header="test-secret", storage_backend="gcs")


def test_authentication_secret_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTH_HEADER", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
