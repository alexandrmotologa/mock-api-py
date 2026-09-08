"""Mock authentication engine with HS256 JWT tokens and authorization middleware."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from mock_api_py.store import DataStore

DEFAULT_SECRET = "mock-api-py-secret-jwt-key-3.12"
DOCS_PATHS = {"/docs", "/redoc", "/openapi.json", "/favicon.ico", "/_admin"}


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _base64url_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def create_access_token(payload: Dict[str, Any], secret: str = DEFAULT_SECRET, expires_in: int = 86400) -> str:
    """Generates a standard HS256 signed JSON Web Token."""
    header = {"alg": "HS256", "typ": "JWT"}
    token_payload = dict(payload)
    token_payload["exp"] = int(time.time()) + expires_in
    token_payload["iat"] = int(time.time())

    encoded_header = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _base64url_encode(json.dumps(token_payload, separators=(",", ":")).encode("utf-8"))

    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    encoded_signature = _base64url_encode(signature)

    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def verify_access_token(token: str, secret: str = DEFAULT_SECRET) -> Optional[Dict[str, Any]]:
    """Verifies a JWT signature and expiration. Returns payload if valid, None otherwise."""
    parts = token.strip().split(".")
    if len(parts) != 3:
        return None

    encoded_header, encoded_payload, encoded_signature = parts
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    expected_sig = _base64url_encode(hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest())

    if not hmac.compare_digest(expected_sig, encoded_signature):
        return None

    try:
        payload_bytes = _base64url_decode(encoded_payload)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None

    if "exp" in payload and time.time() > payload["exp"]:
        return None

    return payload


def create_auth_router(store: DataStore, secret: str = DEFAULT_SECRET) -> APIRouter:
    """Creates FastAPI router exposing /auth/login, /auth/register, and /auth/me."""
    router = APIRouter(prefix="/auth", tags=["Authentication"])

    @router.post("/login", summary="Login and receive a Bearer JWT token")
    async def login(request: Request):
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        email = body.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        # Lookup in users collection if available
        matched_user = None
        if store.is_collection("users"):
            for u in store.get_all("users"):
                if str(u.get("email", "")).lower() == str(email).lower():
                    matched_user = u
                    break

        if not matched_user:
            # Generate a mock user profile if not in users list
            matched_user = {
                "id": 1,
                "name": email.split("@")[0].capitalize(),
                "email": email,
                "role": "user",
            }

        token = create_access_token(
            payload={
                "sub": str(matched_user.get("id", 1)),
                "email": matched_user.get("email"),
                "role": matched_user.get("role", "user"),
            },
            secret=secret,
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": matched_user,
        }

    @router.post("/register", status_code=201, summary="Register a new user and receive a token")
    async def register(request: Request):
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        email = body.get("email")
        name = body.get("name")
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        new_user = {
            "name": name or email.split("@")[0].capitalize(),
            "email": email,
            "role": body.get("role", "user"),
        }

        created = store.create("users", new_user)
        token = create_access_token(
            payload={
                "sub": str(created.get("id")),
                "email": created.get("email"),
                "role": created.get("role"),
            },
            secret=secret,
        )

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": created,
        }

    @router.get("/me", summary="Get profile of currently authenticated user")
    async def get_me(request: Request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Bearer token")

        token = auth_header[7:].strip()
        payload = verify_access_token(token, secret=secret)
        if not payload:
            raise HTTPException(status_code=401, detail="Token expired or invalid")

        user_id = payload.get("sub")
        user = None
        if store.is_collection("users") and user_id:
            user = store.get_by_id("users", user_id)

        if not user:
            user = payload

        return {"user": user}

    return router


class AuthMiddleware(BaseHTTPMiddleware):
    """Protects mutating routes (POST, PUT, PATCH, DELETE) by requiring a valid Bearer token."""

    def __init__(self, app, secret: str = DEFAULT_SECRET) -> None:
        super().__init__(app)
        self.secret = secret

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Whitelist public paths
        if (
            path in DOCS_PATHS
            or path.startswith("/auth/")
            or path.startswith("/static")
            or path == "/"
        ):
            return await call_next(request)

        # Enforce token on mutating HTTP methods
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized: Missing or invalid Authorization Bearer token"},
                )

            token = auth_header[7:].strip()
            payload = verify_access_token(token, secret=self.secret)
            if not payload:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized: Bearer token is invalid or expired"},
                )

            # Attach user info to request state for downstream handlers
            request.state.user = payload

        return await call_next(request)
