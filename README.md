# ⚡ mock-api-py (fastmock)

[![Tests](https://github.com/alexandrmotologa/mock-api-py/actions/workflows/test.yml/badge.svg)](https://github.com/alexandrmotologa/mock-api-py/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/Python-3.11%2B%20%7C%203.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> **Modern Instant Mock CRUD Engine with FastAPI, Rich CLI, and Chaos Testing.**  
> Spin up a full RESTful backend with filtering, sorting, pagination, and interactive Swagger documentation in under a second from a simple JSON file.

---

## 🚀 Why `mock-api-py`?

If you loved `json-server`, you will love `mock-api-py` even more:

- ⚡ **Lightning Fast**: Powered by ASGI and Uvicorn with async I/O.
- 📖 **Interactive Swagger UI**: Full OpenAPI docs automatically available at `/docs` and `/redoc`.
- 🎨 **Modern Console UX**: Styled Rich terminal output with detected resource tables and live-colored HTTP request logs.
- 🎲 **Built-in Chaos Engine**: Simulate realistic network conditions with latency jitter (`--delay 200-800`) and random 500 error injection (`--error-rate 0.1`) to test frontend resilience.
- 🔍 **Advanced Query Engine**:
  - Exact property filtering (`category=electronics&inStock=true`)
  - Comparative operators (`price_gt=25`, `price_gte=50`, `price_lt=100`, `price_lte=100`, `price_ne=29.99`)
  - Substring matching (`title_like=mouse`)
  - Full-text search across all object fields (`q=wireless`)
  - Multi-property sorting (`_sort=price&_order=desc`)
  - RFC-compliant pagination with `X-Total-Count` and `Link` headers (`_page=1&_limit=10`)
- 🔗 **Nested Relational Routes**: Automatically detects foreign keys (e.g. `userId` in `products` -> `GET /users/1/products`).
- 🤖 **Synthetic Data Generator**: Generate realistic datasets with Faker straight from the CLI (`mock-api generate`).
- 💾 **Safe Atomic Persistence**: In-memory speed by default with optional atomic write-back (`--save`) or strict `--read-only` mode.
- 👀 **Live Watch Mode**: Auto-reload in-memory data store when the JSON file changes on disk (`--watch`).
- 📁 **Static File Serving**: Serve static assets alongside mock APIs (`--static ./public`).

---

## 📦 Installation

Run directly with `uvx` (no installation required):
```bash
uvx mock-api-py db.json
```

Or install via `pip` / `uv`:
```bash
pip install mock-api-py
# or
uv tool install mock-api-py
```

---

## 🖥️ Console Interface

When you run `mock-api`, your terminal greets you with a clean, informative dashboard:

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                     ⚡ mock-api v0.1.0 ⚡                         ┃
┃           Modern Instant Mock CRUD Server for Developers         ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
 🚀 Server running at: http://127.0.0.1:8000
 📖 Interactive API Docs: http://127.0.0.1:8000/docs
 ⏱️  Simulated Delay: 300ms | 💾 Auto-save: ON
 📦 Detected Resources:
   • GET /products       [4 items]
   • GET /users          [2 items]
   • GET /profile        [1 object]

[2026-09-08 22:30:15] GET    /products?category=electronics - 200 OK (304.1ms)
[2026-09-08 22:30:18] POST   /products - 201 (301.5ms)
[2026-09-08 22:30:22] DELETE /products/1 - 200 OK (300.8ms)
```

---

## 🏁 Quickstart

### 1. Create a `db.json`
```json
{
  "products": [
    { "id": 1, "title": "Wireless Mouse", "price": 29.99, "category": "electronics", "inStock": true, "userId": 1 },
    { "id": 2, "title": "Mechanical Keyboard", "price": 89.99, "category": "electronics", "inStock": false, "userId": 1 }
  ],
  "users": [
    { "id": 1, "name": "Alice Johnson", "email": "alice@example.com" }
  ],
  "profile": {
    "name": "Alexandr",
    "theme": "dark"
  }
}
```

### 2. Start the Server
```bash
mock-api db.json
```

Visit:
- **API**: [http://127.0.0.1:8000/products](http://127.0.0.1:8000/products)
- **Interactive Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🛠️ CLI Usage & Flags

```bash
mock-api [DB_FILE] [OPTIONS]
```

### Options

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--port` | `-p` | `8000` | Port to bind the server to |
| `--host` | `-h` | `127.0.0.1` | Host address to bind |
| `--delay` | `-d` | `None` | Artificial latency in ms. Supports fixed (`300`) or jitter range (`200-800`) |
| `--error-rate` | `-e` | `0.0` | Random 500 error injection rate between `0.0` and `1.0` (e.g. `0.1` = 10%) |
| `--save` / `--write-back` | | `False` | Automatically persist POST/PUT/PATCH/DELETE mutations back to disk |
| `--read-only` | | `False` | Disallow all mutating HTTP methods (POST, PUT, PATCH, DELETE) |
| `--watch` | `-w` | `False` | Auto-reload in-memory database when the file is modified externally on disk |
| `--static` | | `None` | Directory to mount as static file server at `/static` |

---

## 🎲 Chaos Engineering Examples

Test how your React, Vue, or mobile frontend handles flaky networks and server errors:

```bash
# Add fixed 500ms latency to every request
mock-api db.json --delay 500

# Simulate variable 3G mobile network (jitter between 200ms and 900ms)
mock-api db.json --delay 200-900

# Inject a 15% random failure rate to test Error Boundaries
mock-api db.json --error-rate 0.15

# Combine jitter, chaos errors, and auto-save
mock-api db.json --delay 100-400 --error-rate 0.1 --save
```

---

## 🤖 Synthetic Data Generation

Need test data immediately? Generate realistic datasets with Faker:

```bash
mock-api generate --output data.json --schema "users:20,products:50,posts:30,comments:100"
```

Then boot it right up:
```bash
mock-api data.json
```

Supported built-in schemas: `users`, `products`, `posts`, `comments`, `todos`, `companies`, plus generic custom names.

---

## 📡 REST API & Query Reference

### Standard CRUD Endpoints
- `GET    /products` - List products with query filtering
- `GET    /products/1` - Get product by ID
- `POST   /products` - Create product (auto-generates unique ID)
- `PUT    /products/1` - Replace product
- `PATCH  /products/1` - Partially update product
- `DELETE /products/1` - Delete product

### Singleton Endpoints
- `GET   /profile` - Get singleton object
- `PATCH /profile` - Update singleton fields

### Query Parameters

| Feature | Example | Description |
|---------|---------|-------------|
| **Exact Filter** | `?category=electronics&inStock=true` | Filter by scalar attributes |
| **Greater Than or Equal** | `?price_gte=50` | Numeric or string comparison |
| **Less Than or Equal** | `?price_lte=100` | Numeric or string comparison |
| **Not Equal** | `?category_ne=furniture` | Exclude matching values |
| **Full-Text Search** | `?q=wireless` | Case-insensitive search across all fields |
| **Sort** | `?_sort=price&_order=desc` | Sort by field ascending or descending |
| **Pagination** | `?_page=1&_limit=10` | Returns items with `X-Total-Count` and RFC `Link` headers |
| **Nested Routes** | `GET /users/1/products` | Returns products belonging to `userId: 1` |

For detailed documentation, see [docs/api.md](docs/api.md).

---

## 🧪 Running Tests

```bash
# Create virtualenv and install dependencies
uv venv
uv pip install -e ".[dev]"

# Run full test suite
uv run pytest -v
```

---

## 📄 License

MIT © [Alexandr Motologa](LICENSE)
