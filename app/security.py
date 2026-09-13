"""Segurança: hash de senha e cookies assinados por HMAC."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from app.config import SECRET_KEY

_PEPPER = b"pymaster-cookie-v1"
_SALT = b"pymaster-password-v1"


def hash_password(password: str) -> str:
    iterations = 260_000
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), _SALT, iterations
    )
    return f"pbkdf2${iterations}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _scheme, iterations, hex_digest = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _SALT, int(iterations)
        )
        return hmac.compare_digest(digest.hex(), hex_digest)
    except Exception:
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text.encode("ascii"))


def make_session_token(user_id: int, days: int = 90) -> str:
    payload = json.dumps({"uid": user_id, "exp": int(time.time()) + days * 86400}).encode()
    body = _b64(payload)
    sig = hmac.new(_PEPPER, body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read_session_token(token: str) -> int | None:
    try:
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(_PEPPER, body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        payload = json.loads(_unb64(body))
        if payload.get("exp", 0) < time.time():
            return None
        return int(payload["uid"])
    except Exception:
        return None