"""Shared fixtures for mock-api-py tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from mock_api_py.server import create_app
from mock_api_py.store import DataStore


@pytest.fixture
def sample_data():
    return {
        "products": [
            {
                "id": 1,
                "title": "Wireless Mouse",
                "price": 29.99,
                "category": "electronics",
                "inStock": True,
                "userId": 1,
            },
            {
                "id": 2,
                "title": "Mechanical Keyboard",
                "price": 89.99,
                "category": "electronics",
                "inStock": False,
                "userId": 1,
            },
            {
                "id": 3,
                "title": "Noise Cancelling Headphones",
                "price": 199.99,
                "category": "audio",
                "inStock": True,
                "userId": 2,
            },
        ],
        "users": [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"},
        ],
        "profile": {
            "name": "Alexandr",
            "status": "building",
        },
    }


@pytest.fixture
def store(sample_data):
    return DataStore(initial_data=sample_data)


@pytest.fixture
async def client(store):
    app = create_app(store=store, enable_logging=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
