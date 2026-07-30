"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from irma import __version__
from irma.api.routes import router
from irma.config import get_settings
from irma.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Iran-focused investment research and explainable allocation API. "
            "No guaranteed return, live trading, or automatic order execution."
        ),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[item.strip() for item in settings.cors_origins.split(",") if item.strip()],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-IRMA-Admin-Key"],
    )
    application.include_router(router)
    return application


app = create_app()
