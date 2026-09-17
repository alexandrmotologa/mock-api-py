"""Unit and integration tests for URL rewriter middleware and rules."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from mock_api_py.rewriter import URLRewriter
from mock_api_py.server import create_app
from mock_api_py.store import DataStore


def test_rewriter_rules():
    rules = {
        "/api/*": "/$1",
        "/articles/:id": "/posts/:id",
        "/feed": "/products?_sort=price&_order=desc",
    }
    rewriter = URLRewriter(rules)

    # Wildcard
    path, query = rewriter.rewrite("/api/users")
    assert path == "/users"
    assert query is None

    # Parameter
    path, query = rewriter.rewrite("/articles/42")
    assert path == "/posts/42"
    assert query is None

    # Query string target
    path, query = rewriter.rewrite("/feed")
    assert path == "/products"
    assert query == "_sort=price&_order=desc"

    # Non-matching
    path, query = rewriter.rewrite("/unknown/route")
    assert path == "/unknown/route"
    assert query is None


@pytest.mark.asyncio
async def test_rewriter_middleware(tmp_path, sample_data):
    routes_file = tmp_path / "routes.json"
    routes_file.write_text(
        '{"/api/*": "/$1", "/catalog/:id": "/products/:id"}', encoding="utf-8"
    )

    store = DataStore(initial_data=sample_data)
    app = create_app(store=store, routes_file=str(routes_file), enable_logging=False)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Request through /api/products rewritten to /products
        res = await client.get("/api/products")
        assert res.status_code == 200
        assert len(res.json()) == 3

        # Parameter rewrite /catalog/1 rewritten to /products/1
        res_item = await client.get("/catalog/1")
        assert res_item.status_code == 200
        assert res_item.json()["title"] == "Wireless Mouse"


@pytest.mark.asyncio
async def test_targeted_route_mocking(tmp_path, sample_data):
    routes_file = tmp_path / "routes.json"
    rules = {
        "/api/*": "/$1",
        "/billing/checkout": {
            "status": 402,
            "body": {"error": "Payment Required", "code": "CARD_DECLINED"},
            "headers": {"X-Custom-Header": "FastMock-Intercepted"},
        },
        "/special/plain": {
            "status": 200,
            "body": "Hello Plain Text",
            "headers": {"Content-Type": "text/plain"},
        },
        "/admin/only-post": {
            "method": "POST",
            "status": 201,
            "body": {"created": True},
        },
    }
    routes_file.write_text(json.dumps(rules), encoding="utf-8")

    store = DataStore(initial_data=sample_data)
    app = create_app(store=store, routes_file=str(routes_file), enable_logging=False)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Targeted 402 with custom body and header
        res_402 = await client.post("/billing/checkout")
        assert res_402.status_code == 402
        assert res_402.headers["X-Custom-Header"] == "FastMock-Intercepted"
        assert res_402.json() == {"error": "Payment Required", "code": "CARD_DECLINED"}

        # 2. Plain text custom media type
        res_plain = await client.get("/special/plain")
        assert res_plain.status_code == 200
        assert res_plain.text == "Hello Plain Text"
        assert "text/plain" in res_plain.headers["content-type"]

        # 3. Method-specific mock (POST matches, GET falls through)
        res_admin_post = await client.post("/admin/only-post")
        assert res_admin_post.status_code == 201
        assert res_admin_post.json() == {"created": True}

        res_admin_get = await client.get("/admin/only-post")
        assert res_admin_get.status_code == 404  # Not intercepted by mock POST rule, 404 in datastore

