import os
import logging
import bcrypt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from godata.repos import UserRepo
from godata.models import User

log = logging.getLogger(__name__)

SECRET = os.environ["JWT_SECRET"]
ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", 10080))
FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY", "AIzaSyDZP0PmPpIKA9efDEg8t0qYMzGMZDixuGc")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MINUTES)
    return jwt.encode(
        {
            "sub": str(user.id),
            "adm": bool(user.is_admin),
            "email": user.email,
            "name": getattr(user, "name", None),
            "exp": exp,
        },
        SECRET,
        algorithm=ALGORITHM,
    )


def verify_google_token(id_token_str: str) -> dict:
    """Verify a Firebase ID token via the Firebase REST API."""
    import urllib.request
    import json as _json

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FIREBASE_API_KEY}"
    payload = _json.dumps({"idToken": id_token_str}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read())
    except Exception as e:
        log.warning("Firebase token lookup failed: %s", e)
        raise HTTPException(status_code=401, detail="Token Google invalide")

    users = data.get("users", [])
    if not users:
        raise HTTPException(status_code=401, detail="Token Google invalide")
    u = users[0]
    return {
        "uid": u.get("localId", ""),
        "email": u.get("email", ""),
        "name": u.get("displayName"),
    }


def get_current_user(token: str | None = Depends(oauth2_scheme)) -> User | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
        return UserRepo.get_by_id(user_id)
    except (JWTError, KeyError, ValueError):
        return None


def require_user(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Non authentifié")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé aux administrateurs")
    return user
