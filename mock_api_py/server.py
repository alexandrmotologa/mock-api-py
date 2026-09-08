from contextlib import asynccontextmanager
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from rich.console import Console

from mock_api_py.admin import create_admin_router
from mock_api_py.auth import AuthMiddleware, create_auth_router, DEFAULT_SECRET
from mock_api_py.middleware import (
    ChaosErrorMiddleware,
    DelayInjectorMiddleware,
    RequestLoggerMiddleware,
)
from mock_api_py.rewriter import URLRewriter, URLRewriterMiddleware
from mock_api_py.router import create_mock_router
from mock_api_py.store import DataStore

console = Console()


def create_app(
    store: DataStore,
    delay: Optional[str] = None,
    error_rate: float = 0.0,
    enable_logging: bool = True,
    watch: bool = False,
    static_dir: Optional[str] = None,
    enable_auth: bool = False,
    jwt_secret: str = DEFAULT_SECRET,
    routes_file: Optional[str] = None,
) -> FastAPI:
    """Creates and configures a FastAPI instance with all dynamic routes and middlewares."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        watch_task = None
        if watch and store.file_path:
            async def _watch_loop():
                while True:
                    try:
                        await asyncio.sleep(0.5)
                        if store.check_and_reload():
                            console.print(
                                f"[dim yellow][WATCH][/dim yellow] [yellow]External file modification detected. "
                                f"Reloaded '{store.file_path.name}'.[/yellow]"
                            )
                    except asyncio.CancelledError:
                        break
                    except Exception:
                        pass

            watch_task = asyncio.create_task(_watch_loop())

        try:
            yield
        finally:
            if watch_task:
                watch_task.cancel()

    app = FastAPI(
        title="mock-api-py",
        version="0.1.0",
        description="Instant Modern Mock REST API Engine built on FastAPI",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
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

    if enable_auth:
        app.add_middleware(AuthMiddleware, secret=jwt_secret)

    if error_rate > 0:
        app.add_middleware(ChaosErrorMiddleware, error_rate=error_rate)

    if delay:
        app.add_middleware(DelayInjectorMiddleware, delay_spec=delay)

    if routes_file:
        rewriter = URLRewriter.from_file(routes_file)
        app.add_middleware(URLRewriterMiddleware, rewriter=rewriter)

    # 3. Dynamic Routes & Auth Router
    if enable_auth:
        auth_router = create_auth_router(store, secret=jwt_secret)
        app.include_router(auth_router)

    router = create_mock_router(store)
    app.include_router(router)

    # 4. Embedded Web Admin Dashboard
    admin_router = create_admin_router()
    app.include_router(admin_router)

    # 5. Static Files Mount (optional)
    if static_dir:
        static_path = Path(static_dir)
        if static_path.exists():
            app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    # 6. Root Endpoint with System Overview
    @app.get("/", tags=["System"], summary="API Root Overview")
    async def root_overview():
        return {
            "name": "mock-api-py",
            "version": "0.1.0",
            "documentation": "/docs",
            "admin_dashboard": "/_admin",
            "auth_enabled": enable_auth,
            "resources": {
                "collections": store.get_collections(),
                "singletons": store.get_singletons(),
            },
            "status": "online",
        }

    return app
