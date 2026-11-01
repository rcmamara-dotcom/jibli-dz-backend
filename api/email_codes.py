"""
In-memory store for e-mail verification codes (same approach as reset_tokens).
A 6-digit code per user, valid 15 minutes, max 5 attempts.
shortcut: codes are lost on restart and not shared between workers — the user
just asks for a new one; move to the DB if the API runs several workers.
"""
import secrets
import time

_EXPIRE_SECONDS = 15 * 60
_MAX_ATTEMPTS = 5

# user_id -> (email, code, expires_at, attempts_left)
_store: dict[int, tuple[str, str, float, int]] = {}


def generate(user_id: int, email: str) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    _store[user_id] = (email, code, time.monotonic() + _EXPIRE_SECONDS, _MAX_ATTEMPTS)
    return code


def check(user_id: int, email: str, code: str) -> bool:
    """True if the code matches the user's current e-mail; consumes it on success."""
    entry = _store.get(user_id)
    if entry is None:
        return False
    stored_email, stored_code, expires_at, attempts = entry
    if time.monotonic() > expires_at or attempts <= 0 or stored_email != email:
        _store.pop(user_id, None)
        return False
    if secrets.compare_digest(stored_code, code.strip()):
        _store.pop(user_id, None)
        return True
    _store[user_id] = (stored_email, stored_code, expires_at, attempts - 1)
    return False
