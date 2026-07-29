"""FastAPI application entry point."""

from fastapi import FastAPI

from irma.api.routes import router
from irma.config import get_settings

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Experimental rule-based investment allocation backend for IRMA.",
)
app.include_router(router)
