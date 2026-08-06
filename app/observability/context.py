from collections.abc import Iterator
from contextlib import contextmanager

from structlog.contextvars import bound_contextvars, clear_contextvars


def clear_observability_context() -> None:
    clear_contextvars()


@contextmanager
def bind_request_id(request_id: str) -> Iterator[None]:
    with bound_contextvars(request_id=request_id):
        yield
