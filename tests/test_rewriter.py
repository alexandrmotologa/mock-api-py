"""Unit and integration tests for URL rewriter middleware and rules."""

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
