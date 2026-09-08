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
