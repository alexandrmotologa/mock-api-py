import socket
import pytest
from httpx import ASGITransport, AsyncClient
from mock_api_py.cli import find_available_port
from mock_api_py.server import create_app
from mock_api_py.store import DataStore


@pytest.mark.anyio
async def test_reset_http_endpoint():
    initial = {"users": [{"id": 1, "name": "Admin"}]}
    store = DataStore(initial_data=initial)
    app = create_app(store)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a user
        create_res = await ac.post("/users", json={"name": "Guest"})
        assert create_res.status_code == 201

        # Check count is 2
        get_res = await ac.get("/users")
        assert len(get_res.json()) == 2

        # Trigger reset
        reset_res = await ac.post("/_reset")
        assert reset_res.status_code == 200
        assert reset_res.json()["message"] == "Database reset to initial boot snapshot successfully"

        # Verify reverted to 1
        after_reset = await ac.get("/users")
        users = after_reset.json()
        assert len(users) == 1
        assert users[0]["name"] == "Admin"


def test_find_available_port():
    # Bind a temporary socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        occupied_port = s.getsockname()[1]

        # Asking for occupied_port should yield next available port
        found_port = find_available_port("127.0.0.1", occupied_port)
        assert found_port != occupied_port
        assert found_port > occupied_port
