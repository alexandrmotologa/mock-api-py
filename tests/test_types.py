import pytest
from httpx import ASGITransport, AsyncClient
from mock_api_py.store import DataStore
from mock_api_py.server import create_app
from mock_api_py.types_generator import generate_typescript_definitions, _to_pascal_case


def test_pascal_case_conversion():
    assert _to_pascal_case("users") == "User"
    assert _to_pascal_case("categories") == "Category"
    assert _to_pascal_case("boxes") == "Box"
    assert _to_pascal_case("blog_posts") == "BlogPost"
    assert _to_pascal_case("order-items") == "OrderItem"
    assert _to_pascal_case("profile") == "Profile"


def test_generate_typescript_definitions():
    store = DataStore(
        initial_data={
            "users": [
                {"id": 1, "name": "Alice", "email": "alice@example.com", "active": True},
                {"id": 2, "name": "Bob", "email": "bob@example.com", "role": "admin"},
            ],
            "settings": {"theme": "dark", "version": 2},
        }
    )

    ts = generate_typescript_definitions(store)
    assert "export interface User {" in ts
    assert "id: number;" in ts
    assert "name: string;" in ts
    assert "email: string;" in ts
    # role is not in item 1, so it should be optional
    assert "role?: string;" in ts
    assert "export interface Setting {" in ts or "export interface Settings {" in ts
    assert "export interface Database {" in ts
    assert "users: User[];" in ts


@pytest.mark.anyio
async def test_types_http_endpoint():
    store = DataStore(
        initial_data={
            "articles": [
                {"id": 101, "title": "Understanding Mock APIs", "views": 1500}
            ]
        }
    )
    app = create_app(store)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/_types")
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/plain")
        body = res.text
        assert "export interface Article {" in body
        assert "title: string;" in body
        assert "views: number;" in body
        assert "export interface Database {" in body
