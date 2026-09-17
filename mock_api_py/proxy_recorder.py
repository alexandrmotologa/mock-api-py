"""Asynchronous ASGI reverse proxy middleware and live traffic VCR recorder."""

from __future__ import annotations

from typing import Any

import httpx
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from mock_api_py.store import DataStore

HOP_BY_HOP_HEADERS: set[str] = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
}

EXCLUDED_PREFIXES: tuple[str, ...] = (
    "/_",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/upload",
    "/uploads",
    "/static",
    "/favicon.ico",
)


def deduce_collection_name(path: str) -> str:
    """
    Deduces resource collection name from the URL path.
    Examples:
      - '/v1/charges' -> 'charges'
      - '/v1/charges/ch_123' -> 'charges'
      - '/api/users' -> 'users'
      - '/users/42' -> 'users'
      - '/users/octocat/repos' -> 'repos'
      - '/orders' -> 'orders'
    """
    clean_path = path.split("?")[0].strip("/")
    if not clean_path:
        return "root"

    parts = [p for p in clean_path.split("/") if p]
    while parts and parts[0].lower() in {"api", "v1", "v2", "v3", "v4", "v5", "rest"}:
        parts.pop(0)

    if not parts:
        return "root"

    last = parts[-1]
    is_id = False
    if last.isdigit() or len(last) == 36 and last.count("-") == 4 or "_" in last and any(c.isdigit() for c in last) or len(parts) >= 2 and (
        parts[-2].endswith("s") or parts[-2].endswith("ies") or parts[-2].endswith("es")
    ):
        is_id = True

    if is_id and len(parts) >= 2:
        return parts[-2].lower()

    return parts[-1].lower()


def record_payload_to_store(store: DataStore, collection: str, payload: Any) -> None:
    """Inserts or updates recorded JSON response objects in the active DataStore."""
    if store is None or store.read_only:
        return

    items: list[dict[str, Any]] = []
    if isinstance(payload, list):
        items = [x for x in payload if isinstance(x, dict)]
    elif isinstance(payload, dict):
        if "data" in payload and isinstance(payload["data"], list):
            items = [x for x in payload["data"] if isinstance(x, dict)]
        elif "items" in payload and isinstance(payload["items"], list):
            items = [x for x in payload["items"] if isinstance(x, dict)]
        elif "results" in payload and isinstance(payload["results"], list):
            items = [x for x in payload["results"] if isinstance(x, dict)]
        else:
            items = [payload]

    for item in items:
        item_id = item.get("id")
        if item_id is not None:
            existing = store.get_by_id(collection, item_id)
            if existing is not None:
                store.update(collection, item_id, item, partial=False)
            else:
                store.create(collection, item)
        else:
            store.create(collection, item)


class ProxyRecorderMiddleware(BaseHTTPMiddleware):
    """
    Transparent reverse proxy ASGI middleware that forwards requests to an upstream URL
    and optionally records live JSON responses to the local mock DataStore.
    """

    def __init__(
        self,
        app: Any,
        upstream_url: str,
        record: bool = False,
        store: DataStore | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(app)
        self.upstream_url = upstream_url.rstrip("/")
        self.record = record
        self.store = store
        self.client = client or httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if any(path.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            return await call_next(request)

        # Build target URL
        target_url = f"{self.upstream_url}{path}"
        if request.url.query:
            target_url = f"{target_url}?{request.url.query}"

        # Strip hop-by-hop headers
        forward_headers = {
            k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP_HEADERS
        }

        body = await request.body()

        try:
            upstream_res = await self.client.request(
                method=request.method,
                url=target_url,
                headers=forward_headers,
                content=body,
            )
        except httpx.RequestError as exc:
            return JSONResponse(
                status_code=502,
                content={"error": "Bad Gateway", "detail": f"Upstream proxy error: {str(exc)}"},
            )

        # Ingest payload into store if record mode is enabled
        if self.record and request.method.upper() == "GET" and 200 <= upstream_res.status_code < 300:
            content_type = upstream_res.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    payload = upstream_res.json()
                    collection = deduce_collection_name(path)
                    if self.store:
                        record_payload_to_store(self.store, collection, payload)
                except Exception:
                    pass

        response_headers = {
            k: v
            for k, v in upstream_res.headers.items()
            if k.lower() not in HOP_BY_HOP_HEADERS
            and k.lower() not in {"content-length", "content-encoding"}
        }

        return Response(
            content=upstream_res.content,
            status_code=upstream_res.status_code,
            headers=response_headers,
            media_type=upstream_res.headers.get("content-type"),
        )
