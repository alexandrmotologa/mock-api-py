"""Dynamically registers RESTful CRUD endpoints and nested routes for collections and singletons."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from mock_api_py.query_engine import execute_query
from mock_api_py.store import DataStore, ReadOnlyError


def _find_foreign_key_relations(store: DataStore) -> List[Dict[str, str]]:
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

        for key in sample.keys():
            if key.endswith("Id") and len(key) > 2:
                prefix = key[:-2].lower()  # e.g. "user" from "userId"
                # Check potential parent collection names
                candidates = [prefix + "s", prefix + "es", prefix]
                for parent in collections:
                    if parent.lower() in candidates and parent != child:
                        relations.append({
                            "parent": parent,
                            "child": child,
                            "fk": key,
                        })
                        break

    return relations


def create_mock_router(store: DataStore) -> APIRouter:
    """Generates an APIRouter containing all dynamic routes from the store data."""
    router = APIRouter()

    # 1. Register Collection Routes
    for col_name in store.get_collections().keys():
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

                return result.items

            return get_all

        # Closure generator for GET /{collection}/{id}
        def make_get_by_id(collection: str):
            async def get_by_id(id: str):
                item = store.get_by_id(collection, id)
                if item is None:
                    raise HTTPException(status_code=404, detail=f"Item with id '{id}' not found in '{collection}'")
                return item

            return get_by_id

        # Closure generator for POST /{collection}
        def make_create(collection: str):
            async def create_item(request: Request):
                try:
                    payload = await request.json()
                    if not isinstance(payload, dict):
                        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
                    new_item = store.create(collection, payload)
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
                        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
                    updated = store.update(collection, id, payload, partial=False)
                    if updated is None:
                        raise HTTPException(status_code=404, detail=f"Item with id '{id}' not found in '{collection}'")
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
                        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
                    updated = store.update(collection, id, payload, partial=True)
                    if updated is None:
                        raise HTTPException(status_code=404, detail=f"Item with id '{id}' not found in '{collection}'")
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
                        raise HTTPException(status_code=404, detail=f"Item with id '{id}' not found in '{collection}'")
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
    for single_name in store.get_singletons():
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
                        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
                    return store.update_singleton(key, payload, partial=True)
                except ReadOnlyError:
                    raise HTTPException(status_code=403, detail="Server is in read-only mode")

            return patch_singleton

        def make_put_singleton(key: str):
            async def put_singleton(request: Request):
                try:
                    payload = await request.json()
                    if not isinstance(payload, dict):
                        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
                    return store.update_singleton(key, payload, partial=False)
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
                    raise HTTPException(status_code=404, detail=f"Parent item with id '{id}' not found in '{parent_col}'")

                # Filter child items by foreign key matching parent id
                all_child_items = store.get_all(child_col)
                target_fk_str = str(id)

                matched = [
                    item for item in all_child_items
                    if isinstance(item, dict) and str(item.get(foreign_key)) == target_fk_str
                ]

                # Apply standard query engine on filtered set
                query_params = dict(request.query_params)
                result = execute_query(matched, query_params, str(request.url))

                response.headers["X-Total-Count"] = str(result.total_count)
                response.headers["Access-Control-Expose-Headers"] = "X-Total-Count, Link"
                if result.link_header:
                    response.headers["Link"] = result.link_header

                return result.items

            return get_nested

        router.add_api_route(
            f"/{parent}/{{id}}/{child}",
            make_get_nested(parent, child, fk),
            methods=["GET"],
            tags=[tag],
            summary=f"Get {child} belonging to {parent} by ID",
        )

    return router
