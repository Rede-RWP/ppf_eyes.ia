from __future__ import annotations

from typing import List, Set

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import Store, StoreUser, User
from app.permissions import (
    ALL_ROLES,
    ROLE_ADMIN,
    ROLE_GESTOR,
    ROLE_OPERADOR,
    accessible_store_ids,
    is_admin,
    require_roles,
    user_role,
)
from app.schemas import UserAdminOut, UserCreate, UserUpdate
from app.security import hash_password, revoke_all_user_sessions

router = APIRouter(prefix="/api/users", tags=["users"])


def _user_out(user: User) -> UserAdminOut:
    links = user.store_links or []
    store_ids = [link.store_id for link in links]
    store_names = [
        link.store.name for link in links if getattr(link, "store", None) is not None
    ]
    return UserAdminOut(
        id=user.id,
        username=user.username,
        role=user_role(user),
        display_name=user.display_name,
        store_ids=store_ids,
        store_names=store_names,
        is_active=bool(user.is_active),
        created_at=user.created_at,
    )


def _validate_role(role: str, actor: User) -> str:
    role = (role or "").strip().lower()
    if role not in ALL_ROLES:
        raise HTTPException(status_code=400, detail="Role inválida")
    if not is_admin(actor) and role == ROLE_ADMIN:
        raise HTTPException(
            status_code=403, detail="Somente admin pode criar outro admin"
        )
    if not is_admin(actor) and role not in {ROLE_GESTOR, ROLE_OPERADOR}:
        raise HTTPException(status_code=403, detail="Role não permitida")
    return role


def _normalize_store_ids(db: Session, actor: User, store_ids: List[int]) -> List[int]:
    unique = sorted({int(x) for x in store_ids if x is not None})
    if not unique:
        return []
    existing = {
        s.id
        for s in db.query(Store).filter(Store.id.in_(unique), Store.is_active.is_(True)).all()
    }
    missing = set(unique) - existing
    if missing:
        raise HTTPException(status_code=400, detail=f"Lojas inválidas: {sorted(missing)}")
    allowed = accessible_store_ids(db, actor)
    if allowed is not None:
        forbidden = set(unique) - allowed
        if forbidden:
            raise HTTPException(
                status_code=403,
                detail="Você só pode vincular lojas às quais tem acesso",
            )
    return unique


def _set_stores(db: Session, user: User, store_ids: List[int]) -> None:
    user.store_links.clear()
    db.flush()
    for sid in store_ids:
        user.store_links.append(StoreUser(store_id=sid))


@router.get("", response_model=List[UserAdminOut])
def list_users(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin", "gestor")),
):
    users = (
        db.query(User)
        .options(joinedload(User.store_links).joinedload(StoreUser.store))
        .order_by(User.username.asc())
        .all()
    )
    if is_admin(actor):
        return [_user_out(u) for u in users]

    # Gestor: vê a si mesmo + usuários que compartilham ao menos uma loja
    my_stores = accessible_store_ids(db, actor) or set()
    out = []
    for u in users:
        if u.id == actor.id:
            out.append(_user_out(u))
            continue
        if user_role(u) == ROLE_ADMIN:
            continue
        their = {link.store_id for link in (u.store_links or [])}
        if their & my_stores:
            out.append(_user_out(u))
    return out


@router.post("", response_model=UserAdminOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin", "gestor")),
):
    username = payload.username.strip().lower()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Usuário já existe")
    role = _validate_role(payload.role, actor)
    store_ids = _normalize_store_ids(db, actor, payload.store_ids)
    if role != ROLE_ADMIN and not store_ids:
        raise HTTPException(
            status_code=400,
            detail="Gestor e operador precisam de ao menos uma loja",
        )
    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        role=role,
        display_name=(payload.display_name or "").strip() or None,
        is_active=payload.is_active,
    )
    db.add(user)
    db.flush()
    _set_stores(db, user, store_ids)
    db.commit()
    user = (
        db.query(User)
        .options(joinedload(User.store_links).joinedload(StoreUser.store))
        .filter(User.id == user.id)
        .first()
    )
    return _user_out(user)


@router.put("/{user_id}", response_model=UserAdminOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin", "gestor")),
):
    user = (
        db.query(User)
        .options(joinedload(User.store_links).joinedload(StoreUser.store))
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if not is_admin(actor):
        my_stores: Set[int] = accessible_store_ids(db, actor) or set()
        their = {link.store_id for link in (user.store_links or [])}
        if user.id != actor.id and not (their & my_stores):
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        if user_role(user) == ROLE_ADMIN:
            raise HTTPException(status_code=403, detail="Não é possível editar admin")

    data = payload.model_dump(exclude_unset=True)
    if "role" in data and data["role"] is not None:
        user.role = _validate_role(data["role"], actor)
    if "display_name" in data:
        user.display_name = (data["display_name"] or "").strip() or None
    if "is_active" in data and data["is_active"] is not None:
        if user.id == actor.id and not data["is_active"]:
            raise HTTPException(status_code=400, detail="Não desative a si mesmo")
        user.is_active = data["is_active"]
    if "password" in data and data["password"]:
        user.password_hash = hash_password(data["password"])
        revoke_all_user_sessions(db, user.id)
    if "store_ids" in data and data["store_ids"] is not None:
        store_ids = _normalize_store_ids(db, actor, data["store_ids"])
        if user_role(user) != ROLE_ADMIN and not store_ids:
            raise HTTPException(
                status_code=400,
                detail="Gestor e operador precisam de ao menos uma loja",
            )
        _set_stores(db, user, store_ids)

    db.commit()
    user = (
        db.query(User)
        .options(joinedload(User.store_links).joinedload(StoreUser.store))
        .filter(User.id == user_id)
        .first()
    )
    return _user_out(user)


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if user.id == actor.id:
        raise HTTPException(status_code=400, detail="Não exclua a si mesmo")
    revoke_all_user_sessions(db, user.id)
    db.delete(user)
    db.commit()
    return {"ok": True}
