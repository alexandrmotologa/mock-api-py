"""Custom URL rewriting and targeted route mocking middleware supporting wildcards, parameters, query rewrites, and mocked HTTP responses."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RewriteRule:
    """Represents a compiled pattern-to-target rewrite rule."""

    def __init__(self, source_pattern: str, target_pattern: str) -> None:
        self.source_raw = source_pattern
        self.target_raw = target_pattern

        # Check if target has a query string override
        if "?" in target_pattern:
            self.target_path, self.target_query = target_pattern.split("?", 1)
        else:
            self.target_path = target_pattern
            self.target_query = None

        # Compile regex: replace :param with ([^/]+) and * with (.*)
        regex_str = "^" + re.escape(self.source_raw) + "$"
        regex_str = regex_str.replace(r"\*", r"(.*)")
        regex_str = re.sub(r":([a-zA-Z0-9_]+)", r"([^/]+)", regex_str)
        self.regex = re.compile(regex_str)
        self.param_names = re.findall(r":([a-zA-Z0-9_]+)", self.source_raw)

    def match_and_rewrite(self, path: str) -> tuple[str, str | None] | None:
        """Matches path against the rule. Returns (new_path, new_query) or None."""
        match = self.regex.match(path)
        if not match:
            return None

        rewritten_path = self.target_path
        groups = match.groups()

        # Replace $1, $2, etc.
        for i, val in enumerate(groups, start=1):
            rewritten_path = rewritten_path.replace(f"${i}", val)

        # Replace :param names
        for p_name, val in zip(self.param_names, groups):
            rewritten_path = rewritten_path.replace(f":{p_name}", val)

        # Normalize path
        if not rewritten_path.startswith("/"):
            rewritten_path = "/" + rewritten_path

        return rewritten_path, self.target_query


class MockResponseRule:
    """Represents a rule that directly intercepts and responds with a mocked HTTP response."""

    def __init__(self, source_pattern: str, response_spec: dict[str, Any]) -> None:
        self.source_raw = source_pattern
        self.status_code = int(response_spec.get("status", 200))
        self.body = response_spec.get("body", {})
        self.headers = response_spec.get("headers", {})
        self.method = response_spec.get("method")  # e.g., "GET", "POST", or None for all

        # Compile regex pattern identical to RewriteRule
        regex_str = "^" + re.escape(self.source_raw) + "$"
        regex_str = regex_str.replace(r"\*", r"(.*)")
        regex_str = re.sub(r":([a-zA-Z0-9_]+)", r"([^/]+)", regex_str)
        self.regex = re.compile(regex_str)

    def matches(self, path: str, method: str) -> bool:
        """Checks whether the incoming path and HTTP method match this mock rule."""
        if self.method and self.method.upper() != method.upper():
            return False
        return bool(self.regex.match(path))


class URLRewriter:
    """Manages a list of RewriteRules and MockResponseRules loaded from dict or JSON file."""

    def __init__(self, rules: dict[str, Any] | None = None) -> None:
        self.rules: list[RewriteRule] = []
        self.mock_rules: list[MockResponseRule] = []
        if rules:
            for src, tgt in rules.items():
                if isinstance(tgt, dict):
                    self.mock_rules.append(MockResponseRule(src, tgt))
                elif isinstance(tgt, str):
                    rule = RewriteRule(src, tgt)
                    self.rules.append(rule)

    @classmethod
    def from_file(cls, file_path: str | Path) -> URLRewriter:
        path = Path(file_path)
        if not path.exists():
            return cls({})
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(data if isinstance(data, dict) else {})

    def get_mock_response(self, path: str, method: str) -> MockResponseRule | None:
        """Finds the first matching mock response rule for the given path and method."""
        for rule in self.mock_rules:
            if rule.matches(path, method):
                return rule
        return None

    def rewrite(self, path: str) -> tuple[str, str | None]:
        """Applies the first matching rewrite rule. Returns (new_path, optional_query)."""
        for rule in self.rules:
            result = rule.match_and_rewrite(path)
            if result is not None:
                return result
        return path, None


class URLRewriterMiddleware(BaseHTTPMiddleware):
    """ASGI Middleware modifying request path/query_string or short-circuiting with mock responses."""

    def __init__(self, app, rewriter: URLRewriter) -> None:
        super().__init__(app)
        self.rewriter = rewriter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        orig_path = request.scope.get("path", "")
        method = request.method

        # 1. Check for targeted mock response override
        mock_rule = self.rewriter.get_mock_response(orig_path, method)
        if mock_rule is not None:
            headers = dict(mock_rule.headers) if mock_rule.headers else {}
            if isinstance(mock_rule.body, str):
                content_type = headers.get("content-type") or headers.get("Content-Type")
                if content_type and "json" not in content_type.lower():
                    return Response(
                        content=mock_rule.body,
                        status_code=mock_rule.status_code,
                        headers=headers,
                        media_type=content_type,
                    )
            return JSONResponse(
                status_code=mock_rule.status_code,
                content=mock_rule.body,
                headers=headers,
            )

        # 2. Check for URL rewrite
        new_path, extra_query = self.rewriter.rewrite(orig_path)

        if new_path != orig_path:
            request.scope["path"] = new_path

        if extra_query:
            orig_query = request.scope.get("query_string", b"").decode("latin-1")
            if orig_query:
                combined_query = f"{extra_query}&{orig_query}".encode("latin-1")
            else:
                combined_query = extra_query.encode("latin-1")
            request.scope["query_string"] = combined_query

        return await call_next(request)
