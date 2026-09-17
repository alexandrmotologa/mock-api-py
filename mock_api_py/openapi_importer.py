"""OpenAPI (3.0 / 3.1) and Swagger 2.0 specification importer for mock-api-py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from mock_api_py.generator import generate_from_schema
from mock_api_py.schema_parser import (
    FieldSpec,
    ModelSpec,
    SchemaSpec,
    _convert_json_schema_property,
    to_collection_name,
)


def _resolve_ref(spec: dict[str, Any], ref: str) -> dict[str, Any]:
    """Resolves a local JSON pointer $ref within the spec."""
    if not ref.startswith("#/"):
        return {}

    parts = ref.lstrip("#/").split("/")
    curr: Any = spec
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            return {}

    return curr if isinstance(curr, dict) else {}


def parse_openapi_spec(file_path: str | Path) -> SchemaSpec:
    """
    Parses an OpenAPI 3.x or Swagger 2.0 spec (JSON or YAML) into a SchemaSpec.
    Discovers models from:
      1. `components.schemas` (OpenAPI 3.x)
      2. `definitions` (Swagger 2.0)
      3. `paths` response schemas with $refs
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"OpenAPI spec file '{file_path}' does not exist.")

    with open(path, encoding="utf-8") as f:
        raw_text = f.read()

    if path.suffix.lower() in {".yaml", ".yml"}:
        spec = yaml.safe_load(raw_text)
    else:
        spec = json.loads(raw_text)

    if not isinstance(spec, dict):
        raise ValueError("Invalid OpenAPI spec: root must be an object.")

    discovered_schemas: dict[str, dict[str, Any]] = {}

    # 1. Inspect components.schemas (OpenAPI 3.0 / 3.1)
    components = spec.get("components", {})
    if isinstance(components, dict):
        schemas = components.get("schemas", {})
        if isinstance(schemas, dict):
            for name, schema_def in schemas.items():
                if isinstance(schema_def, dict):
                    discovered_schemas[name] = schema_def

    # 2. Inspect definitions (Swagger 2.0)
    definitions = spec.get("definitions", {})
    if isinstance(definitions, dict):
        for name, schema_def in definitions.items():
            if isinstance(schema_def, dict) and name not in discovered_schemas:
                discovered_schemas[name] = schema_def

    # 3. Inspect paths for inline schemas or $refs
    paths = spec.get("paths", {})
    if isinstance(paths, dict):
        for path_key, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if method.lower() not in {"get", "post", "put", "patch", "delete"} or not isinstance(
                    operation, dict
                ):
                    continue
                responses = operation.get("responses", {})
                if not isinstance(responses, dict):
                    continue
                # Inspect 200 or 201 responses
                for status_code in ("200", "201", 200, 201):
                    res_obj = responses.get(status_code)
                    if not isinstance(res_obj, dict):
                        continue

                    schema_obj: dict[str, Any] | None = None
                    # OpenAPI 3
                    if "content" in res_obj and isinstance(res_obj["content"], dict):
                        json_media = res_obj["content"].get("application/json", {})
                        if isinstance(json_media, dict):
                            schema_obj = json_media.get("schema")
                    # Swagger 2
                    elif "schema" in res_obj and isinstance(res_obj["schema"], dict):
                        schema_obj = res_obj["schema"]

                    if schema_obj and isinstance(schema_obj, dict):
                        if "$ref" in schema_obj:
                            resolved = _resolve_ref(spec, schema_obj["$ref"])
                            ref_name = schema_obj["$ref"].split("/")[-1]
                            if ref_name and ref_name not in discovered_schemas and resolved:
                                discovered_schemas[ref_name] = resolved
                        elif schema_obj.get("type") == "array" and "items" in schema_obj:
                            items_schema = schema_obj["items"]
                            if isinstance(items_schema, dict) and "$ref" in items_schema:
                                resolved = _resolve_ref(spec, items_schema["$ref"])
                                ref_name = items_schema["$ref"].split("/")[-1]
                                if ref_name and ref_name not in discovered_schemas and resolved:
                                    discovered_schemas[ref_name] = resolved
                        elif "properties" in schema_obj:
                            model_name = schema_obj.get("title") or path_key.strip("/").split("/")[
                                -1
                            ].capitalize()
                            if model_name not in discovered_schemas:
                                discovered_schemas[model_name] = schema_obj

    # Build ModelSpecs from discovered schemas
    models: list[ModelSpec] = []
    for model_name, schema_obj in discovered_schemas.items():
        # Handle allOf or direct properties
        properties: dict[str, Any] = {}
        if "properties" in schema_obj and isinstance(schema_obj["properties"], dict):
            properties = schema_obj["properties"]
        elif "allOf" in schema_obj and isinstance(schema_obj["allOf"], list):
            for sub_schema in schema_obj["allOf"]:
                if isinstance(sub_schema, dict):
                    if "$ref" in sub_schema:
                        sub_schema = _resolve_ref(spec, sub_schema["$ref"])
                    if "properties" in sub_schema and isinstance(sub_schema["properties"], dict):
                        properties.update(sub_schema["properties"])

        if not properties:
            continue

        fields: list[FieldSpec] = []
        for prop_name, prop_def in properties.items():
            if isinstance(prop_def, dict):
                # Resolve property level $ref if any
                if "$ref" in prop_def:
                    resolved_prop = _resolve_ref(spec, prop_def["$ref"])
                    if resolved_prop:
                        prop_def = resolved_prop
                fields.append(_convert_json_schema_property(prop_name, prop_def))

        if fields:
            models.append(
                ModelSpec(
                    name=model_name,
                    collection_name=to_collection_name(model_name),
                    fields=fields,
                )
            )

    return SchemaSpec(models=models)


def import_openapi_to_db(
    spec_path: str | Path,
    output_path: str | Path | None = None,
    count: int = 10,
) -> dict[str, list[dict[str, Any]]]:
    """
    Imports an OpenAPI / Swagger spec file, parses its data schemas,
    generates synthetic mock data, and optionally writes it to output_path.
    """
    spec = parse_openapi_spec(spec_path)
    return generate_from_schema(spec, count=count, output_path=str(output_path) if output_path else None)


# Alias for convenience
import_openapi_spec = import_openapi_to_db

