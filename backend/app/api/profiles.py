from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Camera, MonitorProfile, User
from app.schemas import ProfileCreate, ProfileOut, ProfileUpdate
from app.permissions import require_roles
from app.services.ai_common import slugify
from app.services.profiles_seed import ensure_default_profiles

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _to_out(profile: MonitorProfile, cameras_count: int = 0) -> ProfileOut:
    return ProfileOut(
        id=profile.id,
        name=profile.name,
        slug=profile.slug,
        description=profile.description,
        environment_type=profile.environment_type,
        rule_sem_touca=profile.rule_sem_touca,
        rule_fardamento=profile.rule_fardamento,
        rule_sem_epi=profile.rule_sem_epi,
        rule_celular=bool(getattr(profile, "rule_celular", False)),
        phone_max_minutes=int(getattr(profile, "phone_max_minutes", 5) or 5),
        rule_tempo_espera=bool(getattr(profile, "rule_tempo_espera", False)),
        wait_max_minutes=int(getattr(profile, "wait_max_minutes", 10) or 10),
        uniform_expected=profile.uniform_expected,
        extra_instructions=profile.extra_instructions,
        custom_prompt=profile.custom_prompt,
        is_default=profile.is_default,
        cameras_count=cameras_count,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("", response_model=List[ProfileOut])
def list_profiles(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "gestor")),
):
    ensure_default_profiles(db)
    profiles = db.query(MonitorProfile).order_by(MonitorProfile.name.asc()).all()
    out = []
    for p in profiles:
        count = db.query(Camera).filter(Camera.profile_id == p.id).count()
        out.append(_to_out(p, count))
    return out


@router.post("", response_model=ProfileOut)
def create_profile(
    payload: ProfileCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    ensure_default_profiles(db)
    slug = slugify(payload.name)
    if db.query(MonitorProfile).filter(MonitorProfile.slug == slug).first():
        raise HTTPException(status_code=400, detail="Já existe um perfil com esse nome")
    if payload.is_default:
        db.query(MonitorProfile).update({MonitorProfile.is_default: False})
    profile = MonitorProfile(
        name=payload.name.strip(),
        slug=slug,
        environment_type=(payload.environment_type or "geral").strip(),
        description=(payload.description or "").strip() or None,
        rule_sem_touca=payload.rule_sem_touca,
        rule_fardamento=payload.rule_fardamento,
        rule_sem_epi=payload.rule_sem_epi,
        rule_celular=payload.rule_celular,
        phone_max_minutes=payload.phone_max_minutes,
        rule_tempo_espera=payload.rule_tempo_espera,
        wait_max_minutes=payload.wait_max_minutes,
        uniform_expected=(payload.uniform_expected or "").strip() or None,
        extra_instructions=(payload.extra_instructions or "").strip() or None,
        custom_prompt=(payload.custom_prompt or "").strip() or None,
        is_default=payload.is_default,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _to_out(profile, 0)


@router.put("/{profile_id}", response_model=ProfileOut)
def update_profile(
    profile_id: int,
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    profile = db.query(MonitorProfile).filter(MonitorProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil não encontrado")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        new_slug = slugify(data["name"])
        clash = (
            db.query(MonitorProfile)
            .filter(MonitorProfile.slug == new_slug, MonitorProfile.id != profile_id)
            .first()
        )
        if clash:
            raise HTTPException(status_code=400, detail="Já existe um perfil com esse nome")
        profile.name = data.pop("name").strip()
        profile.slug = new_slug
    if data.get("is_default"):
        db.query(MonitorProfile).update({MonitorProfile.is_default: False})
    for field, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    count = db.query(Camera).filter(Camera.profile_id == profile.id).count()
    return _to_out(profile, count)


@router.delete("/{profile_id}")
def delete_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    profile = db.query(MonitorProfile).filter(MonitorProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil não encontrado")
    linked = db.query(Camera).filter(Camera.profile_id == profile_id).count()
    if linked:
        raise HTTPException(
            status_code=400,
            detail=f"Há {linked} câmera(s) usando este perfil. Troque o perfil delas antes.",
        )
    db.delete(profile)
    db.commit()
    return {"ok": True}
