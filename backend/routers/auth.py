from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User, Session as DbSession
from backend.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserMeResponse
from backend.services.auth import (
    create_jwt_token,
    decode_jwt_token,
    hash_password,
    verify_password,
)


router = APIRouter()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _get_current_user(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token nao fornecido")

    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_jwt_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token invalido ou expirado")

    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario nao encontrado")

    return user


@router.post("/api/auth/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = _normalize_email(payload.email)

    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Email invalido")

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email ja cadastrado")

    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_jwt_token(user.id, user.email)
    return AuthResponse(token=token, email=user.email, user_id=user.id)


@router.post("/api/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = _normalize_email(payload.email)

    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou senha incorretos")

    token = create_jwt_token(user.id, user.email)
    return AuthResponse(token=token, email=user.email, user_id=user.id)


@router.post("/api/auth/logout")
def logout(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token nao fornecido")

    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_jwt_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token invalido ou expirado")

    return {"message": "Logout realizado com sucesso"}


@router.get("/api/auth/me", response_model=UserMeResponse)
def me(current_user: User = Depends(_get_current_user)) -> UserMeResponse:
    return UserMeResponse(email=current_user.email, user_id=current_user.id)