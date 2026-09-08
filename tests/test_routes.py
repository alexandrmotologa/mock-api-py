"""End-to-end API tests for dynamic routes, singletons, nested routes, and middlewares."""

import time
import pytest
from httpx import ASGITransport, AsyncClient

from mock_api_py.server import create_app
from mock_api_py.store import DataStore


@pytest.mark.asyncio
async def test_root_overview(client):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "mock-api-py"
    assert "products" in data["resources"]["collections"]
    assert "profile" in data["resources"]["singletons"]


@pytest.mark.asyncio
async def test_get_collection_and_headers(client):
    response = await client.get("/products")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert response.headers.get("X-Total-Count") == "3"


@pytest.mark.asyncio
async def test_get_collection_filtered(client):
    response = await client.get("/products?category=electronics&price_lte=50")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Wireless Mouse"


@pytest.mark.asyncio
async def test_get_by_id_and_404(client):
    # Found
    res = await client.get("/products/1")
    assert res.status_code == 200
    assert res.json()["title"] == "Wireless Mouse"

    # Not found
    res_404 = await client.get("/products/999")
    assert res_404.status_code == 404


@pytest.mark.asyncio
async def test_post_create(client):
    new_product = {"title": "Gaming Desk", "price": 149.99, "category": "furniture"}
    res = await client.post("/products", json=new_product)
    assert res.status_code == 201
    created = res.json()
    assert created["id"] == 4
    assert created["title"] == "Gaming Desk"

    # Verify present in listing
    res_list = await client.get("/products/4")
    assert res_list.status_code == 200


@pytest.mark.asyncio
async def test_put_update(client):
    replacement = {"title": "Updated Keyboard", "price": 99.99}
    res = await client.put("/products/2", json=replacement)
    assert res.status_code == 200
    updated = res.json()
    assert updated["id"] == 2
    assert updated["title"] == "Updated Keyboard"
    assert "category" not in updated  # Replaced


@pytest.mark.asyncio
async def test_patch_update(client):
    partial = {"inStock": True}
    res = await client.patch("/products/2", json=partial)
    assert res.status_code == 200
    updated = res.json()
    assert updated["id"] == 2
    assert updated["inStock"] is True
    assert updated["title"] == "Mechanical Keyboard"


@pytest.mark.asyncio
async def test_delete(client):
    res = await client.delete("/products/1")
    assert res.status_code == 200
    assert res.json()["id"] == 1

    # Verify deleted
    res_check = await client.get("/products/1")
    assert res_check.status_code == 404

    # Second delete returns 404
    res_del2 = await client.delete("/products/1")
    assert res_del2.status_code == 404


@pytest.mark.asyncio
async def test_singleton_routes(client):
    # GET
    res = await client.get("/profile")
    assert res.status_code == 200
    assert res.json()["name"] == "Alexandr"

    # PATCH
    res_patch = await client.patch("/profile", json={"status": "live"})
    assert res_patch.status_code == 200
    assert res_patch.json()["status"] == "live"
    assert res_patch.json()["name"] == "Alexandr"


@pytest.mark.asyncio
async def test_nested_relational_routes(client):
    # Products 1 and 2 belong to user 1; Product 3 belongs to user 2
    res_user1_products = await client.get("/users/1/products")
    assert res_user1_products.status_code == 200
    user1_products = res_user1_products.json()
    assert len(user1_products) == 2
    assert all(p["userId"] == 1 for p in user1_products)

    res_user2_products = await client.get("/users/2/products")
    assert res_user2_products.status_code == 200
    user2_products = res_user2_products.json()
    assert len(user2_products) == 1
    assert user2_products[0]["id"] == 3

    # Parent 404
    res_404 = await client.get("/users/999/products")
    assert res_404.status_code == 404


@pytest.mark.asyncio
async def test_read_only_protection(sample_data):
    ro_store = DataStore(initial_data=sample_data, read_only=True)
    app = create_app(store=ro_store, enable_logging=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ro_client:
        res_post = await ro_client.post("/products", json={"title": "Test"})
        assert res_post.status_code == 403

        res_put = await ro_client.put("/products/1", json={"title": "Test"})
        assert res_put.status_code == 403

        res_patch = await ro_client.patch("/products/1", json={"title": "Test"})
        assert res_patch.status_code == 403

        res_del = await ro_client.delete("/products/1")
        assert res_del.status_code == 403


@pytest.mark.asyncio
async def test_delay_middleware(sample_data):
    store = DataStore(initial_data=sample_data)
    app = create_app(store=store, delay="50ms", enable_logging=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as d_client:
        start = time.perf_counter()
        res = await d_client.get("/products")
        elapsed = time.perf_counter() - start
        assert res.status_code == 200
        assert elapsed >= 0.04  # At least ~50ms


@pytest.mark.asyncio
async def test_chaos_middleware(sample_data):
    store = DataStore(initial_data=sample_data)
    # 100% error rate
    app = create_app(store=store, error_rate=1.0, enable_logging=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as chaos_client:
        res = await chaos_client.get("/products")
        assert res.status_code == 500
        assert "Chaos Engine" in res.json()["error"]

        # Docs endpoint should still be accessible even under 100% chaos
        res_docs = await chaos_client.get("/docs")
        assert res_docs.status_code == 200
