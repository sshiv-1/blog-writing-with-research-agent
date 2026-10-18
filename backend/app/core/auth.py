from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Optional

import jwt
from jwt import PyJWKClient, PyJWKClientError
from fastapi import HTTPException, Request

logger = logging.getLogger("app.core.auth")


@dataclass
class AuthUser:
    id: str
    email: Optional[str] = None
    role: str = "authenticated"


_ALLOWED_JWKS_ALGORITHMS = ["RS256", "ES256", "EdDSA"]
_jwks_client_lock = threading.Lock()
_jwks_clients: dict[str, PyJWKClient] = {}


def _get_jwks_client(supabase_url: str) -> PyJWKClient:
    """Return a cached PyJWKClient for the given Supabase URL."""
    clean_url = supabase_url.rstrip("/")
    with _jwks_client_lock:
        if clean_url not in _jwks_clients:
            jwks_uri = f"{clean_url}/auth/v1/.well-known/jwks.json"
            _jwks_clients[clean_url] = PyJWKClient(
                jwks_uri,
                cache_keys=True,
                max_cached_keys=16,
                lifespan=3600,
            )
        return _jwks_clients[clean_url]


def verify_supabase_jwt(token: str) -> AuthUser:
    """
    Verify a Supabase JWT token and return the authenticated user.
    Strictly enforces:
    - SUPABASE_URL presence
    - Algorithm pinning: HS256 (only if SUPABASE_JWT_SECRET configured),
      or RS256/ES256/EdDSA via JWKS. Rejects 'none' and unpinned algorithms.
    - Audience: 'authenticated'
    - Issuer: '{SUPABASE_URL}/auth/v1'
    """
    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    if not supabase_url:
        raise HTTPException(
            status_code=401,
            detail="SUPABASE_URL is not configured on the server.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )

    expected_issuer = f"{supabase_url}/auth/v1"
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")

    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Malformed token header.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )

    alg = header.get("alg")
    if not alg or alg.lower() == "none":
        raise HTTPException(
            status_code=401,
            detail="Token algorithm 'none' is rejected.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )

    payload: dict
    if alg == "HS256":
        if not jwt_secret or not jwt_secret.strip():
            raise HTTPException(
                status_code=401,
                detail="HS256 token rejected: SUPABASE_JWT_SECRET is not configured on server.",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
            )
        try:
            payload = jwt.decode(
                token,
                jwt_secret.strip(),
                algorithms=["HS256"],
                audience="authenticated",
                issuer=expected_issuer,
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=401,
                detail=f"Token validation failed: {str(exc)}",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
            )
    elif alg in _ALLOWED_JWKS_ALGORITHMS:
        try:
            jwks_client = _get_jwks_client(supabase_url)
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
                issuer=expected_issuer,
            )
        except (jwt.PyJWTError, PyJWKClientError) as exc:
            raise HTTPException(
                status_code=401,
                detail=f"Token validation failed: {str(exc)}",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
            )
        except Exception as exc:
            raise HTTPException(
                status_code=401,
                detail="Failed to retrieve or verify JWKS public key.",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
            )
    else:
        raise HTTPException(
            status_code=401,
            detail=f"Unsupported token algorithm '{alg}'.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Token payload missing subject ('sub').",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )

    return AuthUser(
        id=str(user_id),
        email=payload.get("email"),
        role=payload.get("role", "authenticated"),
    )


def _extract_token_from_header(auth_header: Optional[str]) -> Optional[str]:
    """Extract Bearer token from Authorization header, or None if not present/invalid format."""
    if not auth_header:
        return None
    parts = auth_header.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def get_current_user(request: Request) -> AuthUser:
    """
    FastAPI dependency for endpoints requiring authentication.
    Raises HTTP 401 if token is missing, expired, or invalid.
    """
    auth_header = request.headers.get("Authorization")
    token = _extract_token_from_header(auth_header)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_supabase_jwt(token)


def get_optional_user(request: Request) -> Optional[AuthUser]:
    """
    FastAPI dependency for endpoints with optional authentication (guests permitted).
    - If Authorization header is absent: returns None.
    - If Authorization header is present: validates token; raises 401 on invalid/expired token.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.strip():
        return None
    token = _extract_token_from_header(auth_header)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )
    return verify_supabase_jwt(token)
