"""Système de droits : chaque rôle donne un ensemble de permissions."""
from fastapi import Depends, HTTPException, status
from godata.models import User
from .auth import require_user

# vip : publie gratuitement (partenaires, proches) sans accès à l'admin
PERMISSIONS: dict[str, frozenset[str]] = {
    "user": frozenset(),
    "vip": frozenset({"publish_free"}),
    "moderator": frozenset({"publish_free", "moderate"}),
    "admin": frozenset({"publish_free", "moderate", "manage_users"}),
}


def can(user: User, permission: str) -> bool:
    return permission in PERMISSIONS.get(user.role, frozenset())


def require(permission: str):
    """Dépendance FastAPI : 403 si l'utilisateur n'a pas la permission."""
    def dependency(user: User = Depends(require_user)) -> User:
        if not can(user, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")
        return user
    return dependency
