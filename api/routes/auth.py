import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Request, status
from godata.repos import UserRepo
from ..schemas import (
    RegisterIn, LoginIn, TokenOut, ForgotPasswordIn, ResetPasswordIn,
    GoogleAuthIn, MeOut, ChangePasswordIn, UpdateMeIn, VerifyEmailIn, ChangeEmailIn,
)
from ..auth import (
    hash_password, verify_password, create_token, verify_google_token,
    require_user,
)
from ..reset_tokens import generate as gen_reset_token, consume as consume_reset_token
from .. import email_codes
from ..scheduler import _send
from ..limiter import limiter
from godata.models import User

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _send_verification_code(user: User) -> None:
    code = email_codes.generate(user.id, user.email)
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:24px">
      <div style="background:#0f5c32;border-radius:12px;padding:20px 24px;color:white;margin-bottom:24px">
        <strong style="font-size:20px">📦 JIBLI DZ</strong>
      </div>
      <h2 style="color:#111827">✉️ Confirme ton adresse e-mail</h2>
      <p style="color:#6b7280;line-height:1.6">Voici ton code de vérification, valable <strong>15 minutes</strong> :</p>
      <p style="font-size:32px;font-weight:700;letter-spacing:8px;color:#0f5c32;margin:20px 0">{code}</p>
      <p style="color:#6b7280;font-size:12px">Si tu n'as pas créé de compte JIBLI DZ, ignore cet e-mail.</p>
    </div>
    """
    _send(user.email, f"{code} — ton code de vérification JIBLI DZ", html)
    if not os.environ.get("SMTP_HOST"):
        log.info("SMTP non configuré — code de vérification pour %s : %s", user.email, code)


def _me(user: User) -> MeOut:
    out = MeOut.model_validate(user)
    out.has_password = bool(user.password_hash)
    return out


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn) -> TokenOut:
    log.debug("POST /api/auth/register — email=%s", body.email)
    if body.password != body.confirm_password:
        raise HTTPException(status_code=422, detail="Les mots de passe ne correspondent pas")
    if len(body.password) < 6:
        raise HTTPException(status_code=422, detail="Le mot de passe doit faire au moins 6 caractères")
    try:
        existing = UserRepo.get_by_email(body.email)
        if existing:
            raise HTTPException(status_code=400, detail="Cet e-mail est déjà utilisé")
        user = UserRepo.create(
            body.email,
            hash_password(body.password),
            name=body.name,
            birth_date=body.birth_date,
            phone=body.phone,
        )
        log.debug("User created: id=%s email=%s", user.id, user.email)
        _send_verification_code(user)
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
        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="E-mail ou mot de passe incorrect")
        log.debug("Login OK: id=%s", user.id)
        return TokenOut(access_token=create_token(user))
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Erreur inattendue dans /login: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/google", response_model=TokenOut)
def google_auth(body: GoogleAuthIn) -> TokenOut:
    """Sign in or register via Google / Firebase ID token."""
    claims = verify_google_token(body.id_token)
    google_id = claims.get("uid") or claims.get("sub", "")
    email = claims.get("email", "")
    name = claims.get("name")
    if not google_id or not email:
        raise HTTPException(status_code=400, detail="Token Google incomplet")
    user = UserRepo.get_or_create_by_google(google_id=google_id, email=email, name=name)
    log.info("Google auth OK: user_id=%s email=%s", user.id, user.email)
    return TokenOut(access_token=create_token(user))


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(require_user)) -> MeOut:
    return _me(user)


@router.patch("/me", response_model=MeOut)
def update_me(body: UpdateMeIn, user: User = Depends(require_user)) -> MeOut:
    UserRepo.update_profile(user.id, **body.model_dump(include=body.model_fields_set))
    return _me(UserRepo.get_by_id(user.id))


@router.post("/verify-email", response_model=MeOut)
@limiter.limit("10/hour")
def verify_email(request: Request, body: VerifyEmailIn, user: User = Depends(require_user)) -> MeOut:
    if not user.email_verified:
        if not email_codes.check(user.id, user.email, body.code):
            raise HTTPException(status_code=400, detail="Code invalide ou expiré")
        UserRepo.set_email_verified(user.id)
        log.info("E-mail vérifié pour user_id=%s", user.id)
    return _me(UserRepo.get_by_id(user.id))


@router.post("/resend-code", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/hour")
def resend_code(request: Request, user: User = Depends(require_user)) -> None:
    if not user.email_verified:
        _send_verification_code(user)


@router.post("/change-email", response_model=MeOut)
@limiter.limit("5/hour")
def change_email(request: Request, body: ChangeEmailIn, user: User = Depends(require_user)) -> MeOut:
    if not user.password_hash:
        raise HTTPException(status_code=400, detail="Compte Google : l'e-mail est géré par Google")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mot de passe incorrect")
    if body.new_email == user.email:
        return _me(user)
    if UserRepo.get_by_email(body.new_email):
        raise HTTPException(status_code=400, detail="Cet e-mail est déjà utilisé")
    UserRepo.update_email(user.id, body.new_email)
    updated = UserRepo.get_by_id(user.id)
    _send_verification_code(updated)
    log.info("E-mail changé pour user_id=%s", user.id)
    return _me(updated)


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/hour")
def forgot_password(request: Request, body: ForgotPasswordIn) -> None:
    user = UserRepo.get_by_email(body.email)
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


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: ChangePasswordIn, user: User = Depends(require_user)) -> None:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    if body.new_password != body.confirm_new_password:
        raise HTTPException(status_code=422, detail="Les mots de passe ne correspondent pas")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=422, detail="Le mot de passe doit faire au moins 6 caractères")
    UserRepo.update_password(user.id, hash_password(body.new_password))
    log.info("Mot de passe changé pour user_id=%s", user.id)


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
