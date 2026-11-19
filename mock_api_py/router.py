"""Dynamically registers RESTful CRUD endpoints and nested routes for collections and singletons."""

from __future__ import annotations

import copy
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from mock_api_py.events import EventBroadcaster
from mock_api_py.query_engine import execute_query
from mock_api_py.store import DataStore, ReadOnlyError


def _singularize(word: str) -> str:
    """Converts a plural collection name to its singular form."""
    lower = word.lower()
    if lower.endswith("ies") and len(lower) > 3:
        return word[:-3] + "y"
    elif (
        lower.endswith("ses")
        or lower.endswith("xes")
        or lower.endswith("ches")
        or lower.endswith("shes")
    ):
        return word[:-2]
    elif lower.endswith("s") and not lower.endswith("ss") and len(lower) > 3:
        return word[:-1]
    return word


def _pluralize(word: str) -> str:
    """Converts a singular word to a plural collection name."""
    lower = word.lower()
    if lower.endswith("y") and len(lower) > 2 and lower[-2] not in "aeiou":
        return word[:-1] + "ies"
    elif lower.endswith("s") or lower.endswith("x") or lower.endswith("ch") or lower.endswith("sh"):
        return word + "es"
    elif not lower.endswith("s"):
        return word + "s"
    return word


def resolve_relations_for_item(
    item: dict[str, Any],
    current_collection: str,
    store: DataStore,
    embed: str | None = None,
    expand: str | None = None,
) -> dict[str, Any]:
    """Resolves _embed and _expand foreign key relationships for a single item."""
    if not isinstance(item, dict):
        return item

    result = copy.deepcopy(item)
    known_cols = store.get_known_collections()

    # 1. Embed child collections (e.g. GET /posts?_embed=comments)
    if embed:
        embed_targets = [e.strip() for e in embed.split(",") if e.strip()]
        for target in embed_targets:
            target_col = None
            for col in known_cols:
                if col.lower() == target.lower():
                    target_col = col
                    break
            if not target_col:
                plural = _pluralize(target)
                for col in known_cols:
                    if col.lower() == plural.lower():
                        target_col = col
                        break

            if not target_col:
                result[target] = []
                continue

            parent_singular = _singularize(current_collection)
            candidate_fks = [
                f"{parent_singular}Id",
                f"{parent_singular}_id",
                parent_singular,
                f"{current_collection}Id",
                f"{current_collection}_id",
            ]

            parent_id_str = str(result.get("id"))
            child_items = store.get_all(target_col)
            matching_children = []

            for child in child_items:
                if not isinstance(child, dict):
                    continue
                for fk in candidate_fks:
                    if fk in child and str(child[fk]) == parent_id_str:
                        matching_children.append(copy.deepcopy(child))
                        break

            result[target] = matching_children

    # 2. Expand parent collections (e.g. GET /comments?_expand=post)
    if expand:
        expand_targets = [e.strip() for e in expand.split(",") if e.strip()]
        for target in expand_targets:
            target_col = None
            for col in known_cols:
                if col.lower() == target.lower():
                    target_col = col
                    break
            if not target_col:
                plural = _pluralize(target)
                for col in known_cols:
                    if col.lower() == plural.lower():
                        target_col = col
                        break

            if not target_col:
                result[target] = None
                continue

            target_singular = _singularize(target)
            candidate_fks = [
                f"{target_singular}Id",
                f"{target_singular}_id",
                target_singular,
                f"{target_col}Id",
                f"{target_col}_id",
                f"{_singularize(target_col)}Id",
                f"{_singularize(target_col)}_id",
            ]

            parent_obj = None
            for fk in candidate_fks:
                if fk in result and result[fk] is not None:
                    parent_id_str = str(result[fk])
                    parent_candidate = store.get_by_id(target_col, parent_id_str)
                    if parent_candidate is not None:
                        parent_obj = copy.deepcopy(parent_candidate)
                        break

            result[target] = parent_obj

    return result


def resolve_relations(
    items: list[dict[str, Any]],
    current_collection: str,
    store: DataStore,
    embed: str | None = None,
    expand: str | None = None,
) -> list[dict[str, Any]]:
    """Resolves _embed and _expand foreign key relationships for a list of items."""
    if not embed and not expand:
        return items
    return [
        resolve_relations_for_item(
            item=item,
            current_collection=current_collection,
            store=store,
            embed=embed,
            expand=expand,
        )
        for item in items
    ]


def _find_foreign_key_relations(store: DataStore) -> list[dict[str, str]]:
    """
    Detects relational foreign keys between collections.
    For example:
      If 'users' collection exists and 'products' contains 'userId',
      maps parent='users', child='products', fk='userId'.
    """
    relations = []
    collections = list(store.get_collections().keys())

    for child in collections:
        items = store.get_all(child)
        if not items:
            continue

        sample = items[0]
        if not isinstance(sample, dict):
            continue

        for key in sample:
            if key.endswith("Id") and len(key) > 2:
                prefix = key[:-2].lower()  # e.g. "user" from "userId"
                # Check potential parent collection names
                candidates = [prefix + "s", prefix + "es", prefix]
                for parent in collections:
                    if parent.lower() in candidates and parent != child:
                        relations.append(
                            {
                                "parent": parent,
                                "child": child,
                                "fk": key,
                            }
                        )
                        break

    return relations


def create_mock_router(store: DataStore, broadcaster: EventBroadcaster | None = None) -> APIRouter:
    """Generates an APIRouter containing all dynamic routes from the store data."""
    router = APIRouter()

    # 1. Register Collection Routes
    for col_name in store.get_known_collections():
        tag = col_name.capitalize()

        # Closure generator for GET /{collection}
        def make_get_all(collection: str):
            async def get_all(request: Request, response: Response):
                items = store.get_all(collection)
                query_params = dict(request.query_params)
                result = execute_query(items, query_params, str(request.url))

                response.headers["X-Total-Count"] = str(result.total_count)
                response.headers["Access-Control-Expose-Headers"] = "X-Total-Count, Link"
                if result.link_header:
                    response.headers["Link"] = result.link_header

                processed_items = resolve_relations(
                    items=result.items,
                    current_collection=collection,
                    store=store,
                    embed=query_params.get("_embed"),
                    expand=query_params.get("_expand"),
                )

                return processed_items

            return get_all

        # Closure generator for GET /{collection}/{id}
        def make_get_by_id(collection: str):
            async def get_by_id(id: str, request: Request):
                item = store.get_by_id(collection, id)
                if item is None:
                    raise HTTPException(
                        status_code=404, detail=f"Item with id '{id}' not found in '{collection}'"
                    )
                query_params = dict(request.query_params)
                if "_embed" in query_params or "_expand" in query_params:
                    item = resolve_relations_for_item(
                        item=item,
                        current_collection=collection,
                        store=store,
                        embed=query_params.get("_embed"),
                        expand=query_params.get("_expand"),
                    )
                return item

            return get_by_id

        # Closure generator for POST /{collection}
        def make_create(collection: str):
            async def create_item(request: Request):
                try:
                    payload = await request.json()
                    if not isinstance(payload, dict):
                        raise HTTPException(
                            status_code=400, detail="Request body must be a JSON object"
                        )
                    new_item = store.create(collection, payload)
                    if broadcaster is not None:
                        await broadcaster.publish(
                            event="create",
                            data={"action": "create", "collection": collection, "item": new_item},
                            collection=collection,
                        )
                    return JSONResponse(status_code=201, content=new_item)
                except ReadOnlyError:
                    raise HTTPException(status_code=403, detail="Server is in read-only mode")
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=str(e))

            return create_item

        # Closure generator for PUT /{collection}/{id}
        def make_put(collection: str):
            async def update_item(id: str, request: Request):
                try:
                    payload = await request.json()
                    if not isinstance(payload, dict):
                        raise HTTPException(
                            status_code=400, detail="Request body must be a JSON object"
                        )
                    updated = store.update(collection, id, payload, partial=False)
                    if updated is None:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Item with id '{id}' not found in '{collection}'",
                        )
                    if broadcaster is not None:
                        await broadcaster.publish(
                            event="update",
                            data={"action": "update", "collection": collection, "item": updated},
                            collection=collection,
                        )
                    return updated
                except ReadOnlyError:
                    raise HTTPException(status_code=403, detail="Server is in read-only mode")

            return update_item

        # Closure generator for PATCH /{collection}/{id}
        def make_patch(collection: str):
            async def patch_item(id: str, request: Request):
                try:
                    payload = await request.json()
                    if not isinstance(payload, dict):
                        raise HTTPException(
                            status_code=400, detail="Request body must be a JSON object"
                        )
                    updated = store.update(collection, id, payload, partial=True)
                    if updated is None:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Item with id '{id}' not found in '{collection}'",
                        )
                    if broadcaster is not None:
                        await broadcaster.publish(
                            event="patch",
                            data={"action": "patch", "collection": collection, "item": updated},
                            collection=collection,
                        )
                    return updated
                except ReadOnlyError:
                    raise HTTPException(status_code=403, detail="Server is in read-only mode")

            return patch_item

        # Closure generator for DELETE /{collection}/{id}
        def make_delete(collection: str):
            async def delete_item(id: str):
                try:
                    deleted = store.delete(collection, id)
                    if deleted is None:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Item with id '{id}' not found in '{collection}'",
                        )
                    if broadcaster is not None:
                        await broadcaster.publish(
                            event="delete",
                            data={"action": "delete", "collection": collection, "item": deleted},
                            collection=collection,
                        )
                    return deleted
                except ReadOnlyError:
                    raise HTTPException(status_code=403, detail="Server is in read-only mode")

            return delete_item

        router.add_api_route(
            f"/{col_name}",
            make_get_all(col_name),
            methods=["GET"],
            tags=[tag],
            summary=f"List and filter {col_name}",
        )
        router.add_api_route(
            f"/{col_name}/{{id}}",
            make_get_by_id(col_name),
            methods=["GET"],
            tags=[tag],
            summary=f"Get {col_name} item by ID",
        )
        router.add_api_route(
            f"/{col_name}",
            make_create(col_name),
            methods=["POST"],
            tags=[tag],
            status_code=201,
            summary=f"Create new {col_name} item",
        )
        router.add_api_route(
            f"/{col_name}/{{id}}",
            make_put(col_name),
            methods=["PUT"],
            tags=[tag],
            summary=f"Replace {col_name} item by ID",
        )
        router.add_api_route(
            f"/{col_name}/{{id}}",
            make_patch(col_name),
            methods=["PATCH"],
            tags=[tag],
            summary=f"Partially update {col_name} item by ID",
        )
        router.add_api_route(
            f"/{col_name}/{{id}}",
            make_delete(col_name),
            methods=["DELETE"],
            tags=[tag],
            summary=f"Delete {col_name} item by ID",
        )

    # 2. Register Singleton Routes
    for single_name in store.get_known_singletons():
        tag = single_name.capitalize()

        def make_get_singleton(key: str):
            async def get_singleton():
                val = store.get_singleton(key)
                if val is None:
                    raise HTTPException(status_code=404, detail=f"Resource '{key}' not found")
                return val

            return get_singleton

        def make_patch_singleton(key: str):
            async def patch_singleton(request: Request):
                try:
                    payload = await request.json()
                    if not isinstance(payload, dict):
                        raise HTTPException(
                            status_code=400, detail="Request body must be a JSON object"
                        )
                    val = store.update_singleton(key, payload, partial=True)
                    if broadcaster is not None:
                        await broadcaster.publish(
                            event="singleton_patch",
                            data={"action": "patch", "singleton": key, "item": val},
                            collection=key,
                        )
                    return val
                except ReadOnlyError:
                    raise HTTPException(status_code=403, detail="Server is in read-only mode")

            return patch_singleton

        def make_put_singleton(key: str):
            async def put_singleton(request: Request):
                try:
                    payload = await request.json()
                    if not isinstance(payload, dict):
                        raise HTTPException(
                            status_code=400, detail="Request body must be a JSON object"
                        )
                    val = store.update_singleton(key, payload, partial=False)
                    if broadcaster is not None:
                        await broadcaster.publish(
                            event="singleton_update",
                            data={"action": "update", "singleton": key, "item": val},
                            collection=key,
                        )
                    return val
                except ReadOnlyError:
                    raise HTTPException(status_code=403, detail="Server is in read-only mode")

            return put_singleton

        router.add_api_route(
            f"/{single_name}",
            make_get_singleton(single_name),
            methods=["GET"],
            tags=[tag],
            summary=f"Get {single_name} singleton",
        )
        router.add_api_route(
            f"/{single_name}",
            make_patch_singleton(single_name),
            methods=["PATCH"],
            tags=[tag],
            summary=f"Partially update {single_name} singleton",
        )
        router.add_api_route(
            f"/{single_name}",
            make_put_singleton(single_name),
            methods=["PUT"],
            tags=[tag],
            summary=f"Replace {single_name} singleton",
        )

    # 3. Register Nested Relational Routes (e.g. GET /users/{id}/products)
    relations = _find_foreign_key_relations(store)
    for rel in relations:
        parent = rel["parent"]
        child = rel["child"]
        fk = rel["fk"]
        tag = f"{parent.capitalize()} -> {child.capitalize()}"

        def make_get_nested(parent_col: str, child_col: str, foreign_key: str):
            async def get_nested(id: str, request: Request, response: Response):
                parent_item = store.get_by_id(parent_col, id)
                if parent_item is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Parent item with id '{id}' not found in '{parent_col}'",
                    )

                # Filter child items by foreign key matching parent id
                all_child_items = store.get_all(child_col)
                target_fk_str = str(id)

                matched = [
                    item
                    for item in all_child_items
                    if isinstance(item, dict) and str(item.get(foreign_key)) == target_fk_str
                ]

                # Apply standard query engine on filtered set
                query_params = dict(request.query_params)
                result = execute_query(matched, query_params, str(request.url))

                response.headers["X-Total-Count"] = str(result.total_count)
                response.headers["Access-Control-Expose-Headers"] = "X-Total-Count, Link"
                if result.link_header:
                    response.headers["Link"] = result.link_header

                processed_items = resolve_relations(
                    items=result.items,
                    current_collection=child_col,
                    store=store,
                    embed=query_params.get("_embed"),
                    expand=query_params.get("_expand"),
                )

                return processed_items

            return get_nested

        router.add_api_route(
            f"/{parent}/{{id}}/{child}",
            make_get_nested(parent, child, fk),
            methods=["GET"],
            tags=[tag],
            summary=f"Get {child} belonging to {parent} by ID",
        )

    return router
