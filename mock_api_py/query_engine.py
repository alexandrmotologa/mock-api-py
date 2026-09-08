"""Query engine for filtering, full-text searching, sorting, and paginating collections."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


@dataclass
class QueryResult:
    """Encapsulates the filtered/paginated items and pagination metadata."""
    items: List[Dict[str, Any]]
    total_count: int
    link_header: Optional[str] = None


def _coerce_value(raw: str) -> Any:
    """Attempts to coerce query param string into boolean, int, float, or raw string."""
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower == "null" or lower == "none":
        return None

    # Try integer
    try:
        if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
            return int(raw)
    except ValueError:
        pass

    # Try float
    try:
        return float(raw)
    except ValueError:
        pass

    return raw


def _matches_full_text(obj: Any, term: str) -> bool:
    """Recursively checks if term (case-insensitive) is in any scalar values of obj."""
    term_lower = term.lower()
    if isinstance(obj, dict):
        return any(_matches_full_text(v, term_lower) for v in obj.values())
    if isinstance(obj, list):
        return any(_matches_full_text(elem, term_lower) for elem in obj)
    return term_lower in str(obj).lower()


def _compare_values(val: Any, target: Any, op: str) -> bool:
    """Compares two values under operator 'gte', 'lte', or 'ne' with automatic type coercion."""
    if val is None:
        return False

    # Attempt to convert to common type for comparison
    try:
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            target_num = float(target)
            if op == "gte":
                return val >= target_num
            elif op == "lte":
                return val <= target_num
            elif op == "ne":
                return val != target_num
        elif isinstance(val, str):
            target_str = str(target)
            if op == "gte":
                return val >= target_str
            elif op == "lte":
                return val <= target_str
            elif op == "ne":
                return val != target_str
    except (TypeError, ValueError):
        pass

    if op == "ne":
        return str(val) != str(target)

    return False


def _build_link_header(
    base_url: str,
    query_params: Dict[str, Any],
    page: int,
    limit: int,
    total_count: int,
) -> Optional[str]:
    """Builds an RFC-5988 Link header for pagination."""
    if limit <= 0 or total_count <= 0:
        return None

    total_pages = math.ceil(total_count / limit)
    if total_pages <= 1:
        return None

    def make_url(p: int) -> str:
        parsed = urlsplit(base_url)
        params = dict(parse_qsl(parsed.query))
        params.update(query_params)
        params["_page"] = str(p)
        params["_limit"] = str(limit)
        new_query = urlencode(params)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))

    links: List[str] = []
    links.append(f'<{make_url(1)}>; rel="first"')

    if page > 1:
        links.append(f'<{make_url(page - 1)}>; rel="prev"')

    if page < total_pages:
        links.append(f'<{make_url(page + 1)}>; rel="next"')

    links.append(f'<{make_url(total_pages)}>; rel="last"')

    return ", ".join(links)


def execute_query(
    items: List[Dict[str, Any]],
    params: Dict[str, Any],
    request_url: Optional[str] = None,
) -> QueryResult:
    """
    Executes full filtering, searching, sorting, and pagination on a list of dicts.
    Supported params:
      - `<key>=<value>`: Exact match
      - `<key>_gte=<value>`: Greater than or equal
      - `<key>_lte=<value>`: Less than or equal
      - `<key>_ne=<value>`: Not equal
      - `q=<search>`: Full-text search
      - `_sort=<fields>`: Comma-separated sort keys
      - `_order=<asc|desc>`: Sort directions
      - `_page=<number>`: 1-indexed page number
      - `_limit=<number>`: Page size
    """
    filtered = list(items)

    # 1. Separate reserved query parameters
    reserved = {"_sort", "_order", "_page", "_limit", "q"}
    filter_params = {k: v for k, v in params.items() if k not in reserved}

    # 2. Filter by fields and comparative operators
    for raw_key, raw_val in filter_params.items():
        if raw_key.endswith("_gte"):
            field = raw_key[:-4]
            coerced = _coerce_value(str(raw_val))
            filtered = [
                item for item in filtered
                if field in item and _compare_values(item[field], coerced, "gte")
            ]
        elif raw_key.endswith("_lte"):
            field = raw_key[:-4]
            coerced = _coerce_value(str(raw_val))
            filtered = [
                item for item in filtered
                if field in item and _compare_values(item[field], coerced, "lte")
            ]
        elif raw_key.endswith("_ne"):
            field = raw_key[:-3]
            coerced = _coerce_value(str(raw_val))
            filtered = [
                item for item in filtered
                if field not in item or _compare_values(item[field], coerced, "ne")
            ]
        else:
            # Exact match
            coerced = _coerce_value(str(raw_val))
            filtered = [
                item for item in filtered
                if raw_key in item and (
                    item[raw_key] == coerced or str(item[raw_key]).lower() == str(raw_val).lower()
                )
            ]

    # 3. Full-Text Search (q)
    query_term = params.get("q")
    if query_term is not None and str(query_term).strip():
        filtered = [
            item for item in filtered
            if _matches_full_text(item, str(query_term).strip())
        ]

    # 4. Sorting (_sort, _order)
    sort_fields_str = params.get("_sort")
    if sort_fields_str:
        sort_fields = [f.strip() for f in str(sort_fields_str).split(",") if f.strip()]
        order_str = str(params.get("_order", "asc")).lower()
        orders = [o.strip() for o in order_str.split(",") if o.strip()]

        # Sort in reverse order of fields so first specified field has highest precedence
        for i in reversed(range(len(sort_fields))):
            field = sort_fields[i]
            direction = orders[i] if i < len(orders) else (orders[0] if orders else "asc")
            is_desc = direction.lower() == "desc"

            def sort_key(item: Dict[str, Any]) -> Tuple[int, Any]:
                val = item.get(field)
                if val is None:
                    return (1, "")
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    return (0, float(val))
                return (0, str(val).lower())

            filtered.sort(key=sort_key, reverse=is_desc)

    total_count = len(filtered)

    # 5. Pagination (_page, _limit)
    page_param = params.get("_page")
    limit_param = params.get("_limit")
    link_header: Optional[str] = None

    if page_param is not None or limit_param is not None:
        try:
            page = max(1, int(page_param or 1))
        except (ValueError, TypeError):
            page = 1

        try:
            limit = max(1, int(limit_param or 10))
        except (ValueError, TypeError):
            limit = 10

        start = (page - 1) * limit
        end = start + limit
        paginated_items = filtered[start:end]

        if request_url:
            link_header = _build_link_header(request_url, params, page, limit, total_count)

        return QueryResult(items=paginated_items, total_count=total_count, link_header=link_header)

    return QueryResult(items=filtered, total_count=total_count, link_header=None)
