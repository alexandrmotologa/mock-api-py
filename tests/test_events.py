"""Unit and integration tests for Server-Sent Events (SSE) real-time streaming."""

from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from mock_api_py.events import EventBroadcaster, format_sse
from mock_api_py.server import create_app
from mock_api_py.store import DataStore


def test_format_sse():
    # Simple JSON data
    formatted = format_sse({"msg": "hello"}, event="greeting", event_id="1")
    assert "event: greeting" in formatted
    assert "id: 1" in formatted
    assert 'data: {"msg": "hello"}' in formatted
    assert formatted.endswith("\n\n")

    # Plain text string
    formatted_text = format_sse("line1\nline2")
    assert "data: line1\ndata: line2\n\n" in formatted_text


@pytest.mark.asyncio
async def test_event_broadcaster_pub_sub():
    broadcaster = EventBroadcaster()
    assert broadcaster.subscriber_count == 0

    q1 = broadcaster.subscribe()
    q2 = broadcaster.subscribe()
    assert broadcaster.subscriber_count == 2

    # Broadcast event
    await broadcaster.publish(event="mutation", data={"action": "test"}, collection="items")

    msg1 = await q1.get()
    msg2 = await q2.get()
    assert msg1["event"] == "mutation"
    assert msg1["data"] == {"action": "test"}
    assert msg1["collection"] == "items"
    assert msg2["event"] == "mutation"

    # Unsubscribe
    broadcaster.unsubscribe(q1)
    assert broadcaster.subscriber_count == 1
    broadcaster.unsubscribe(q2)
    assert broadcaster.subscriber_count == 0


@pytest.mark.asyncio
async def test_sse_endpoint_initial_connection():
    store = DataStore(initial_data={"users": [{"id": 1, "name": "Alice"}]})
    broadcaster = EventBroadcaster()
    app = create_app(store=store, broadcaster=broadcaster, enable_logging=False)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Request with limit=1 to receive only initial handshake event
        res = await client.get("/events?limit=1")
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        assert "event: connected" in res.text
        assert "connected" in res.text


@pytest.mark.asyncio
async def test_sse_global_events_mutation_stream():
    store = DataStore(initial_data={"users": [{"id": 1, "name": "Alice"}]})
    broadcaster = EventBroadcaster()
    app = create_app(store=store, broadcaster=broadcaster, enable_logging=False)
    transport = ASGITransport(app=app)

    async with (
        AsyncClient(transport=transport, base_url="http://testserver") as client_stream,
        AsyncClient(transport=transport, base_url="http://testserver") as client_sender,
    ):
        async def trigger_mutation():
            await asyncio.sleep(0.05)
            await client_sender.post("/users", json={"name": "Bob"})

        mutation_task = asyncio.create_task(trigger_mutation())

        # Request limit=2 (event 1: connected, event 2: mutation)
        res = await client_stream.get("/events?limit=2")
        await mutation_task

        assert res.status_code == 200
        assert "event: connected" in res.text
        assert "event: create" in res.text
        assert "Bob" in res.text


@pytest.mark.asyncio
async def test_sse_collection_filtered_stream():
    store = DataStore(initial_data={
        "users": [{"id": 1, "name": "Alice"}],
        "posts": [{"id": 1, "title": "Hello"}],
    })
    broadcaster = EventBroadcaster()
    app = create_app(store=store, broadcaster=broadcaster, enable_logging=False)
    transport = ASGITransport(app=app)

    async with (
        AsyncClient(transport=transport, base_url="http://testserver") as client_stream,
        AsyncClient(transport=transport, base_url="http://testserver") as client_sender,
    ):
        async def trigger_mutations():
            await asyncio.sleep(0.05)
            # 1. Mutate 'posts' -> filtered out by /users/_stream
            await client_sender.post("/posts", json={"title": "World"})
            await asyncio.sleep(0.05)
            # 2. Mutate 'users' -> captured by /users/_stream
            await client_sender.post("/users", json={"name": "Charlie"})

        mutation_task = asyncio.create_task(trigger_mutations())

        # /users/_stream with limit=2 (event 1: connected, event 2: users mutation)
        res = await client_stream.get("/users/_stream?limit=2")
        await mutation_task

        assert res.status_code == 200
        assert "event: connected" in res.text
        assert "event: create" in res.text
        assert "Charlie" in res.text
        assert "World" not in res.text


@pytest.mark.asyncio
async def test_sse_ticker_interval():
    store = DataStore(initial_data={})
    app = create_app(store=store, stream_interval=0.05, enable_logging=False)
    transport = ASGITransport(app=app)

    # Use router lifespan context to execute background ticker task in tests
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://testserver") as client,
    ):
        # Request limit=2 (event 1: connected, event 2: tick)
        res = await client.get("/events?limit=2")
        assert res.status_code == 200
        assert "event: connected" in res.text
        assert "event: tick" in res.text
        assert '"count":' in res.text
