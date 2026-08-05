import secrets
from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from app.settings import Settings


async def require_authorized_actor(
    request: Request,
    token: Annotated[str | None, Header(alias="X-Auth-Token")] = None,
) -> None:
    settings: Settings = request.app.state.settings
    if token is None or not secrets.compare_digest(token, settings.auth_header.get_secret_value()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication token"
        )
