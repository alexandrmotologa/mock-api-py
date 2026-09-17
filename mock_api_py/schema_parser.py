"""Dynamic schema parser for inline CLI model syntax and JSON/YAML Schema specifications."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

IRREGULAR_PLURALS: dict[str, str] = {
    "person": "people",
    "child": "children",
    "man": "men",
    "woman": "women",
    "tooth": "teeth",
    "foot": "feet",
    "mouse": "mice",
    "crisis": "crises",
    "datum": "data",
}


def to_collection_name(name: str) -> str:
    """Converts a model name (e.g. 'Patient', 'Order', 'Category') to a lowercase plural collection name."""
    s = name.strip().lower()
    if not s:
        return "items"

    if s in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[s]

    if s.endswith("s"):
        return s

    if s.endswith("y") and len(s) > 1 and s[-2] not in "aeiou":
        return s[:-1] + "ies"

    if s.endswith(("ch", "sh", "x", "z")):
        return s + "es"

    return s + "s"


def split_respecting_parentheses(s: str, delimiter: str = ",") -> list[str]:
    """Splits a string by delimiter while ignoring delimiters enclosed in parentheses."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0

    for char in s:
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            if depth > 0:
                depth -= 1
            current.append(char)
        elif char == delimiter and depth == 0:
            token = "".join(current).strip()
            if token:
                parts.append(token)
            current = []
        else:
            current.append(char)

    last_token = "".join(current).strip()
    if last_token:
        parts.append(last_token)

    return parts


@dataclass
class FieldSpec:
    """Specification for a single model field."""

    name: str
    type_name: str
    params: Any = field(default_factory=list)


@dataclass
class ModelSpec:
    """Specification for an entity model/collection."""

    name: str
    collection_name: str
    fields: list[FieldSpec]
    count: int | None = None


@dataclass
class SchemaSpec:
    """Composite schema containing one or more models."""

    models: list[ModelSpec]


def parse_field_spec(field_str: str) -> FieldSpec:
    """
    Parses a single field string.
    Examples:
      - 'id' -> FieldSpec(name='id', type_name='id')
      - 'full_name:name' -> FieldSpec(name='full_name', type_name='name')
      - 'blood_type:choice(A+,A-,B+,B-,O+,O-)' -> FieldSpec(name='blood_type', type_name='choice', params=['A+', 'A-', ...])
      - 'age:int(18,65)' -> FieldSpec(name='age', type_name='int', params=(18, 65))
    """
    field_str = field_str.strip()
    if ":" in field_str:
        name, type_def = field_str.split(":", 1)
        name = name.strip()
        type_def = type_def.strip()
    else:
        name = field_str
        type_def = "id" if field_str.lower() == "id" else "string"

    # Extract function-style parameters: choice(...), int(...), float(...)
    if "(" in type_def and type_def.endswith(")"):
        base_type = type_def[: type_def.index("(")].strip().lower()
        args_str = type_def[type_def.index("(") + 1 : -1].strip()

        if base_type == "choice":
            raw_choices = split_respecting_parentheses(args_str, ",")
            clean_choices = [c.strip().strip("'\"") for c in raw_choices if c.strip()]
            return FieldSpec(name=name, type_name="choice", params=clean_choices)

        if base_type in {"int", "integer"}:
            int_parts = [p.strip() for p in args_str.split(",") if p.strip()]
            if len(int_parts) >= 2:
                try:
                    return FieldSpec(
                        name=name,
                        type_name="int",
                        params=(int(int_parts[0]), int(int_parts[1])),
                    )
                except ValueError:
                    pass
            elif len(int_parts) == 1:
                try:
                    return FieldSpec(name=name, type_name="int", params=(1, int(int_parts[0])))
                except ValueError:
                    pass
            return FieldSpec(name=name, type_name="int", params=(1, 1000))

        if base_type == "float":
            float_parts = [p.strip() for p in args_str.split(",") if p.strip()]
            if len(float_parts) >= 2:
                try:
                    return FieldSpec(
                        name=name,
                        type_name="float",
                        params=(float(float_parts[0]), float(float_parts[1])),
                    )
                except ValueError:
                    pass
            return FieldSpec(name=name, type_name="float", params=(0.0, 100.0))

        return FieldSpec(name=name, type_name=base_type, params=args_str)

    return FieldSpec(name=name, type_name=type_def.lower(), params=[])


def parse_inline_model(model_str: str) -> SchemaSpec:
    """
    Parses inline model syntax into a SchemaSpec.
    Format: 'ModelName:field1:type1,field2:type2,...'
    Multiple models can be separated by ';' or '\n'.
    """
    model_definitions = [m.strip() for m in model_str.replace("\n", ";").split(";") if m.strip()]
    models: list[ModelSpec] = []

    for def_str in model_definitions:
        if ":" not in def_str:
            continue
        model_name, fields_str = def_str.split(":", 1)
        model_name = model_name.strip()
        field_tokens = split_respecting_parentheses(fields_str, ",")

        fields: list[FieldSpec] = []
        for token in field_tokens:
            fields.append(parse_field_spec(token))

        models.append(
            ModelSpec(
                name=model_name,
                collection_name=to_collection_name(model_name),
                fields=fields,
            )
        )

    return SchemaSpec(models=models)


def _convert_json_schema_property(prop_name: str, prop_def: dict[str, Any]) -> FieldSpec:
    """Maps a standard JSON Schema property definition to a FieldSpec."""
    if "enum" in prop_def and isinstance(prop_def["enum"], list):
        return FieldSpec(name=prop_name, type_name="choice", params=prop_def["enum"])

    if "faker" in prop_def:
        return FieldSpec(name=prop_name, type_name=str(prop_def["faker"]).lower())

    schema_format = prop_def.get("format", "").lower()
    if schema_format in {"email", "date", "date-time", "uuid", "uri", "hostname", "ipv4"}:
        mapped = "date" if schema_format == "date-time" else schema_format
        return FieldSpec(name=prop_name, type_name=mapped)

    schema_type = prop_def.get("type", "").lower()
    if schema_type == "integer":
        min_val = prop_def.get("minimum", 1)
        max_val = prop_def.get("maximum", 1000)
        return FieldSpec(name=prop_name, type_name="int", params=(int(min_val), int(max_val)))

    if schema_type == "number":
        return FieldSpec(name=prop_name, type_name="price")

    if schema_type == "boolean":
        return FieldSpec(name=prop_name, type_name="boolean")

    # Name-based heuristic mapping for strings
    lower_name = prop_name.lower()
    if lower_name == "id":
        return FieldSpec(name=prop_name, type_name="id")
    if "email" in lower_name:
        return FieldSpec(name=prop_name, type_name="email")
    if any(k in lower_name for k in ("name", "full_name", "firstname", "lastname")):
        return FieldSpec(name=prop_name, type_name="name")
    if "phone" in lower_name:
        return FieldSpec(name=prop_name, type_name="phone")
    if any(k in lower_name for k in ("price", "amount", "total", "cost")):
        return FieldSpec(name=prop_name, type_name="price")
    if any(k in lower_name for k in ("date", "created_at", "updated_at", "timestamp")):
        return FieldSpec(name=prop_name, type_name="date")
    if "uuid" in lower_name:
        return FieldSpec(name=prop_name, type_name="uuid")

    return FieldSpec(name=prop_name, type_name="string")


def parse_schema_file(file_path: str | Path) -> SchemaSpec:
    """
    Parses a JSON or YAML schema file into a SchemaSpec.
    Supports:
      1. Simple mapping: { "Patient": { "id": "id", "full_name": "name" } }
      2. Standard JSON Schema with $defs / definitions or root properties.
      3. Models array: { "models": [ { "name": "Patient", "fields": [...] } ] }
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Schema file '{file_path}' does not exist.")

    with open(path, encoding="utf-8") as f:
        content = f.read()

    data: Any
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(content)
    else:
        data = json.loads(content)

    if not isinstance(data, dict):
        raise ValueError(f"Schema root must be a JSON/YAML object, got {type(data).__name__}")

    models: list[ModelSpec] = []

    # 1. Models list array: { "models": [ ... ] }
    if "models" in data and isinstance(data["models"], list):
        for item in data["models"]:
            if isinstance(item, dict) and "name" in item:
                m_name = item["name"]
                fields: list[FieldSpec] = []
                fields_raw = item.get("fields", {})
                if isinstance(fields_raw, dict):
                    for f_name, f_type in fields_raw.items():
                        if isinstance(f_type, dict):
                            fields.append(_convert_json_schema_property(f_name, f_type))
                        else:
                            fields.append(parse_field_spec(f"{f_name}:{f_type}"))
                elif isinstance(fields_raw, list):
                    for f_token in fields_raw:
                        fields.append(parse_field_spec(str(f_token)))
                models.append(
                    ModelSpec(
                        name=m_name,
                        collection_name=to_collection_name(m_name),
                        fields=fields,
                        count=item.get("count"),
                    )
                )
        return SchemaSpec(models=models)

    # 2. JSON Schema with $defs or definitions
    defs = data.get("$defs") or data.get("definitions")
    if defs and isinstance(defs, dict):
        for def_name, def_obj in defs.items():
            if isinstance(def_obj, dict) and "properties" in def_obj:
                fields = [
                    _convert_json_schema_property(p_name, p_def)
                    for p_name, p_def in def_obj["properties"].items()
                    if isinstance(p_def, dict)
                ]
                models.append(
                    ModelSpec(
                        name=def_name,
                        collection_name=to_collection_name(def_name),
                        fields=fields,
                    )
                )
        if models:
            return SchemaSpec(models=models)

    # 3. Root JSON Schema object: { "title": "Patient", "type": "object", "properties": { ... } }
    if "properties" in data and isinstance(data["properties"], dict):
        model_name = data.get("title") or path.stem.capitalize()
        fields = [
            _convert_json_schema_property(p_name, p_def)
            for p_name, p_def in data["properties"].items()
            if isinstance(p_def, dict)
        ]
        models.append(
            ModelSpec(
                name=model_name,
                collection_name=to_collection_name(model_name),
                fields=fields,
            )
        )
        return SchemaSpec(models=models)

    # 4. Dictionary of entity models: { "Patient": { "id": "id", "name": "name" } }
    for m_name, def_val in data.items():
        if isinstance(def_val, dict):
            if "properties" in def_val and isinstance(def_val["properties"], dict):
                fields = [
                    _convert_json_schema_property(p_name, p_def)
                    for p_name, p_def in def_val["properties"].items()
                    if isinstance(p_def, dict)
                ]
            else:
                fields = []
                for f_name, f_val in def_val.items():
                    if isinstance(f_val, dict):
                        fields.append(_convert_json_schema_property(f_name, f_val))
                    else:
                        fields.append(parse_field_spec(f"{f_name}:{f_val}"))
            models.append(
                ModelSpec(
                    name=m_name,
                    collection_name=to_collection_name(m_name),
                    fields=fields,
                )
            )

    return SchemaSpec(models=models)
