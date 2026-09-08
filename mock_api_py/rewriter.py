"""Custom URL rewriting middleware supporting wildcards, parameters, and query rewrites."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


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

    def match_and_rewrite(self, path: str) -> Optional[Tuple[str, Optional[str]]]:
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


class URLRewriter:
    """Manages a list of RewriteRules loaded from dict or JSON file."""

    def __init__(self, rules: Optional[Dict[str, str]] = None) -> None:
        self.rules: List[RewriteRule] = []
        if rules:
            for src, tgt in rules.items():
                self.rules.append(RewriteRule(src, tgt))

    @classmethod
    def from_file(cls, file_path: Union[str, Path]) -> URLRewriter:
        path = Path(file_path)
        if not path.exists():
            return cls({})
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data if isinstance(data, dict) else {})

    def rewrite(self, path: str) -> Tuple[str, Optional[str]]:
        """Applies the first matching rewrite rule. Returns (new_path, optional_query)."""
        for rule in self.rules:
            result = rule.match_and_rewrite(path)
            if result is not None:
                return result
        return path, None


class URLRewriterMiddleware(BaseHTTPMiddleware):
    """ASGI Middleware modifying request path/query_string before route resolution."""

    def __init__(self, app, rewriter: URLRewriter) -> None:
        super().__init__(app)
        self.rewriter = rewriter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        orig_path = request.scope.get("path", "")
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
