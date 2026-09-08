"""Unit and E2E tests for mock authentication, JWT tokens, and AuthMiddleware."""

import pytest
from httpx import ASGITransport, AsyncClient

from mock_api_py.auth import create_access_token, verify_access_token
from mock_api_py.server import create_app
from mock_api_py.store import DataStore


def test_jwt_generation_and_verification():
    payload = {"sub": "1", "email": "test@example.com", "role": "admin"}
    token = create_access_token(payload, secret="test-secret", expires_in=3600)
    assert isinstance(token, str)
    assert len(token.split(".")) == 3

    verified = verify_access_token(token, secret="test-secret")
    assert verified is not None
    assert verified["sub"] == "1"
    assert verified["email"] == "test@example.com"
    assert verified["role"] == "admin"

    # Wrong secret fails
    assert verify_access_token(token, secret="wrong-secret") is None

    # Expired token fails
    expired_token = create_access_token(payload, secret="test-secret", expires_in=-10)
    assert verify_access_token(expired_token, secret="test-secret") is None


@pytest.mark.asyncio
async def test_auth_routes_and_protection(sample_data):
    store = DataStore(initial_data=sample_data)
    app = create_app(store=store, enable_auth=True, enable_logging=False)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Login with existing user
        login_res = await client.post(
            "/auth/login", json={"email": "alice@example.com", "password": "any"}
        )
        assert login_res.status_code == 200
        auth_data = login_res.json()
        assert "access_token" in auth_data
        token = auth_data["access_token"]
        assert auth_data["user"]["email"] == "alice@example.com"

        # 2. Test GET /auth/me with Bearer token
        me_res = await client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert me_res.status_code == 200
        assert me_res.json()["user"]["email"] == "alice@example.com"

        # 3. GET /products works without authentication
        get_res = await client.get("/products")
        assert get_res.status_code == 200

        # 4. POST /products WITHOUT token should be 401 Unauthorized
        post_unauth = await client.post(
            "/products", json={"title": "Secured Gadget", "price": 49.99}
        )
        assert post_unauth.status_code == 401
        assert "Unauthorized" in post_unauth.json()["detail"]

        # 5. POST /products WITH valid Bearer token should succeed (201 Created)
        post_auth = await client.post(
            "/products",
            json={"title": "Secured Gadget", "price": 49.99},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert post_auth.status_code == 201
        assert post_auth.json()["title"] == "Secured Gadget"

        # 6. POST /products with INVALID token fails with 401
        post_invalid = await client.post(
            "/products",
            json={"title": "Invalid Token Test"},
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert post_invalid.status_code == 401

        # 7. Register new user
        reg_res = await client.post(
            "/auth/register",
            json={"name": "Charlie", "email": "charlie@example.com", "role": "admin"},
        )
        assert reg_res.status_code == 201
        assert "access_token" in reg_res.json()
