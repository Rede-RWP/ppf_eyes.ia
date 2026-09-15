from __future__ import annotations

from typing import Optional, Set

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Camera, StoreUser, User
from app.security import get_current_user

ROLE_ADMIN = "admin"
ROLE_GESTOR = "gestor"
ROLE_OPERADOR = "operador"
ALL_ROLES = {ROLE_ADMIN, ROLE_GESTOR, ROLE_OPERADOR}

WEEKDAY_LABELS = [
    "Segunda",
    "Terça",
    "Quarta",
    "Quinta",
    "Sexta",
    "Sábado",
    "Domingo",
]


def user_role(user: User) -> str:
    role = (getattr(user, "role", None) or ROLE_ADMIN).strip().lower()
    return role if role in ALL_ROLES else ROLE_ADMIN


def is_admin(user: User) -> bool:
    return user_role(user) == ROLE_ADMIN


def is_gestor(user: User) -> bool:
    return user_role(user) == ROLE_GESTOR


def is_operador(user: User) -> bool:
    return user_role(user) == ROLE_OPERADOR


def require_roles(*roles: str):
    allowed = {r.lower() for r in roles}

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user_role(user) not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sem permissão para esta ação",
            )
        return user

    return _dep


def accessible_store_ids(db: Session, user: User) -> Optional[Set[int]]:
    """None = todas as lojas (admin). Set vazio = nenhuma."""
    if is_admin(user):
        return None
    rows = (
        db.query(StoreUser.store_id).filter(StoreUser.user_id == user.id).all()
    )
    return {r[0] for r in rows}


def can_access_store(db: Session, user: User, store_id: Optional[int]) -> bool:
    if store_id is None:
        return is_admin(user)
    ids = accessible_store_ids(db, user)
    if ids is None:
        return True
    return store_id in ids


def can_access_camera(db: Session, user: User, camera: Camera) -> bool:
    return can_access_store(db, user, camera.store_id)


def assert_camera_access(db: Session, user: User, camera: Camera) -> None:
    if not can_access_camera(db, user, camera):
        raise HTTPException(status_code=404, detail="Câmera não encontrada")


def filter_cameras_for_user(query, db: Session, user: User):
    ids = accessible_store_ids(db, user)
    if ids is None:
        return query
    if not ids:
        return query.filter(Camera.id == -1)
    return query.filter(Camera.store_id.in_(ids))


def normalize_cnpj(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return None
    if len(digits) != 14:
        raise HTTPException(status_code=400, detail="CNPJ deve ter 14 dígitos")
    return (
        f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    )


def validate_time(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    parts = value.strip().split(":")
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail=f"Horário inválido: {value}")
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Horário inválido: {value}") from exc
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise HTTPException(status_code=400, detail=f"Horário inválido: {value}")
    return f"{h:02d}:{m:02d}"


def default_hours_payload() -> list[dict]:
    hours = []
    for day in range(7):
        closed = False
        opens, closes = "10:00", "22:00"
        if day >= 5:
            closes = "23:00"
        hours.append(
            {
                "weekday": day,
                "opens_at": opens,
                "closes_at": closes,
                "is_closed": closed,
            }
        )
    return hours
