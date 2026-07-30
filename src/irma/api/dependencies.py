"""FastAPI dependencies."""

import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from irma.config import get_settings


def require_admin_key(x_irma_admin_key: Annotated[str | None, Header()] = None) -> None:
    configured = get_settings().admin_key
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin refresh is disabled until IRMA_ADMIN_KEY is configured",
        )
    if x_irma_admin_key is None or not secrets.compare_digest(x_irma_admin_key, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin key")
