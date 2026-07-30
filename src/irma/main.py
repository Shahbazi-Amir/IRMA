"""FastAPI application entry point."""

import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from irma import __version__
from irma.api.routes import router
from irma.config import get_settings
from irma.logging import configure_logging, request_id_context


class OperationalMiddleware(BaseHTTPMiddleware):
    """Attach request IDs, timing and conservative security headers."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:128]
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_context.reset(token)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.2f}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


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
        allow_headers=["Content-Type", "X-IRMA-Admin-Key", "X-Request-ID"],
    )
    application.add_middleware(OperationalMiddleware)
    application.include_router(router)
    return application


app = create_app()
