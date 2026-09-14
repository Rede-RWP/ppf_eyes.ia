from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import TokenOut, UserOut
from app.security import (
    _client_ip,
    cookie_settings,
    create_session_token,
    get_current_user,
    is_locked_out,
    record_login_attempt,
    revoke_all_user_sessions,
    revoke_session,
    too_many_requests,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    ip = _client_ip(request)
    username = (form_data.username or "").strip()

    if too_many_requests(db, ip=ip):
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas. Aguarde um minuto e tente novamente.",
        )
    if is_locked_out(db, username=username, ip=ip):
        raise HTTPException(
            status_code=429,
            detail="Conta temporariamente bloqueada por tentativas inválidas. Tente mais tarde.",
        )

    user = db.query(User).filter(User.username == username).first()
    valid = bool(
        user
        and getattr(user, "is_active", True)
        and verify_password(form_data.password, user.password_hash)
    )
    if not valid:
        record_login_attempt(db, username=username, ip=ip, success=False)
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")

    record_login_attempt(db, username=username, ip=ip, success=True)
    token, _session = create_session_token(db, user, request)

    ck = cookie_settings()
    response.set_cookie(
        value=token,
        **ck,
    )
    return TokenOut(access_token=token)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    jti = getattr(request.state, "auth_jti", None)
    if jti:
        revoke_session(db, jti)
    response.delete_cookie(
        key=cookie_settings()["key"],
        path="/",
    )
    return {"ok": True, "username": user.username}


@router.post("/logout-all")
def logout_all(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    revoke_all_user_sessions(db, user.id)
    response.delete_cookie(
        key=cookie_settings()["key"],
        path="/",
    )
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
