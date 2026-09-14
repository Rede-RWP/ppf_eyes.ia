from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import AuthSession, LoginAttempt, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if request.client and request.client.host:
        return request.client.host[:64]
    return "unknown"


def _user_agent(request: Request) -> str:
    return (request.headers.get("user-agent") or "")[:255]


def is_locked_out(db: Session, *, username: str, ip: str) -> bool:
    settings = get_settings()
    since = datetime.utcnow() - timedelta(minutes=settings.auth_lockout_minutes)
    fails = (
        db.query(LoginAttempt)
        .filter(
            LoginAttempt.username == username,
            LoginAttempt.ip_address == ip,
            LoginAttempt.success.is_(False),
            LoginAttempt.created_at >= since,
        )
        .count()
    )
    return fails >= settings.auth_max_failed_attempts


def too_many_requests(db: Session, *, ip: str) -> bool:
    settings = get_settings()
    since = datetime.utcnow() - timedelta(seconds=settings.auth_rate_limit_window_sec)
    count = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.ip_address == ip, LoginAttempt.created_at >= since)
        .count()
    )
    return count >= settings.auth_rate_limit_max


def record_login_attempt(
    db: Session, *, username: str, ip: str, success: bool
) -> None:
    db.add(
        LoginAttempt(
            username=(username or "")[:80],
            ip_address=ip,
            success=success,
        )
    )
    db.commit()


def create_session_token(
    db: Session,
    user: User,
    request: Request,
) -> tuple[str, AuthSession]:
    settings = get_settings()
    jti = uuid.uuid4().hex
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    session = AuthSession(
        user_id=user.id,
        jti=jti,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
        expires_at=expire,
        last_seen_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    payload = {
        "sub": user.username,
        "uid": user.id,
        "jti": jti,
        "exp": expire,
        "iat": datetime.utcnow(),
        "typ": "access",
    }
    token = jwt.encode(payload, settings.app_secret_key, algorithm=ALGORITHM)
    return token, session


def revoke_session(db: Session, jti: str) -> None:
    row = db.query(AuthSession).filter(AuthSession.jti == jti).first()
    if row and not row.revoked_at:
        row.revoked_at = datetime.utcnow()
        db.commit()


def revoke_all_user_sessions(db: Session, user_id: int) -> None:
    now = datetime.utcnow()
    rows = (
        db.query(AuthSession)
        .filter(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .all()
    )
    for row in rows:
        row.revoked_at = now
    db.commit()


def _extract_token(request: Request, bearer: Optional[str]) -> Optional[str]:
    if bearer:
        return bearer
    settings = get_settings()
    cookie = request.cookies.get(settings.auth_cookie_name)
    return cookie or None


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autenticado",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    raw = _extract_token(request, token)
    if not raw:
        raise _credentials_exception()

    settings = get_settings()
    try:
        payload = jwt.decode(raw, settings.app_secret_key, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        jti: Optional[str] = payload.get("jti")
        if not username or not jti:
            raise _credentials_exception()
    except JWTError as exc:
        raise _credentials_exception() from exc

    session = db.query(AuthSession).filter(AuthSession.jti == jti).first()
    if not session or session.revoked_at is not None:
        raise _credentials_exception()
    if session.expires_at < datetime.utcnow():
        if not session.revoked_at:
            session.revoked_at = datetime.utcnow()
            db.commit()
        raise _credentials_exception()

    user = db.query(User).filter(User.username == username).first()
    if not user or not getattr(user, "is_active", True):
        raise _credentials_exception()

    session.last_seen_at = datetime.utcnow()
    db.commit()
    request.state.auth_jti = jti
    return user


def get_optional_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    try:
        return get_current_user(request, token, db)
    except HTTPException:
        return None


def cookie_settings() -> dict:
    settings = get_settings()
    samesite = (settings.auth_cookie_samesite or "lax").lower()
    if samesite not in {"lax", "strict", "none"}:
        samesite = "lax"
    return {
        "key": settings.auth_cookie_name,
        "httponly": True,
        "secure": bool(settings.auth_cookie_secure) or samesite == "none",
        "samesite": samesite,
        "path": "/",
        "max_age": settings.access_token_expire_minutes * 60,
    }


def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.encryption_key.strip()
    if not key:
        digest = hashlib.sha256(settings.app_secret_key.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest).decode("ascii")
    elif len(key) != 44:
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest).decode("ascii")
    return Fernet(key.encode("ascii"))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return None


def mask_rtsp(url: str) -> str:
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest:
        return url
    creds, hostpart = rest.rsplit("@", 1)
    if ":" in creds:
        user, _pwd = creds.split(":", 1)
        return f"{scheme}://{user}:***@{hostpart}"
    return f"{scheme}://***@{hostpart}"


def generate_secret_key() -> str:
    return secrets.token_urlsafe(48)
