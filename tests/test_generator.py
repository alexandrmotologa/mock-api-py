"""Unit tests for Faker synthetic data generation."""

import json
from mock_api_py.generator import generate_mock_database


def test_generator_schema_parsing(tmp_path):
    out_file = tmp_path / "gen_data.json"
    schema = "users:5,products:8,posts:4"

    db = generate_mock_database(schema_str=schema, output_path=str(out_file))

    assert "users" in db
    assert len(db["users"]) == 5
    assert "products" in db
    assert len(db["products"]) == 8
    assert "posts" in db
    assert len(db["posts"]) == 4
    assert "profile" in db

    # Verify relationships: posts have userId
    user_ids = {u["id"] for u in db["users"]}
    for post in db["posts"]:
        assert post["userId"] in user_ids

    # Verify file saved to disk
    assert out_file.exists()
    with open(out_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert len(loaded["users"]) == 5
