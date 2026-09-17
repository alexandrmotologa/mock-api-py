"""Integration and unit tests for test fixture scenario state management."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from mock_api_py.server import create_app
from mock_api_py.store import DataStore


@pytest.fixture
def fixtures_directory(tmp_path: Path) -> Path:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()

    # 1. Empty state fixture
    empty_fixture = fixtures_dir / "empty_state.json"
    with open(empty_fixture, "w", encoding="utf-8") as f:
        json.dump({"orders": [], "users": []}, f)

    # 2. Blocked user state fixture (YAML)
    blocked_user_yaml = fixtures_dir / "blocked_user.yaml"
    with open(blocked_user_yaml, "w", encoding="utf-8") as f:
        f.write(
            """
users:
  - id: 1
    name: "Blocked User"
    status: "suspended"
orders:
  - id: 101
    userId: 1
    amount: 50.0
"""
        )

    # 3. Normal active state fixture
    active_fixture = fixtures_dir / "active_state.json"
    with open(active_fixture, "w", encoding="utf-8") as f:
        json.dump(
            {
                "users": [
                    {"id": 1, "name": "Alice", "status": "active"},
                    {"id": 2, "name": "Bob", "status": "active"},
                ],
                "orders": [{"id": 1, "userId": 1, "amount": 100.0}],
            },
            f,
        )

    return fixtures_dir


def test_datastore_scenario_loading_and_switching(fixtures_directory: Path):
    store = DataStore(
        fixtures_dir=fixtures_directory,
        initial_data={"users": [{"id": 99, "name": "Initial"}]},
    )

    scenarios = store.get_available_scenarios()
    assert "active_state" in scenarios
    assert "blocked_user" in scenarios
    assert "empty_state" in scenarios

    # Load empty state
    store.load_scenario("empty_state")
    assert store.active_scenario == "empty_state"
    assert store.get_all("users") == []
    assert store.get_all("orders") == []

    # Load blocked user
    store.load_scenario("blocked_user")
    assert store.active_scenario == "blocked_user"
    users = store.get_all("users")
    assert len(users) == 1
    assert users[0]["status"] == "suspended"

    # Reset resets to the scenario snapshot
    store.create("users", {"name": "New User"})
    assert len(store.get_all("users")) == 2
    store.reset()
    assert len(store.get_all("users")) == 1


@pytest.mark.asyncio
async def test_scenario_http_endpoints(fixtures_directory: Path):
    store = DataStore(fixtures_dir=fixtures_directory, initial_data={})
    app = create_app(store=store, enable_logging=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. List scenarios
        res_list = await client.get("/_scenarios")
        assert res_list.status_code == 200
        data = res_list.json()
        assert "empty_state" in data["available"]
        assert "blocked_user" in data["available"]

        # 2. Switch scenario to active_state
        res_switch = await client.post("/_scenario/active_state")
        assert res_switch.status_code == 200
        assert res_switch.json()["active"] == "active_state"

        # Verify collection contents
        res_users = await client.get("/users")
        assert res_users.status_code == 200
        assert len(res_users.json()) == 2

        # 3. Switch to empty_state
        res_empty = await client.post("/_scenario/empty_state")
        assert res_empty.status_code == 200
        res_empty_users = await client.get("/users")
        assert res_empty_users.json() == []

        # 4. 404 on nonexistent scenario
        res_404 = await client.post("/_scenario/nonexistent_one")
        assert res_404.status_code == 404
