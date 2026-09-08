"""FastAPI server factory with CORS, dynamic routes, and middleware pipeline."""

from __future__ import annotations

from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mock_api_py.middleware import (
    ChaosErrorMiddleware,
    DelayInjectorMiddleware,
    RequestLoggerMiddleware,
)
from mock_api_py.router import create_mock_router
from mock_api_py.store import DataStore


def create_app(
    store: DataStore,
    delay: Optional[str] = None,
    error_rate: float = 0.0,
    enable_logging: bool = True,
) -> FastAPI:
    """Creates and configures a FastAPI instance with all dynamic routes and middlewares."""
    app = FastAPI(
        title="mock-api-py",
        version="0.1.0",
        description="Instant Modern Mock REST API Engine built on FastAPI",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # 1. Permissive CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count", "Link"],
    )

    # 2. Add Middlewares in correct execution order (Starlette executes bottom-up)
    if enable_logging:
        app.add_middleware(RequestLoggerMiddleware)

    if error_rate > 0:
        app.add_middleware(ChaosErrorMiddleware, error_rate=error_rate)

    if delay:
        app.add_middleware(DelayInjectorMiddleware, delay_spec=delay)

    # 3. Dynamic Routes
    router = create_mock_router(store)
    app.include_router(router)

    # 4. Root Endpoint with System Overview
    @app.get("/", tags=["System"], summary="API Root Overview")
    async def root_overview():
        return {
            "name": "mock-api-py",
            "version": "0.1.0",
            "documentation": "/docs",
            "resources": {
                "collections": store.get_collections(),
                "singletons": store.get_singletons(),
            },
            "status": "online",
        }

    return app
