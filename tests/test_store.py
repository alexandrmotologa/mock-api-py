"""Unit tests for DataStore CRUD, ID generation, atomic persistence, and read-only mode."""

import json
from pathlib import Path
import pytest
from mock_api_py.store import DataStore, ReadOnlyError


def test_get_all_and_by_id(sample_data):
    store = DataStore(initial_data=sample_data)
    products = store.get_all("products")
    assert len(products) == 3

    item = store.get_by_id("products", 1)
    assert item is not None
    assert item["title"] == "Wireless Mouse"

    # Non-existent
    assert store.get_by_id("products", 999) is None
    assert store.get_all("unknown") == []


def test_create_auto_increment_id(sample_data):
    store = DataStore(initial_data=sample_data)
    new_product = store.create("products", {"title": "Webcam", "price": 49.99})
    assert new_product["id"] == 4
    assert store.get_by_id("products", 4) is not None


def test_create_explicit_id(sample_data):
    store = DataStore(initial_data=sample_data)
    new_product = store.create("products", {"id": 10, "title": "Monitor", "price": 249.99})
    assert new_product["id"] == 10

    # Duplicate ID raises ValueError
    with pytest.raises(ValueError):
        store.create("products", {"id": 10, "title": "Duplicate"})


def test_update_put_and_patch(sample_data):
    store = DataStore(initial_data=sample_data)

    # PUT (full replacement, preserving ID)
    put_result = store.update("products", 1, {"title": "Updated Mouse"}, partial=False)
    assert put_result["id"] == 1
    assert put_result["title"] == "Updated Mouse"
    assert "price" not in put_result

    # PATCH (partial update)
    patch_result = store.update("products", 2, {"inStock": True}, partial=True)
    assert patch_result["id"] == 2
    assert patch_result["title"] == "Mechanical Keyboard"
    assert patch_result["inStock"] is True


def test_delete(sample_data):
    store = DataStore(initial_data=sample_data)
    deleted = store.delete("products", 2)
    assert deleted is not None
    assert deleted["id"] == 2
    assert len(store.get_all("products")) == 2
    assert store.get_by_id("products", 2) is None

    # Deleting non-existent returns None
    assert store.delete("products", 999) is None


def test_singleton_operations(sample_data):
    store = DataStore(initial_data=sample_data)
    profile = store.get_singleton("profile")
    assert profile["name"] == "Alexandr"

    updated = store.update_singleton("profile", {"status": "shipping"}, partial=True)
    assert updated["name"] == "Alexandr"
    assert updated["status"] == "shipping"


def test_read_only_mode(sample_data):
    store = DataStore(initial_data=sample_data, read_only=True)
    with pytest.raises(ReadOnlyError):
        store.create("products", {"title": "Fail"})

    with pytest.raises(ReadOnlyError):
        store.update("products", 1, {"title": "Fail"})

    with pytest.raises(ReadOnlyError):
        store.delete("products", 1)

    with pytest.raises(ReadOnlyError):
        store.update_singleton("profile", {"status": "Fail"})


def test_atomic_persistence(tmp_path):
    db_file = tmp_path / "test_db.json"
    initial = {"items": [{"id": 1, "name": "Initial"}]}
    with open(db_file, "w", encoding="utf-8") as f:
        json.dump(initial, f)

    store = DataStore(file_path=db_file, auto_save=True)
    assert len(store.get_all("items")) == 1

    store.create("items", {"name": "Second"})

    # Verify written to disk
    with open(db_file, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert len(saved["items"]) == 2
    assert saved["items"][1]["name"] == "Second"


def test_check_and_reload(tmp_path):
    import time
    db_file = tmp_path / "reload_db.json"
    with open(db_file, "w", encoding="utf-8") as f:
        json.dump({"items": [{"id": 1, "name": "V1"}]}, f)

    store = DataStore(file_path=db_file)
    assert store.get_all("items")[0]["name"] == "V1"

    # Modify file externally
    time.sleep(0.05)
    with open(db_file, "w", encoding="utf-8") as f:
        json.dump({"items": [{"id": 1, "name": "V2"}]}, f)

    reloaded = store.check_and_reload()
    assert reloaded is True
    assert store.get_all("items")[0]["name"] == "V2"


def test_store_reset():
    initial = {
        "posts": [{"id": 1, "title": "Original"}],
        "profile": {"name": "Admin"},
    }
    store = DataStore(initial_data=initial)

    # Mutate data
    store.create("posts", {"title": "New Post"})
    store.update("posts", 1, {"title": "Changed"}, partial=True)
    store.update_singleton("profile", {"name": "Hacked"})

    assert len(store.get_all("posts")) == 2
    assert store.get_by_id("posts", 1)["title"] == "Changed"
    assert store.get_singleton("profile")["name"] == "Hacked"

    # Reset
    store.reset()

    assert len(store.get_all("posts")) == 1
    assert store.get_by_id("posts", 1)["title"] == "Original"
    assert store.get_singleton("profile")["name"] == "Admin"

