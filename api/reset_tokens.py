"""
In-memory store for password-reset tokens.
Each token is a random 32-byte hex string, valid for 15 minutes.
"""
import secrets
import time
from typing import Optional

_EXPIRE_SECONDS = 15 * 60  # 15 min

# token -> (user_email, expires_at)
_store: dict[str, tuple[str, float]] = {}


def generate(email: str) -> str:
    token = secrets.token_hex(32)
    _store[token] = (email, time.monotonic() + _EXPIRE_SECONDS)
    return token


def consume(token: str) -> Optional[str]:
    """Return email if token is valid and remove it, else None."""
    entry = _store.pop(token, None)
    if entry is None:
        return None
    email, expires_at = entry
    if time.monotonic() > expires_at:
        return None
    return email
