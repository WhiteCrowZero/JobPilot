from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from job_pilot.api.v1.router import api_router
from job_pilot.core.config import settings
from job_pilot.core.exceptions import register_exception_handlers
from job_pilot.core.logging import configure_logging
from job_pilot.core.middleware import RequestLoggingMiddleware
from job_pilot.core.resources import AppResources, build_app_resources

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Application startup started")
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    app.state.resources = build_app_resources(settings)
    logger.info("Application startup completed")
    try:
        yield
    finally:
        logger.info("Application shutdown started")
        resources: AppResources | None = getattr(app.state, "resources", None)
        if resources is not None:
            await resources.close()
        logger.info("Application shutdown completed")


def create_app() -> FastAPI:
    configure_logging(settings, service_name="app")

    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        lifespan=lifespan,
        openapi_url=f"{settings.API_PREFIX}/{settings.API_VERSION}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if settings.LOG_REQUEST_ENABLED:
        app.add_middleware(
            RequestLoggingMiddleware,
            skip_paths=settings.LOG_REQUEST_SKIP_PATHS,
        )
    register_exception_handlers(app)
    app.include_router(api_router, prefix=f"{settings.API_PREFIX}/{settings.API_VERSION}")

    return app


app = create_app()
