"""Integration tests for embedded Web Admin Dashboard."""

import pytest
from httpx import ASGITransport, AsyncClient

from mock_api_py.server import create_app
from mock_api_py.store import DataStore


@pytest.mark.asyncio
async def test_admin_dashboard_endpoint(sample_data):
    store = DataStore(initial_data=sample_data)
    app = create_app(store=store, enable_logging=False)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/_admin")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        html = response.text
        assert "mock-api Studio" in html
        assert "Collections" in html
        assert "Singletons" in html
        assert "TypeScript" in html
        assert "Reset DB" in html
        assert "ts-modal" in html

