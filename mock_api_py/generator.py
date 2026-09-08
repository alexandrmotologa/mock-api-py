"""Synthetic mock dataset generator powered by Faker."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional
from faker import Faker

fake = Faker()


def _generate_users(count: int) -> List[Dict[str, Any]]:
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


def _generate_products(count: int, user_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
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


def _generate_posts(count: int, user_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
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


def _generate_comments(count: int, post_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
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


def _generate_todos(count: int, user_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    return [
        {
            "id": i + 1,
            "userId": random.choice(user_ids) if user_ids else random.randint(1, 5),
            "title": fake.sentence(nb_words=4).rstrip("."),
            "completed": random.choice([True, False]),
        }
        for i in range(count)
    ]


def _generate_companies(count: int) -> List[Dict[str, Any]]:
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


def _generate_generic(entity: str, count: int) -> List[Dict[str, Any]]:
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


def generate_mock_database(schema_str: str, output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Generates a full mock dataset based on comma-separated entity:count specifications.
    Example schema_str: 'users:10,products:25,posts:50'
    """
    # Parse schema string
    specs: Dict[str, int] = {}
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

    db: Dict[str, Any] = {}
    user_ids: List[int] = []
    post_ids: List[int] = []

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
