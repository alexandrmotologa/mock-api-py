"""Unit tests for OpenAPI 3.x and Swagger 2.0 specification import."""

from __future__ import annotations

import json
from pathlib import Path

from mock_api_py.openapi_importer import import_openapi_to_db, parse_openapi_spec


def test_parse_openapi_3_json(tmp_path: Path):
    spec_data = {
        "openapi": "3.0.0",
        "info": {"title": "E-Commerce API", "version": "1.0.0"},
        "paths": {
            "/users": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "List users",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/User"},
                                    }
                                }
                            },
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "username": {"type": "string", "faker": "name"},
                        "email": {"type": "string", "format": "email"},
                    },
                },
                "Order": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "userId": {"type": "integer"},
                        "total": {"type": "number"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "completed", "cancelled"],
                        },
                    },
                },
            }
        },
    }

    spec_file = tmp_path / "openapi.json"
    with open(spec_file, "w", encoding="utf-8") as f:
        json.dump(spec_data, f)

    spec = parse_openapi_spec(spec_file)
    assert len(spec.models) == 2
    model_names = {m.name for m in spec.models}
    assert "User" in model_names
    assert "Order" in model_names

    out_file = tmp_path / "db.json"
    db = import_openapi_to_db(spec_file, output_path=out_file, count=5)
    assert "users" in db
    assert "orders" in db
    assert len(db["users"]) == 5
    assert len(db["orders"]) == 5

    # Verify foreign key relation
    user_ids = {u["id"] for u in db["users"]}
    for o in db["orders"]:
        assert o["userId"] in user_ids
        assert o["status"] in {"pending", "completed", "cancelled"}

    assert out_file.exists()


def test_parse_swagger_2_yaml(tmp_path: Path):
    swagger_yaml = """
swagger: "2.0"
info:
  title: "Petstore API"
  version: "1.0.0"
paths:
  /pets:
    get:
      responses:
        200:
          description: "A list of pets"
          schema:
            type: "array"
            items:
              $ref: "#/definitions/Pet"
definitions:
  Pet:
    type: "object"
    properties:
      id:
        type: "integer"
      name:
        type: "string"
      tag:
        type: "string"
"""
    spec_file = tmp_path / "swagger.yaml"
    with open(spec_file, "w", encoding="utf-8") as f:
        f.write(swagger_yaml)

    db = import_openapi_to_db(spec_file, count=4)
    assert "pets" in db
    assert len(db["pets"]) == 4
    for pet in db["pets"]:
        assert pet["id"] in {1, 2, 3, 4}
        assert isinstance(pet["name"], str)
