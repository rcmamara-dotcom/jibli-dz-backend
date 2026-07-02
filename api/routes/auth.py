from fastapi import APIRouter, HTTPException, status
from godata.repos import UserRepo
from ..schemas import RegisterIn, LoginIn, TokenOut
from ..auth import hash_password, verify_password, create_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn) -> TokenOut:
    if UserRepo.get_by_email(body.email):
        raise HTTPException(status_code=400, detail="Cet e-mail est déjà utilisé")
    user = UserRepo.create(body.email, hash_password(body.password))
    return TokenOut(access_token=create_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn) -> TokenOut:
    user = UserRepo.get_by_email(body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-mail ou mot de passe incorrect")
    return TokenOut(access_token=create_token(user.id))
