from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from job_pilot.api.v1.router import api_router
from job_pilot.core.config import settings
from job_pilot.core.exceptions import register_exception_handlers
from job_pilot.core.resources import AppResources, build_app_resources


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    app.state.resources = build_app_resources(settings)
    try:
        yield
    finally:
        resources: AppResources | None = getattr(app.state, "resources", None)
        if resources is not None:
            await resources.close()


def create_app() -> FastAPI:
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
    register_exception_handlers(app)
    app.include_router(api_router, prefix=f"{settings.API_PREFIX}/{settings.API_VERSION}")

    return app


app = create_app()
