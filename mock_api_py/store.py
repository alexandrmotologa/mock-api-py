"""In-memory data store with atomic JSON persistence and CRUD operations."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

import yaml


class ReadOnlyError(Exception):
    """Raised when an operation attempts to mutate a read-only store."""


class DataStore:
    """Manages the in-memory dataset, ID generation, and atomic persistence."""

    def __init__(
        self,
        file_path: str | Path | None = None,
        initial_data: dict[str, Any] | None = None,
        auto_save: bool = False,
        read_only: bool = False,
        fixtures_dir: str | Path | None = None,
        initial_scenario: str | None = None,
    ) -> None:
        self.file_path = Path(file_path) if file_path else None
        self.auto_save = auto_save
        self.read_only = read_only
        self.data: dict[str, Any] = {}
        self.last_modified: float | None = None

        self.fixtures_dir = Path(fixtures_dir) if fixtures_dir else None
        self.scenarios: dict[str, dict[str, Any]] = {}
        self.active_scenario: str | None = None

        if self.fixtures_dir and self.fixtures_dir.exists():
            self.load_fixtures_from_directory(self.fixtures_dir)

        if initial_scenario and initial_scenario in self.scenarios:
            self.load_scenario(initial_scenario)
        elif initial_data is not None:
            self.data = copy.deepcopy(initial_data)
        elif self.file_path and self.file_path.exists():
            self.load()
        else:
            self.data = {}

        # Preserve the initial seed state for instant database resets
        self.initial_snapshot: dict[str, Any] = copy.deepcopy(self.data)

    def load_fixtures_from_directory(self, dir_path: str | Path) -> None:
        """Scans a directory for JSON and YAML fixture files and registers scenarios."""
        p = Path(dir_path)
        if not p.exists() or not p.is_dir():
            return

        for f_path in p.iterdir():
            if f_path.is_file() and f_path.suffix.lower() in {".json", ".yaml", ".yml"}:
                scenario_name = f_path.stem
                try:
                    with open(f_path, encoding="utf-8") as f:
                        if f_path.suffix.lower() in {".yaml", ".yml"}:
                            content = yaml.safe_load(f)
                        else:
                            content = json.load(f)
                    if isinstance(content, dict):
                        self.scenarios[scenario_name] = content
                except Exception:
                    pass

    def get_available_scenarios(self) -> list[str]:
        """Returns the list of all registered scenario names."""
        return sorted(list(self.scenarios.keys()))

    def load_scenario(self, name: str) -> dict[str, Any]:
        """Swaps the active in-memory dataset to a registered scenario fixture."""
        if name not in self.scenarios:
            raise KeyError(
                f"Scenario '{name}' not found. Available scenarios: {self.get_available_scenarios()}"
            )

        self.data = copy.deepcopy(self.scenarios[name])
        self.active_scenario = name
        if self.auto_save and not self.read_only and self.file_path:
            self.save()
        return copy.deepcopy(self.data)

    def reset(self) -> dict[str, Any]:
        """Resets the dataset back to its initial boot snapshot or active scenario snapshot."""
        if self.active_scenario and self.active_scenario in self.scenarios:
            self.data = copy.deepcopy(self.scenarios[self.active_scenario])
        else:
            self.data = copy.deepcopy(self.initial_snapshot)
        if self.auto_save and not self.read_only and self.file_path:
            self.save()
        return copy.deepcopy(self.data)

    def load(self) -> None:
        """Loads data from the JSON file into memory."""
        if not self.file_path or not self.file_path.exists():
            return
        with open(self.file_path, encoding="utf-8") as f:
            self.data = json.load(f)
        self.last_modified = os.path.getmtime(self.file_path)

    def check_and_reload(self) -> bool:
        """Checks if the file was modified externally on disk and reloads if necessary."""
        if not self.file_path or not self.file_path.exists():
            return False
        try:
            current_mtime = os.path.getmtime(self.file_path)
            if self.last_modified is None or current_mtime > self.last_modified:
                self.load()
                return True
        except OSError:
            pass
        return False

    def save(self) -> None:
        """Atomically persists in-memory data to the JSON file using a temp file."""
        if not self.auto_save or self.read_only or not self.file_path:
            return

        target_dir = self.file_path.parent.resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        # Write to a temp file in the same directory to ensure atomic os.replace across platforms
        temp_fd, temp_path = tempfile.mkstemp(
            dir=target_dir,
            prefix=f".{self.file_path.name}.",
            suffix=".tmp",
            text=True,
        )
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.replace(temp_path, self.file_path)
            self.last_modified = os.path.getmtime(self.file_path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    def is_collection(self, key: str) -> bool:
        """Returns True if the resource key represents a list/collection."""
        return isinstance(self.data.get(key), list)

    def is_singleton(self, key: str) -> bool:
        """Returns True if the resource key represents a singleton dictionary."""
        return isinstance(self.data.get(key), dict)

    def get_collections(self) -> dict[str, int]:
        """Returns a mapping of collection names to their current item count."""
        return {
            k: len(v)
            for k, v in self.data.items()
            if isinstance(v, list)
        }

    def get_known_collections(self) -> list[str]:
        """Returns all collection names present in active data or any loaded scenario fixture."""
        cols = set(self.get_collections().keys())
        for fix_data in self.scenarios.values():
            if isinstance(fix_data, dict):
                for k, v in fix_data.items():
                    if isinstance(v, list):
                        cols.add(k)
        return sorted(cols)

    def get_singletons(self) -> list[str]:
        """Returns a list of keys representing singleton objects."""
        return [
            k for k, v in self.data.items()
            if isinstance(v, dict)
        ]

    def get_known_singletons(self) -> list[str]:
        """Returns all singleton keys present in active data or any loaded scenario fixture."""
        sings = set(self.get_singletons())
        for fix_data in self.scenarios.values():
            if isinstance(fix_data, dict):
                for k, v in fix_data.items():
                    if isinstance(v, dict):
                        sings.add(k)
        return sorted(sings)

    def _generate_id(self, collection: str) -> int | str:
        """Generates a new unique identifier based on the collection's existing IDs."""
        items = self.data.get(collection, [])
        if not items:
            return 1

        ids = [item.get("id") for item in items if isinstance(item, dict) and "id" in item]
        if not ids:
            return 1

        # Check if all existing IDs are integers
        if all(isinstance(i, int) for i in ids):
            return max(ids) + 1

        # Check if all existing IDs are integer-like strings
        all_numeric = all(isinstance(i, (int, str)) and str(i).isdigit() for i in ids)
        if all_numeric:
            int_values = [int(i) for i in ids]
            return max(int_values) + 1

        # Otherwise generate a UUID string
        return str(uuid.uuid4())

    def get_all(self, collection: str) -> list[dict[str, Any]]:
        """Returns all items in a collection."""
        if not self.is_collection(collection):
            return []
        return copy.deepcopy(self.data[collection])

    def get_by_id(self, collection: str, id_val: Any) -> dict[str, Any] | None:
        """Finds an item by its ID (coercing to string for comparison)."""
        if not self.is_collection(collection):
            return None
        target_id_str = str(id_val)
        for item in self.data[collection]:
            if isinstance(item, dict) and str(item.get("id")) == target_id_str:
                return copy.deepcopy(item)
        return None

    def create(self, collection: str, item_data: dict[str, Any]) -> dict[str, Any]:
        """Creates and appends a new item to a collection."""
        if self.read_only:
            raise ReadOnlyError("Store is in read-only mode")

        if collection not in self.data or not isinstance(self.data[collection], list):
            self.data[collection] = []

        new_item = copy.deepcopy(item_data)
        if "id" not in new_item or new_item["id"] is None or str(new_item["id"]).strip() == "":
            new_item["id"] = self._generate_id(collection)
        else:
            # Check for duplicate ID
            if self.get_by_id(collection, new_item["id"]) is not None:
                raise ValueError(f"Item with ID '{new_item['id']}' already exists in '{collection}'")

        self.data[collection].append(new_item)
        self.save()
        return copy.deepcopy(new_item)

    def update(
        self,
        collection: str,
        id_val: Any,
        item_data: dict[str, Any],
        partial: bool = False,
    ) -> dict[str, Any] | None:
        """Updates an existing item (PUT or PATCH)."""
        if self.read_only:
            raise ReadOnlyError("Store is in read-only mode")

        if not self.is_collection(collection):
            return None

        target_id_str = str(id_val)
        items = self.data[collection]

        for i, item in enumerate(items):
            if isinstance(item, dict) and str(item.get("id")) == target_id_str:
                original_id = item.get("id")
                if partial:
                    updated = copy.deepcopy(item)
                    for k, v in item_data.items():
                        if k != "id":
                            updated[k] = v
                else:
                    updated = copy.deepcopy(item_data)
                    updated["id"] = original_id

                items[i] = updated
                self.save()
                return copy.deepcopy(updated)

        return None

    def delete(self, collection: str, id_val: Any) -> dict[str, Any] | None:
        """Deletes an item by ID from a collection."""
        if self.read_only:
            raise ReadOnlyError("Store is in read-only mode")

        if not self.is_collection(collection):
            return None

        target_id_str = str(id_val)
        items = self.data[collection]

        for i, item in enumerate(items):
            if isinstance(item, dict) and str(item.get("id")) == target_id_str:
                deleted_item = items.pop(i)
                self.save()
                return copy.deepcopy(deleted_item)

        return None

    def get_singleton(self, key: str) -> dict[str, Any] | None:
        """Retrieves a singleton dictionary resource."""
        val = self.data.get(key)
        if isinstance(val, dict):
            return copy.deepcopy(val)
        return None

    def update_singleton(
        self, key: str, data: dict[str, Any], partial: bool = False
    ) -> dict[str, Any] | None:
        """Updates a singleton resource (PUT or PATCH)."""
        if self.read_only:
            raise ReadOnlyError("Store is in read-only mode")

        current = self.data.get(key)
        if not isinstance(current, dict):
            current = {}

        if partial:
            updated = copy.deepcopy(current)
            updated.update(data)
        else:
            updated = copy.deepcopy(data)

        self.data[key] = updated
        self.save()
        return copy.deepcopy(updated)
