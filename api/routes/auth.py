import logging
from fastapi import APIRouter, HTTPException, status
from godata.repos import UserRepo
from ..schemas import RegisterIn, LoginIn, TokenOut
from ..auth import hash_password, verify_password, create_token

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn) -> TokenOut:
    log.debug("POST /api/auth/register — email=%s", body.email)
    try:
        existing = UserRepo.get_by_email(body.email)
        log.debug("get_by_email result: %s", existing)
        if existing:
            log.debug("Email already used: %s", body.email)
            raise HTTPException(status_code=400, detail="Cet e-mail est déjà utilisé")
        user = UserRepo.create(body.email, hash_password(body.password))
        log.debug("User created: id=%s email=%s", user.id, user.email)
        return TokenOut(access_token=create_token(user))
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Erreur inattendue dans /register: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn) -> TokenOut:
    log.debug("POST /api/auth/login — email=%s", body.email)
    try:
        user = UserRepo.get_by_email(body.email)
        log.debug("get_by_email result: %s", user)
        if not user or not verify_password(body.password, user.password_hash):
            log.debug("Auth failed for email=%s", body.email)
            raise HTTPException(status_code=401, detail="E-mail ou mot de passe incorrect")
        log.debug("Login OK: id=%s", user.id)
        return TokenOut(access_token=create_token(user))
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Erreur inattendue dans /login: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
