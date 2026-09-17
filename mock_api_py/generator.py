"""Synthetic mock dataset generator powered by Faker."""

from __future__ import annotations

import json
import random
import uuid
from pathlib import Path
from typing import Any

from faker import Faker

from mock_api_py.schema_parser import FieldSpec, ModelSpec, SchemaSpec

fake = Faker()


def _generate_users(count: int) -> list[dict[str, Any]]:
    roles = ["admin", "editor", "user", "viewer"]
    return [
        {
            "id": i + 1,
            "name": fake.name(),
            "email": fake.unique.email(),
            "role": random.choice(roles),
            "avatarUrl": f"https://api.dicebear.com/7.x/avataaars/svg?seed={fake.user_name()}",
            "createdAt": fake.date_time_between(start_date="-1y", end_date="now").isoformat(),
        }
        for i in range(count)
    ]


def _generate_products(count: int, user_ids: list[int] | None = None) -> list[dict[str, Any]]:
    categories = ["electronics", "audio", "office", "books", "clothing", "gaming"]
    return [
        {
            "id": i + 1,
            "title": fake.catch_phrase(),
            "price": round(random.uniform(9.99, 999.99), 2),
            "category": random.choice(categories),
            "inStock": random.choice([True, True, False]),  # 66% in stock
            "rating": round(random.uniform(3.0, 5.0), 1),
            "description": fake.paragraph(nb_sentences=2),
            "userId": random.choice(user_ids) if user_ids else random.randint(1, 5),
        }
        for i in range(count)
    ]


def _generate_posts(count: int, user_ids: list[int] | None = None) -> list[dict[str, Any]]:
    all_tags = ["tech", "ai", "webdev", "python", "tutorial", "news", "productivity"]
    return [
        {
            "id": i + 1,
            "title": fake.sentence(nb_words=6).rstrip("."),
            "body": "\n\n".join(fake.paragraphs(nb=3)),
            "userId": random.choice(user_ids) if user_ids else random.randint(1, 5),
            "tags": random.sample(all_tags, k=random.randint(1, 3)),
            "createdAt": fake.date_time_between(start_date="-6m", end_date="now").isoformat(),
        }
        for i in range(count)
    ]


def _generate_comments(count: int, post_ids: list[int] | None = None) -> list[dict[str, Any]]:
    return [
        {
            "id": i + 1,
            "postId": random.choice(post_ids) if post_ids else random.randint(1, 10),
            "name": fake.name(),
            "email": fake.email(),
            "body": fake.paragraph(nb_sentences=2),
        }
        for i in range(count)
    ]


def _generate_todos(count: int, user_ids: list[int] | None = None) -> list[dict[str, Any]]:
    return [
        {
            "id": i + 1,
            "userId": random.choice(user_ids) if user_ids else random.randint(1, 5),
            "title": fake.sentence(nb_words=4).rstrip("."),
            "completed": random.choice([True, False]),
        }
        for i in range(count)
    ]


def _generate_companies(count: int) -> list[dict[str, Any]]:
    return [
        {
            "id": i + 1,
            "name": fake.company(),
            "catchPhrase": fake.catch_phrase(),
            "bs": fake.bs(),
            "country": fake.country(),
        }
        for i in range(count)
    ]


def _generate_generic(entity: str, count: int) -> list[dict[str, Any]]:
    return [
        {
            "id": i + 1,
            "title": f"{entity.rstrip('s').capitalize()} {i + 1}",
            "description": fake.sentence(),
            "isActive": random.choice([True, False]),
            "createdAt": fake.date_time_between(start_date="-1y", end_date="now").isoformat(),
        }
        for i in range(count)
    ]


def generate_mock_database(schema_str: str, output_path: str | None = None) -> dict[str, Any]:
    """
    Generates a full mock dataset based on comma-separated entity:count specifications.
    Example schema_str: 'users:10,products:25,posts:50'
    """
    # Parse schema string
    specs: dict[str, int] = {}
    for part in schema_str.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            name, count_str = part.split(":", 1)
            try:
                specs[name.strip().lower()] = max(1, int(count_str.strip()))
            except ValueError:
                specs[name.strip().lower()] = 10
        else:
            specs[part.strip().lower()] = 10

    db: dict[str, Any] = {}
    user_ids: list[int] = []
    post_ids: list[int] = []

    # 1. Generate users first if requested (for relations)
    if "users" in specs:
        users = _generate_users(specs["users"])
        db["users"] = users
        user_ids = [u["id"] for u in users]

    # 2. Generate posts (relates to users)
    if "posts" in specs:
        posts = _generate_posts(specs["posts"], user_ids=user_ids)
        db["posts"] = posts
        post_ids = [p["id"] for p in posts]

    # 3. Generate products (relates to users)
    if "products" in specs:
        db["products"] = _generate_products(specs["products"], user_ids=user_ids)

    # 4. Generate comments (relates to posts)
    if "comments" in specs:
        db["comments"] = _generate_comments(specs["comments"], post_ids=post_ids)

    # 5. Generate todos (relates to users)
    if "todos" in specs:
        db["todos"] = _generate_todos(specs["todos"], user_ids=user_ids)

    # 6. Generate companies
    if "companies" in specs:
        db["companies"] = _generate_companies(specs["companies"])

    # 7. Any other custom entities
    known = {"users", "posts", "products", "comments", "todos", "companies"}
    for name, count in specs.items():
        if name not in known:
            db[name] = _generate_generic(name, count)

    # 8. Add a default profile singleton
    db["profile"] = {
        "name": fake.name(),
        "bio": fake.catch_phrase(),
        "theme": "dark",
    }

    # Save to file if output_path specified
    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return db


def _generate_field_value(
    field_spec: FieldSpec,
    index: int,
    db: dict[str, list[dict[str, Any]]],
) -> Any:
    # 1. Relational Foreign Key Linking
    if field_spec.name.endswith("Id") and len(field_spec.name) > 2:
        prefix = field_spec.name[:-2].lower()
        candidates = [
            prefix + "s",
            prefix + "es",
            prefix[:-1] + "ies" if prefix.endswith("y") else prefix + "s",
            prefix,
        ]
        for candidate in candidates:
            if candidate in db and db[candidate]:
                parent_ids = [
                    item["id"]
                    for item in db[candidate]
                    if isinstance(item, dict) and "id" in item
                ]
                if parent_ids:
                    return random.choice(parent_ids)

    type_name = field_spec.type_name.lower()

    if type_name == "id":
        if field_spec.params == "uuid":
            return str(uuid.uuid4())
        return index + 1

    if type_name in {"name", "full_name"}:
        return fake.name()
    if type_name == "first_name":
        return fake.first_name()
    if type_name == "last_name":
        return fake.last_name()
    if type_name == "email":
        try:
            return fake.unique.email()
        except Exception:
            return fake.email()
    if type_name == "phone":
        return fake.phone_number()
    if type_name in {"price", "amount"}:
        return round(random.uniform(9.99, 999.99), 2)
    if type_name in {"date", "created_at", "updated_at"}:
        return fake.date_time_between(start_date="-1y", end_date="now").isoformat()
    if type_name == "uuid":
        return str(uuid.uuid4())
    if type_name == "choice":
        if isinstance(field_spec.params, (list, tuple)) and field_spec.params:
            return random.choice(field_spec.params)
        return fake.word()
    if type_name in {"int", "integer"}:
        if isinstance(field_spec.params, (list, tuple)) and len(field_spec.params) >= 2:
            return random.randint(int(field_spec.params[0]), int(field_spec.params[1]))
        return random.randint(1, 1000)
    if type_name in {"float", "number"}:
        if isinstance(field_spec.params, (list, tuple)) and len(field_spec.params) >= 2:
            return round(random.uniform(float(field_spec.params[0]), float(field_spec.params[1])), 2)
        return round(random.uniform(1.0, 100.0), 2)
    if type_name in {"boolean", "bool"}:
        return random.choice([True, False])
    if type_name in {"text", "paragraph", "description", "body"}:
        return fake.paragraph(nb_sentences=2)
    if type_name in {"sentence", "title"}:
        return fake.sentence(nb_words=5).rstrip(".")
    if type_name == "word":
        return fake.word()
    if type_name in {"avatar", "avatar_url"}:
        return f"https://api.dicebear.com/7.x/avataaars/svg?seed={fake.user_name()}"
    if type_name in {"url", "website"}:
        return fake.url()
    if type_name == "address":
        return fake.address()
    if type_name == "city":
        return fake.city()
    if type_name == "country":
        return fake.country()
    if type_name == "company":
        return fake.company()
    if type_name in {"catchphrase", "catch_phrase"}:
        return fake.catch_phrase()

    # Dynamic fallback based on field name
    lower_name = field_spec.name.lower()
    if "email" in lower_name:
        return fake.email()
    if "name" in lower_name:
        return fake.name()
    if "date" in lower_name:
        return fake.date_time_between(start_date="-1y", end_date="now").isoformat()
    if "phone" in lower_name:
        return fake.phone_number()
    if any(k in lower_name for k in ("price", "amount", "total")):
        return round(random.uniform(9.99, 999.99), 2)

    return fake.word()


def _sort_models_by_dependency(models: list[ModelSpec]) -> list[ModelSpec]:
    """Sorts models so that referenced parent entities are generated before dependent entities."""
    collection_to_model = {m.collection_name: m for m in models}

    def get_deps(m: ModelSpec) -> set[str]:
        deps = set()
        for f in m.fields:
            if f.name.endswith("Id") and len(f.name) > 2:
                prefix = f.name[:-2].lower()
                candidates = [
                    prefix + "s",
                    prefix + "es",
                    prefix[:-1] + "ies" if prefix.endswith("y") else prefix + "s",
                    prefix,
                ]
                for c in candidates:
                    if c in collection_to_model and c != m.collection_name:
                        deps.add(c)
        return deps

    ordered: list[ModelSpec] = []
    seen: set[str] = set()

    for _ in range(len(models)):
        for m in models:
            if m.collection_name not in seen:
                deps = get_deps(m)
                if deps.issubset(seen):
                    ordered.append(m)
                    seen.add(m.collection_name)

    for m in models:
        if m.collection_name not in seen:
            ordered.append(m)
            seen.add(m.collection_name)

    return ordered


def generate_from_schema(
    spec: SchemaSpec,
    count: int = 10,
    output_path: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Generates realistic synthetic mock collections using a parsed SchemaSpec,
    automatically resolving foreign key relations between collections.
    """
    db: dict[str, list[dict[str, Any]]] = {}
    sorted_models = _sort_models_by_dependency(spec.models)

    for model in sorted_models:
        item_count = model.count if model.count is not None else count
        items: list[dict[str, Any]] = []

        for i in range(item_count):
            item: dict[str, Any] = {}
            for field_spec in model.fields:
                item[field_spec.name] = _generate_field_value(field_spec, i, db)
            items.append(item)

        db[model.collection_name] = items

    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return db
