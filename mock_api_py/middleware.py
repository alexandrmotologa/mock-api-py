"""ASGI middlewares for latency simulation, chaos error injection, and rich request logging."""

from __future__ import annotations

import asyncio
import random
import re
import time
from datetime import datetime
from typing import Optional, Tuple

from rich.console import Console
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

console = Console()

DOCS_PATHS = {"/docs", "/redoc", "/openapi.json", "/favicon.ico"}


def parse_delay_arg(delay_arg: Optional[str]) -> Optional[Tuple[float, float]]:
    """
    Parses delay input into (min_seconds, max_seconds).
    Supports:
      - 500 or "500" or "500ms" -> (0.5, 0.5)
      - "200-800" or "200-800ms" -> (0.2, 0.8)
    """
    if delay_arg is None:
        return None

    cleaned = str(delay_arg).strip().lower().rstrip("ms")
    if "-" in cleaned:
        parts = cleaned.split("-", 1)
        try:
            min_ms = float(parts[0].strip())
            max_ms = float(parts[1].strip())
            return (min(min_ms, max_ms) / 1000.0, max(min_ms, max_ms) / 1000.0)
        except ValueError:
            return None

    try:
        val_ms = float(cleaned)
        return (val_ms / 1000.0, val_ms / 1000.0)
    except ValueError:
        return None


class DelayInjectorMiddleware(BaseHTTPMiddleware):
    """Injects fixed or randomized artificial latency before processing the request."""

    def __init__(self, app, delay_spec: Optional[str] = None):
        super().__init__(app)
        self.delay_range = parse_delay_arg(delay_spec)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self.delay_range and request.url.path not in DOCS_PATHS:
            min_delay, max_delay = self.delay_range
            sleep_duration = random.uniform(min_delay, max_delay)
            if sleep_duration > 0:
                await asyncio.sleep(sleep_duration)

        return await call_next(request)


class ChaosErrorMiddleware(BaseHTTPMiddleware):
    """Randomly injects HTTP 500 Internal Server Errors based on the configured error rate."""

    def __init__(self, app, error_rate: float = 0.0):
        super().__init__(app)
        self.error_rate = max(0.0, min(1.0, float(error_rate or 0.0)))

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self.error_rate > 0 and request.url.path not in DOCS_PATHS:
            if random.random() < self.error_rate:
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "Chaos Engine: Simulated 500 Internal Server Error",
                        "path": request.url.path,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

        return await call_next(request)


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Logs incoming requests and elapsed execution time to the Rich console."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Don't log favicon requests to keep console clean
        if request.url.path == "/favicon.ico":
            return await call_next(request)

        start_time = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        method = request.method
        full_path = request.url.path
        if request.url.query:
            full_path += f"?{request.url.query}"

        status_code = response.status_code
        status_text = response.status_code

        # Color coding status
        if 200 <= status_code < 300:
            status_style = "bold green"
        elif 300 <= status_code < 400:
            status_style = "bold blue"
        elif 400 <= status_code < 500:
            status_style = "bold yellow"
        else:
            status_style = "bold red"

        # Method color
        method_colors = {
            "GET": "cyan",
            "POST": "green",
            "PUT": "yellow",
            "PATCH": "magenta",
            "DELETE": "red",
        }
        method_style = method_colors.get(method, "white")

        console.print(
            f"[dim]\\[{now_str}][/dim] "
            f"[{method_style}]{method: <6}[/{method_style}] "
            f"[white]{full_path}[/white] - "
            f"[{status_style}]{status_code}[/{status_style}] "
            f"[dim]({elapsed_ms:.1f}ms)[/dim]"
        )

        return response
