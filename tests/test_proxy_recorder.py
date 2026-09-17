"""Unit and integration tests for reverse proxy forwarding and VCR recording mode."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport, AsyncClient, Response

from mock_api_py.proxy_recorder import deduce_collection_name
from mock_api_py.server import create_app
from mock_api_py.store import DataStore


def test_deduce_collection_name():
    assert deduce_collection_name("/v1/charges") == "charges"
    assert deduce_collection_name("/v1/charges/ch_99") == "charges"
    assert deduce_collection_name("/api/v2/users") == "users"
    assert deduce_collection_name("/users/42") == "users"
    assert deduce_collection_name("/users/octocat/repos") == "repos"
    assert deduce_collection_name("/orders") == "orders"
    assert deduce_collection_name("/items/018b85b2-70b3-7649-8c20-a619623e1178") == "items"
    assert deduce_collection_name("/") == "root"


@pytest.mark.asyncio
async def test_proxy_forwarding_and_headers():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/charges" and request.method == "GET":
            return Response(
                200,
                headers={"Content-Type": "application/json", "X-Upstream": "true"},
                json=[{"id": "ch_1", "amount": 5000}],
            )
        if request.url.path == "/v1/charges" and request.method == "POST":
            data = json.loads(request.read())
            data["id"] = "ch_new"
            return Response(201, json=data)
        if request.url.path == "/not_found":
            return Response(404, json={"error": "Not Found"})
        return Response(400)

    transport = httpx.MockTransport(mock_handler)
    mock_upstream_client = httpx.AsyncClient(transport=transport)

    store = DataStore(initial_data={})
    app = create_app(
        store=store,
        proxy="https://api.example.com",
        record=False,
        proxy_client=mock_upstream_client,
        enable_logging=False,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Forward GET
        res_get = await client.get("/v1/charges")
        assert res_get.status_code == 200
        assert res_get.headers.get("X-Upstream") == "true"
        assert res_get.json() == [{"id": "ch_1", "amount": 5000}]

        # 2. Forward POST with payload
        res_post = await client.post("/v1/charges", json={"amount": 9900, "currency": "usd"})
        assert res_post.status_code == 201
        assert res_post.json()["id"] == "ch_new"
        assert res_post.json()["amount"] == 9900

        # 3. Status 404 propagation
        res_404 = await client.get("/not_found")
        assert res_404.status_code == 404
        assert res_404.json() == {"error": "Not Found"}

    await mock_upstream_client.aclose()


@pytest.mark.asyncio
async def test_proxy_vcr_record_mode_and_persistence(tmp_path: Path):
    db_file = tmp_path / "recorded_db.json"

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/charges":
            return Response(
                200,
                headers={"Content-Type": "application/json"},
                json=[
                    {"id": "ch_1", "amount": 1000},
                    {"id": "ch_2", "amount": 2500},
                ],
            )
        if request.url.path == "/users/octocat":
            return Response(
                200,
                headers={"Content-Type": "application/json"},
                json={"id": 583231, "login": "octocat", "type": "User"},
            )
        return Response(404)

    transport = httpx.MockTransport(mock_handler)
    mock_upstream_client = httpx.AsyncClient(transport=transport)

    store = DataStore(file_path=db_file, initial_data={}, auto_save=True)
    app = create_app(
        store=store,
        proxy="https://api.example.com",
        record=True,
        proxy_client=mock_upstream_client,
        enable_logging=False,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Request collection
        res1 = await client.get("/v1/charges")
        assert res1.status_code == 200

        # Request single entity with ID in URL
        res2 = await client.get("/users/octocat")
        assert res2.status_code == 200

    # Verify store contains recorded collections
    assert "charges" in store.data
    assert len(store.data["charges"]) == 2
    assert store.get_by_id("charges", "ch_1")["amount"] == 1000

    assert "users" in store.data
    assert len(store.data["users"]) == 1
    assert store.get_by_id("users", 583231)["login"] == "octocat"

    # Verify persistence to file
    assert db_file.exists()
    with open(db_file, encoding="utf-8") as f:
        file_data = json.load(f)
    assert len(file_data["charges"]) == 2
    assert len(file_data["users"]) == 1

    await mock_upstream_client.aclose()


@pytest.mark.asyncio
async def test_proxy_error_handling_502():
    def failing_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused by upstream", request=request)

    transport = httpx.MockTransport(failing_handler)
    mock_client = httpx.AsyncClient(transport=transport)

    store = DataStore(initial_data={})
    app = create_app(
        store=store,
        proxy="https://unreachable.local",
        record=False,
        proxy_client=mock_client,
        enable_logging=False,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/some/endpoint")
        assert res.status_code == 502
        assert "Bad Gateway" in res.text

    await mock_client.aclose()


@pytest.mark.asyncio
async def test_proxy_excluded_internal_routes():
    def upstream_handler(request: httpx.Request) -> httpx.Response:
        return Response(500, text="Should not reach upstream")

    transport = httpx.MockTransport(upstream_handler)
    mock_client = httpx.AsyncClient(transport=transport)

    store = DataStore(initial_data={"users": [{"id": 1, "name": "Alice"}]})
    app = create_app(
        store=store,
        proxy="https://api.example.com",
        proxy_client=mock_client,
        enable_logging=False,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Internal docs endpoint
        res_docs = await client.get("/docs")
        assert res_docs.status_code == 200

        # Internal TypeScript definitions endpoint
        res_types = await client.get("/_types")
        assert res_types.status_code == 200
        assert "export interface User" in res_types.text

        # Internal reset endpoint
        res_reset = await client.post("/_reset")
        assert res_reset.status_code == 200

    await mock_client.aclose()
