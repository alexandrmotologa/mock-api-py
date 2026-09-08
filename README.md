<p align="center">
  <img src="docs/images/logo.png" alt="mock-api-py logo" width="130" />
</p>

<h1 align="center">mock-api-py (fastmock)</h1>

<p align="center">
  <a href="https://pypi.org/project/mock-api-py/"><img src="https://img.shields.io/pypi/v/mock-api-py.svg?color=blue&logo=pypi&logoColor=white" alt="PyPI version" /></a>
  <a href="https://github.com/alexandrmotologa/mock-api-py/actions/workflows/test.yml"><img src="https://github.com/alexandrmotologa/mock-api-py/actions/workflows/test.yml/badge.svg" alt="Tests" /></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B%20%7C%203.12-blue?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
</p>

<p align="center">
  Instant mock REST API engine built with Python and FastAPI.<br>
  Serves CRUD endpoints, sorting, filtering, pagination, and OpenAPI docs from a JSON file.
</p>

## Features

- **FastAPI and ASGI engine**: Runs on Uvicorn with asynchronous I/O.
- **OpenAPI documentation**: Interactive Swagger UI at `/docs` and ReDoc at `/redoc`.
- **Terminal dashboard**: Displays detected resource routes and colored HTTP request logs via Rich.
- **Chaos testing**: Configurable latency jitter (`--delay 200-800`) and random 500 error injection (`--error-rate 0.1`).
- **Query engine**: Supports exact filtering, comparisons (`_gt`, `_gte`, `_lt`, `_lte`, `_ne`), substring matching (`_like`), full-text search (`q=`), sorting (`_sort`, `_order`), and pagination (`_page`, `_limit`) with `X-Total-Count` and RFC `Link` headers.
- **Relational routes**: Automatically connects foreign keys (such as `userId` in `products` mapping to `/users/1/products`).
- **TypeScript generator**: Exports TypeScript interfaces matching your collections via `GET /_types` or through the admin interface.
- **Database reset**: Reverts data back to its boot snapshot on demand via `POST /_reset`.
- **File uploads**: Accepts multipart uploads at `POST /upload` and serves them from `/uploads/<filename>`.
- **Port fallback**: Finds and binds the next open port if port 8000 is occupied.
- **Authentication**: Provides JWT authentication endpoints (`/auth/login`, `/auth/register`, `/auth/me`) and protects mutating routes when `--auth` is enabled.
- **Route rewrites**: Remaps URLs and query strings using a `routes.json` file (`--routes`).
- **Web studio**: Browser dashboard at `/_admin` with data tables, JSON viewer, query builder, and database reset.
- **Storage options**: In-memory storage by default, with optional disk persistence (`--save`) or read-only mode (`--read-only`).
- **File watching**: Reloads in-memory data when the database file changes on disk (`--watch`).
- **Static files**: Serves static assets from a designated folder (`--static`).

## Quickstart

### Run with uvx (no installation needed)

If you have [uv](https://docs.astral.sh/uv/) installed:

#### Run with in-memory sample data
```bash
uvx mock-api-py
```
Starts with an in-memory database (`posts`, `users`, `profile`). No file is written to disk.

#### Run with a JSON file
```bash
uvx mock-api-py db.json
```
If `db.json` does not exist in the working directory, `mock-api-py` creates a starter file with sample data and boots the server immediately.

### Generate synthetic data with Faker

To generate mock data before starting:

```bash
# Generate sample records
uvx mock-api-py generate --output db.json --schema "users:20,products:50,posts:30"

# Start the server
uvx mock-api-py db.json
```

### Install with pip

To install into a Python environment:

```bash
pip install mock-api-py
```

Run using any of the available command aliases:
```bash
mock-api db.json
fastmock db.json
mock-api-py db.json
```

## Terminal output

When started, the terminal lists detected endpoints and documentation URLs:

<p align="center">
  <img src="docs/images/terminal_banner.png" alt="mock-api Terminal Dashboard" width="750" />
</p>

Default URLs:
- Web Studio: [http://127.0.0.1:8000/_admin](http://127.0.0.1:8000/_admin)
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Sample collection: [http://127.0.0.1:8000/posts](http://127.0.0.1:8000/posts)

Press `Ctrl + C` to stop the server.

## Frequently asked questions

<details>
<summary><b>What is uvx and how do I install it?</b></summary>

`uvx` runs Python CLI tools in isolated environments without installing them globally. It comes bundled with [uv](https://github.com/astral-sh/uv).

Install `uv` on Windows (PowerShell):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Install on macOS or Linux:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or install via pip:
```bash
pip install uv
```
</details>

<details>
<summary><b>Where is db.json located?</b></summary>

The file is read from or created in the current working directory of your terminal.
</details>

<details>
<summary><b>What happens if port 8000 is occupied?</b></summary>

The server searches for the next open port (such as 8001) and binds to it automatically, logging the selected port in the console.
</details>

## CLI options

```bash
mock-api [DB_FILE] [OPTIONS]
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--port` | `-p` | `8000` | Port to bind the server to |
| `--host` | `-h` | `127.0.0.1` | Host address to bind |
| `--delay` | `-d` | `None` | Artificial latency in milliseconds (supports fixed values like `300` or ranges like `200-800`) |
| `--error-rate` | `-e` | `0.0` | Random HTTP 500 error rate between `0.0` and `1.0` |
| `--save` / `--write-back` | | `False` | Write POST, PUT, PATCH, and DELETE changes back to disk |
| `--read-only` | | `False` | Reject mutating requests (POST, PUT, PATCH, DELETE) |
| `--watch` | `-w` | `False` | Reload data when the database file is modified on disk |
| `--static` | | `None` | Directory to mount as a static file server at `/static` |
| `--auth` | | `False` | Enable JWT authentication and require tokens on write requests |
| `--routes` | `-r` | `None` | Path to a custom route rewrite file |

## Web studio

The admin interface runs at `http://127.0.0.1:8000/_admin`.

Features:
- Resource list showing collections, singletons, and record counts
- Search bar (`q=`) and sorting options
- Data table view and raw JSON view
- TypeScript interface preview modal
- Database reset button
- Direct links to Swagger documentation

<p align="center">
  <img src="docs/images/web_dashboard.png" alt="mock-api Web Studio Dashboard" width="750" />
</p>

## TypeScript generator

You can generate TypeScript interfaces matching your database collections directly from the CLI or within the Web Studio modal:

<p align="center">
  <img src="docs/images/typescript_modal.png" alt="TypeScript Definitions Studio Modal" width="750" />
</p>

Download the types directly via cURL:
```bash
curl http://127.0.0.1:8000/_types > src/types/api.ts
```

Example generated output:
```typescript
export interface User {
  id: number;
  name: string;
  email: string;
  role?: string;
}

export interface Product {
  id: number;
  title: string;
  price: number;
  category: string;
  inStock: boolean;
}

export interface Database {
  users: User[];
  products: Product[];
}
```

## Database reset

To restore the in-memory or persisted database back to its startup state:

```bash
curl -X POST http://127.0.0.1:8000/_reset
```

You can also trigger a reset using the "Reset DB" button in the Web Studio (`/_admin`).

## File uploads

Upload files using multipart form data:

```bash
curl -F "file=@avatar.png" http://127.0.0.1:8000/upload
```

Response:
```json
{
  "url": "/uploads/avatar.png",
  "filename": "avatar.png",
  "size": 42150,
  "contentType": "image/png"
}
```

Uploaded files are served statically from `http://127.0.0.1:8000/uploads/<filename>`.

## Port fallback

If the requested port is already in use, `mock-api-py` selects the next available port and logs the change:

```
Port 8000 is busy. Switched to available port 8001.
```

## Authentication

To enable token authentication:

```bash
mock-api db.json --auth
```

When `--auth` is enabled:
1. `GET` requests and Swagger docs remain open.
2. Mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`) require an `Authorization: Bearer <token>` header, returning `401 Unauthorized` when the token is missing or invalid.
3. Available auth routes:
   - `POST /auth/login` with `{"email": "alice@example.com", "password": "any"}`
   - `POST /auth/register` with `{"name": "Charlie", "email": "charlie@example.com"}`
   - `GET /auth/me` with `Authorization: Bearer <token>`

## Custom route rewrites

To rewrite paths or map legacy URLs, pass a `routes.json` file:

```bash
mock-api db.json --routes routes.json
```

`routes.json`:
```json
{
  "/api/*": "/$1",
  "/articles/:id": "/posts/:id",
  "/top-products": "/products?_sort=price&_order=desc"
}
```

Mapped requests:
- `GET /api/users` routes to `GET /users`
- `GET /articles/42` routes to `GET /posts/42`
- `GET /top-products` routes to `GET /products?_sort=price&_order=desc`

## Chaos testing

Simulate network latency and server errors to test frontend handling:

```bash
# Add fixed 500ms latency to every request
mock-api db.json --delay 500

# Add variable jitter between 200ms and 900ms
mock-api db.json --delay 200-900

# Inject a 15% rate of HTTP 500 errors
mock-api db.json --error-rate 0.15

# Combine latency jitter, error injection, and disk persistence
mock-api db.json --delay 100-400 --error-rate 0.1 --save
```

## Synthetic data generation

Generate test datasets using Faker:

```bash
mock-api generate --output data.json --schema "users:20,products:50,posts:30,comments:100"
```

Start the server with the generated file:
```bash
mock-api data.json
```

Supported schemas: `users`, `products`, `posts`, `comments`, `todos`, `companies`, and generic custom names.

## API reference

All endpoints are documented interactively in Swagger UI at `/docs`:

<p align="center">
  <img src="docs/images/swagger_docs.png" alt="Interactive Swagger OpenAPI Docs" width="750" />
</p>

### CRUD endpoints
- `GET    /<collection>`: List items with filtering, sorting, and pagination
- `GET    /<collection>/:id`: Get item by ID
- `POST   /<collection>`: Create item (assigns a unique ID)
- `PUT    /<collection>/:id`: Replace item
- `PATCH  /<collection>/:id`: Partially update item
- `DELETE /<collection>/:id`: Delete item

### Singleton endpoints
- `GET   /<singleton>`: Get singleton object
- `PATCH /<singleton>`: Update singleton fields

### Query parameters

| Parameter | Example | Description |
|-----------|---------|-------------|
| Exact filter | `?category=electronics&inStock=true` | Filters by matching properties |
| Comparison | `?price_gte=50&price_lte=100` | Supports `_gt`, `_gte`, `_lt`, `_lte`, `_ne` |
| Substring match | `?title_like=mouse` | Case-insensitive substring match |
| Full-text search | `?q=wireless` | Searches across all object fields |
| Sort | `?_sort=price&_order=desc` | Sorts ascending (`asc`) or descending (`desc`) |
| Pagination | `?_page=1&_limit=10` | Paginates results with `X-Total-Count` and RFC `Link` headers |
| Nested routes | `GET /users/1/products` | Filters products matching `userId: 1` |

For more details, see [docs/api.md](docs/api.md).

## Development and tests

```bash
# Set up virtual environment and install dependencies
uv venv
uv pip install -e ".[dev]"

# Run test suite
uv run pytest -v
```

## License

MIT (c) [Alexandr Motologa](LICENSE)
