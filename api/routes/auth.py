import logging
from fastapi import APIRouter, HTTPException, Request, status
from godata.repos import UserRepo
from ..schemas import RegisterIn, LoginIn, TokenOut, ForgotPasswordIn, ResetPasswordIn
from ..auth import hash_password, verify_password, create_token
from ..reset_tokens import generate as gen_reset_token, consume as consume_reset_token
from ..scheduler import _send
from ..limiter import limiter

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


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/hour")
def forgot_password(request: Request, body: ForgotPasswordIn) -> None:
    user = UserRepo.get_by_email(body.email)
    # Always return 204 to avoid email enumeration
    if not user:
        return
    token = gen_reset_token(body.email)
    import os
    base = os.environ.get("PUBLIC_URL", "http://localhost:5173")
    reset_link = f"{base}/?reset={token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:24px">
      <div style="background:#0f5c32;border-radius:12px;padding:20px 24px;color:white;margin-bottom:24px">
        <strong style="font-size:20px">📦 JIBLI DZ</strong>
      </div>
      <h2 style="color:#111827">🔑 Réinitialisation de mot de passe</h2>
      <p style="color:#6b7280;line-height:1.6">
        Tu as demandé à réinitialiser ton mot de passe. Clique sur le bouton ci-dessous.
        Ce lien est valable <strong>15 minutes</strong>.
      </p>
      <a href="{reset_link}" style="display:inline-block;margin:20px 0;padding:14px 28px;background:#0f5c32;color:white;border-radius:8px;text-decoration:none;font-weight:700">
        Réinitialiser mon mot de passe
      </a>
      <p style="color:#6b7280;font-size:12px">
        Si tu n'as pas demandé cette réinitialisation, ignore cet e-mail.
      </p>
      <p style="color:#6b7280;font-size:13px;margin-top:32px">
        JIBLI DZ · France ⇄ Algérie
      </p>
    </div>
    """
    _send(body.email, "🔑 Réinitialisation de ton mot de passe JIBLI DZ", html)
    log.info("Reset token généré pour %s", body.email)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(body: ResetPasswordIn) -> None:
    email = consume_reset_token(body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Lien invalide ou expiré")
    user = UserRepo.get_by_email(email)
    if not user:
        raise HTTPException(status_code=400, detail="Utilisateur introuvable")
    if len(body.password) < 6:
        raise HTTPException(status_code=422, detail="Le mot de passe doit faire au moins 6 caractères")
    UserRepo.update_password(user.id, hash_password(body.password))
    log.info("Mot de passe mis à jour pour user_id=%s", user.id)
