"""
JWT and Authentication Security Utilities using HMAC-SHA256.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional

# Secret key for token signing (in production, set via environment variable)
JWT_SECRET_KEY = "APBS_SUPER_SECRET_PRODUCTION_KEY_177_CHARS"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = 86400  # 24 hours


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s.encode("utf-8"))


def create_access_token(payload: Dict[str, Any], expires_in: int = JWT_EXPIRATION_SECONDS) -> str:
    """
    Generate an HMAC-SHA256 signed JWT token.
    """
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    body = dict(payload)
    body["exp"] = int(time.time()) + expires_in
    body["iat"] = int(time.time())

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    body_b64 = _b64url_encode(json.dumps(body, separators=(",", ":")).encode("utf-8"))

    signing_input = f"{header_b64}.{body_b64}".encode("utf-8")
    signature = hmac.new(JWT_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{header_b64}.{body_b64}.{sig_b64}"


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify signature and expiration of a JWT token. Returns payload or None.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, body_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{body_b64}".encode("utf-8")
        expected_sig = hmac.new(JWT_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload = json.loads(_b64url_decode(body_b64).decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            return None  # Token expired

        return payload
    except Exception:
        return None
