"""Unit and integration tests for dynamic schema parser and schema-driven mock generator."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from mock_api_py.generator import generate_from_schema
from mock_api_py.schema_parser import (
    parse_inline_model,
    parse_schema_file,
    to_collection_name,
)


def test_to_collection_name_pluralization():
    assert to_collection_name("Patient") == "patients"
    assert to_collection_name("Order") == "orders"
    assert to_collection_name("Category") == "categories"
    assert to_collection_name("Box") == "boxes"
    assert to_collection_name("Person") == "people"
    assert to_collection_name("Child") == "children"
    assert to_collection_name("users") == "users"


def test_parse_inline_model_single():
    model_str = (
        "Patient:id,full_name:name,email:email,blood_type:choice(A+,A-,B+,B-,O+,O-),birth_date:date"
    )
    spec = parse_inline_model(model_str)

    assert len(spec.models) == 1
    model = spec.models[0]
    assert model.name == "Patient"
    assert model.collection_name == "patients"
    assert len(model.fields) == 5

    fields_by_name = {f.name: f for f in model.fields}
    assert fields_by_name["id"].type_name == "id"
    assert fields_by_name["full_name"].type_name == "name"
    assert fields_by_name["email"].type_name == "email"
    assert fields_by_name["blood_type"].type_name == "choice"
    assert fields_by_name["blood_type"].params == ["A+", "A-", "B+", "B-", "O+", "O-"]
    assert fields_by_name["birth_date"].type_name == "date"


def test_parse_inline_model_multiple():
    model_str = "User:id,name:name; Post:id,title:sentence,userId:id"
    spec = parse_inline_model(model_str)

    assert len(spec.models) == 2
    assert spec.models[0].name == "User"
    assert spec.models[0].collection_name == "users"
    assert spec.models[1].name == "Post"
    assert spec.models[1].collection_name == "posts"


def test_generate_from_schema_types_and_ranges():
    model_str = (
        "Product:id,name:name,email:email,phone:phone,price:price,created_at:date,"
        "tracking_id:uuid,color:choice(red,green,blue),quantity:int(10,50),in_stock:boolean"
    )
    spec = parse_inline_model(model_str)
    db = generate_from_schema(spec, count=25)

    assert "products" in db
    records = db["products"]
    assert len(records) == 25

    for idx, item in enumerate(records):
        assert item["id"] == idx + 1
        assert isinstance(item["name"], str) and len(item["name"]) > 0
        assert "@" in item["email"]
        assert isinstance(item["phone"], str)
        assert isinstance(item["price"], float)
        assert isinstance(item["created_at"], str)
        # Verify valid UUID
        parsed_uuid = uuid.UUID(item["tracking_id"])
        assert str(parsed_uuid) == item["tracking_id"]
        # Verify choice enum
        assert item["color"] in {"red", "green", "blue"}
        # Verify integer range
        assert 10 <= item["quantity"] <= 50
        # Verify boolean
        assert isinstance(item["in_stock"], bool)


def test_generate_from_schema_foreign_key_linking():
    # Intentionally list Post first to verify dependency sorting
    model_str = "Post:id,title:sentence,userId:id; User:id,name:name"
    spec = parse_inline_model(model_str)
    db = generate_from_schema(spec, count=15)

    assert "users" in db
    assert "posts" in db
    assert len(db["users"]) == 15
    assert len(db["posts"]) == 15

    user_ids = {u["id"] for u in db["users"]}
    for post in db["posts"]:
        assert post["userId"] in user_ids


def test_parse_and_generate_from_json_schema(tmp_path: Path):
    schema_data = {
        "definitions": {
            "Customer": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "fullName": {"type": "string", "faker": "name"},
                    "email": {"type": "string", "format": "email"},
                    "tier": {"type": "string", "enum": ["free", "pro", "enterprise"]},
                },
            },
            "Order": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "customerId": {"type": "integer"},
                    "total": {"type": "number"},
                },
            },
        }
    }
    schema_file = tmp_path / "schema.json"
    with open(schema_file, "w", encoding="utf-8") as f:
        json.dump(schema_data, f)

    spec = parse_schema_file(schema_file)
    assert len(spec.models) == 2

    out_file = tmp_path / "clinic_db.json"
    db = generate_from_schema(spec, count=10, output_path=str(out_file))

    assert "customers" in db
    assert "orders" in db
    assert len(db["customers"]) == 10
    assert len(db["orders"]) == 10

    # Verify foreign key customerId linked to customer IDs
    customer_ids = {c["id"] for c in db["customers"]}
    for order in db["orders"]:
        assert order["customerId"] in customer_ids

    # Verify output file saved to disk
    assert out_file.exists()
    with open(out_file, encoding="utf-8") as f:
        loaded = json.load(f)
    assert len(loaded["customers"]) == 10


def test_parse_and_generate_from_yaml_schema(tmp_path: Path):
    yaml_content = """
Doctor:
  id: id
  name: name
  specialty: choice(Cardiology,Neurology,Pediatrics)
Appointment:
  id: id
  doctorId: id
  date: date
"""
    schema_file = tmp_path / "schema.yaml"
    with open(schema_file, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    spec = parse_schema_file(schema_file)
    assert len(spec.models) == 2

    db = generate_from_schema(spec, count=5)
    assert "doctors" in db
    assert "appointments" in db
    assert len(db["doctors"]) == 5
    assert len(db["appointments"]) == 5

    doctor_ids = {d["id"] for d in db["doctors"]}
    for appt in db["appointments"]:
        assert appt["doctorId"] in doctor_ids
        assert appt["date"] is not None
