# `mock-api-py` API & Query Specification

This document provides a detailed reference for all endpoints, query parameters, headers, and advanced features supported by `mock-api-py`.

---

## 1. REST Endpoints

### Collection Resources (Arrays)
For any key in `db.json` holding a JSON array (e.g., `products`, `users`):

| Method | Endpoint | Description | Response Status |
|--------|----------|-------------|-----------------|
| `GET` | `/{collection}` | List and query items with pagination, filtering, search, and sorting | `200 OK` |
| `GET` | `/{collection}/{id}` | Retrieve a specific item by identifier | `200 OK` or `404 Not Found` |
| `POST` | `/{collection}` | Create a new item (auto-generates unique `id` if omitted) | `201 Created` |
| `PUT` | `/{collection}/{id}` | Complete replacement of the item by ID | `200 OK` or `404 Not Found` |
| `PATCH` | `/{collection}/{id}` | Partial field update of the item by ID | `200 OK` or `404 Not Found` |
| `DELETE` | `/{collection}/{id}` | Remove the item by ID | `200 OK` or `404 Not Found` |

### Singleton Resources (Objects)
For any key in `db.json` holding a JSON object (e.g., `profile`):

| Method | Endpoint | Description | Response Status |
|--------|----------|-------------|-----------------|
| `GET` | `/{singleton}` | Retrieve the singleton object | `200 OK` |
| `PUT` | `/{singleton}` | Replace the singleton object | `200 OK` |
| `PATCH` | `/{singleton}` | Partially update fields in the singleton object | `200 OK` |

### Nested Relational Routes
When objects in collection `B` contain a foreign key pointing to collection `A` (e.g., `userId` linking to `users`):

```http
GET /users/1/products
```
Returns only the items in `products` where `userId == 1`. Full query parameters (filtering, search, pagination, sorting) are also supported on nested endpoints.

---

## 2. Query Engine Reference

### Exact Match Filtering
Filter by any top-level scalar property. Types (boolean, integer, float) are coerced automatically:
```http
GET /products?category=electronics&inStock=true
```

### Comparative & Pattern Operators
Filter numeric or string fields using suffixes:
* `_gt`: Strictly greater than
  ```http
  GET /products?price_gt=50
  ```
* `_gte`: Greater than or equal
  ```http
  GET /products?price_gte=50
  ```
* `_lt`: Strictly less than
  ```http
  GET /products?price_lt=100
  ```
* `_lte`: Less than or equal
  ```http
  GET /products?price_lte=100
  ```
* `_ne`: Not equal
  ```http
  GET /products?category_ne=furniture
  ```
* `_like`: Substring search on specific field (case-insensitive)
  ```http
  GET /products?title_like=wireless
  ```

### Full-Text Search
Recursively scans all scalar fields for the search term (case-insensitive):
```http
GET /products?q=wireless
```

### Sorting
Order collections by one or more properties:
```http
GET /products?_sort=price&_order=desc
GET /products?_sort=category,price&_order=asc,desc
```

### Pagination & Headers
Paginate results with page and limit parameters:
```http
GET /products?_page=1&_limit=10
```

#### Response Headers:
* `X-Total-Count`: Total number of matching records before pagination.
* `Link`: RFC-5988 pagination links for `first`, `prev`, `next`, and `last` pages:
  ```http
  Link: <http://127.0.0.1:8000/products?_page=1&_limit=10>; rel="first", <http://127.0.0.1:8000/products?_page=2&_limit=10>; rel="next", <http://127.0.0.1:8000/products?_page=5&_limit=10>; rel="last"
  ```
* `Access-Control-Expose-Headers`: Exposes `X-Total-Count, Link` to browser clients.

---

## 3. Chaos Engineering & Simulation

### Latency Injection (`--delay`)
* Fixed latency: `--delay 300` (adds 300ms to every request).
* Jitter range: `--delay 100-500` (adds a random latency between 100ms and 500ms).

### Chaos Error Rate (`--error-rate`)
* Inject random HTTP 500 errors: `--error-rate 0.1` (10% of requests will fail).
* The documentation endpoints (`/docs`, `/redoc`, `/openapi.json`) are automatically exempt from chaos injection so developers can inspect schemas uninterrupted.

---

## 4. Authentication Endpoints (`--auth`)

When started with `--auth`, the server exposes dedicated authentication routes and protects write operations (`POST`, `PUT`, `PATCH`, `DELETE`):

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/login` | Login with email/password; returns access token & user profile |
| `POST` | `/auth/register` | Register new user in `users` collection; returns access token |
| `GET` | `/auth/me` | Inspect current user payload from `Authorization: Bearer <token>` |

---

## 5. Custom URL Rewriting (`--routes`)

Supply a JSON mapping file (e.g. `routes.json`) to rewrite paths and default parameters before route evaluation:
```json
{
  "/api/*": "/$1",
  "/articles/:id": "/posts/:id",
  "/top-products": "/products?_sort=price&_order=desc"
}
```

---

## 6. Web Studio Dashboard (`/_admin`)

Access the browser dashboard at:
```http
GET /_admin
```
Provides visual table view, raw JSON inspector, full-text search, live filtering, system health status, one-click TypeScript definitions modal, and instant database reset.

---

## 7. System Utilities

### TypeScript Definitions
Generate ready-to-use TypeScript interfaces inferred from the current database records:
```http
GET /_types
```
Response (`text/plain; charset=utf-8`):
```typescript
/**
 * TypeScript Definitions
 * Auto-generated by mock-api-py
 */

export interface Product {
  id: number;
  category: string;
  inStock: boolean;
  price: number;
  title: string;
  userId: number;
}

export interface Database {
  products: Product[];
}
```

### Instant Database Reset
Revert all collections and singletons to their boot state (snapshot taken upon starting the server):
```http
POST /_reset
```
Response (`application/json`):
```json
{
  "message": "Database reset to initial boot snapshot successfully",
  "resources": {
    "products": 4,
    "users": 2
  }
}
```

---

## 8. Mock File Uploads

Upload files (images, PDFs, documents) without configuring cloud storage:

```http
POST /upload
Content-Type: multipart/form-data
```
Body:
`file`: binary payload

Response (`application/json`):
```json
{
  "url": "/uploads/avatar.png",
  "filename": "avatar.png",
  "size": 18240,
  "contentType": "image/png"
}
```

Uploaded files are immediately served from:
```http
GET /uploads/{filename}
```

---

## 9. Smart Auto-Port Fallback

When running the CLI:
```bash
mock-api db.json --port 8000
```
If port 8000 is already in use by another service, `mock-api-py` will automatically test consecutive ports (`8001`, `8002`, ...) and bind to the first available port, notifying the developer in the console.

