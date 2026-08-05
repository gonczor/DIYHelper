from typing import Any, Protocol


class TaskHandler(Protocol):
    """Execute one task type using JSON-compatible persisted parameters.

    Handlers are registered by task type in the application composition root.
    This keeps the generic task subsystem unaware of email, ingestion, backups,
    or any other business operation while still allowing a worker to reconstruct
    execution from a durable task ID.
    """

    async def __call__(
        self, parameters: dict[str, Any], progress: "TaskProgress"
    ) -> dict[str, Any]: ...


class TaskProgress(Protocol):
    """Persist generic, JSON-compatible execution details for a task."""

    async def update(self, details: dict[str, Any]) -> None: ...
