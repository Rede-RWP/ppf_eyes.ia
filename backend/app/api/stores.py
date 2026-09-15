from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import Store, StoreHour, User
from app.permissions import (
    WEEKDAY_LABELS,
    accessible_store_ids,
    default_hours_payload,
    normalize_cnpj,
    require_roles,
    validate_time,
)
from app.schemas import StoreCreate, StoreOut, StoreUpdate
from app.security import get_current_user

router = APIRouter(prefix="/api/stores", tags=["stores"])


def _hours_out(store: Store) -> list[dict]:
    by_day = {h.weekday: h for h in (store.hours or [])}
    out = []
    for day in range(7):
        h = by_day.get(day)
        default_close = "23:00" if day >= 5 else "22:00"
        if h is None:
            out.append(
                {
                    "weekday": day,
                    "label": WEEKDAY_LABELS[day],
                    "opens_at": "10:00",
                    "closes_at": default_close,
                    "is_closed": False,
                }
            )
            continue
        out.append(
            {
                "weekday": day,
                "label": WEEKDAY_LABELS[day],
                "opens_at": h.opens_at or "10:00",
                "closes_at": h.closes_at or default_close,
                "is_closed": bool(h.is_closed),
            }
        )
    return out


def store_to_out(store: Store) -> StoreOut:
    return StoreOut(
        id=store.id,
        name=store.name,
        cnpj=store.cnpj,
        is_active=store.is_active,
        hours=_hours_out(store),
        cameras_count=len(store.cameras or []),
        created_at=store.created_at,
        updated_at=store.updated_at,
    )


def _apply_hours(db: Session, store: Store, hours: Optional[list]) -> None:
    """Substitui horários da loja. Apaga no DB antes de inserir (evita UNIQUE no MySQL)."""
    payload = hours if hours is not None else default_hours_payload()
    seen = set()
    normalized: list[dict] = []

    for item in payload:
        weekday = int(item["weekday"] if isinstance(item, dict) else item.weekday)
        if weekday in seen or weekday < 0 or weekday > 6:
            continue
        seen.add(weekday)
        if isinstance(item, dict):
            is_closed = bool(item.get("is_closed"))
            opens = validate_time(item.get("opens_at"))
            closes = validate_time(item.get("closes_at"))
        else:
            is_closed = bool(item.is_closed)
            opens = validate_time(item.opens_at)
            closes = validate_time(item.closes_at)
        if is_closed:
            opens = closes = None
        normalized.append(
            {
                "weekday": weekday,
                "opens_at": opens,
                "closes_at": closes,
                "is_closed": is_closed,
            }
        )

    for day in range(7):
        if day not in seen:
            normalized.append(
                {
                    "weekday": day,
                    "opens_at": None,
                    "closes_at": None,
                    "is_closed": True,
                }
            )

    if store.id is not None:
        db.query(StoreHour).filter(StoreHour.store_id == store.id).delete(
            synchronize_session=False
        )
        db.flush()

    store.hours.clear()
    for row in sorted(normalized, key=lambda x: x["weekday"]):
        store.hours.append(
            StoreHour(
                weekday=row["weekday"],
                opens_at=row["opens_at"],
                closes_at=row["closes_at"],
                is_closed=row["is_closed"],
            )
        )


@router.get("", response_model=List[StoreOut])
def list_stores(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = (
        db.query(Store)
        .options(joinedload(Store.hours), joinedload(Store.cameras))
        .order_by(Store.name.asc())
    )
    ids = accessible_store_ids(db, user)
    if ids is not None:
        if not ids:
            return []
        q = q.filter(Store.id.in_(ids))
    return [store_to_out(s) for s in q.all()]


@router.post("", response_model=StoreOut)
def create_store(
    payload: StoreCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    store = Store(
        name=payload.name.strip(),
        cnpj=normalize_cnpj(payload.cnpj),
        is_active=payload.is_active,
    )
    hours_data = (
        [h.model_dump() for h in payload.hours] if payload.hours is not None else None
    )
    db.add(store)
    db.flush()
    _apply_hours(db, store, hours_data)
    db.commit()
    store = (
        db.query(Store)
        .options(joinedload(Store.hours), joinedload(Store.cameras))
        .filter(Store.id == store.id)
        .first()
    )
    return store_to_out(store)


@router.get("/{store_id}", response_model=StoreOut)
def get_store(
    store_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    store = (
        db.query(Store)
        .options(joinedload(Store.hours), joinedload(Store.cameras))
        .filter(Store.id == store_id)
        .first()
    )
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    ids = accessible_store_ids(db, user)
    if ids is not None and store.id not in ids:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    return store_to_out(store)


@router.put("/{store_id}", response_model=StoreOut)
def update_store(
    store_id: int,
    payload: StoreUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    store = (
        db.query(Store)
        .options(joinedload(Store.hours), joinedload(Store.cameras))
        .filter(Store.id == store_id)
        .first()
    )
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        store.name = data["name"].strip()
    if "cnpj" in data:
        store.cnpj = normalize_cnpj(data["cnpj"])
    if "is_active" in data and data["is_active"] is not None:
        store.is_active = data["is_active"]
    if "hours" in data:
        hours_data = data["hours"]
        _apply_hours(db, store, hours_data)
    store.updated_at = datetime.utcnow()
    db.commit()
    store = (
        db.query(Store)
        .options(joinedload(Store.hours), joinedload(Store.cameras))
        .filter(Store.id == store_id)
        .first()
    )
    return store_to_out(store)


@router.delete("/{store_id}")
def delete_store(
    store_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    store = (
        db.query(Store)
        .options(joinedload(Store.cameras))
        .filter(Store.id == store_id)
        .first()
    )
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    if store.cameras:
        raise HTTPException(
            status_code=400,
            detail="Remova ou mova as câmeras desta loja antes de excluir",
        )
    db.delete(store)
    db.commit()
    return {"ok": True}
