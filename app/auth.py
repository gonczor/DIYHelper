import secrets
from typing import Annotated

from fastapi import Header, Request

from app.settings import Settings


class InvalidAuthenticationTokenError(Exception):
    pass


async def require_authorized_actor(
    request: Request,
    token: Annotated[str | None, Header(alias="X-Auth-Token")] = None,
) -> None:
    settings: Settings = request.app.state.settings
    if token is None or not secrets.compare_digest(token, settings.auth_header.get_secret_value()):
        raise InvalidAuthenticationTokenError("invalid authentication token")
