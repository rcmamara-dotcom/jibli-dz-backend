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
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "jibli-dz-aa340")

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
    """Verify a Firebase/Google ID token and return its claims."""
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as grequests
        return id_token.verify_firebase_token(
            id_token_str, grequests.Request(), audience=FIREBASE_PROJECT_ID
        )
    except Exception as e:
        log.warning("Google token verification failed: %s", e)
        raise HTTPException(status_code=401, detail="Token Google invalide")


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
