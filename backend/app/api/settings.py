from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import SettingsOut, SettingsUpdate
from app.permissions import require_roles
from app.security import decrypt_secret, encrypt_secret
from app.services.alert_service import get_or_create_settings
from app.services.ai_router import analyze_frame, resolve_api_key

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Tiny valid JPEG for connectivity tests
_TINY_JPEG = bytes(
    [
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x14, 0x00, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x03, 0xFF, 0xC4, 0x00, 0x14, 0x10, 0x01, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00,
        0x37, 0xFF, 0xD9,
    ]
)


def _key_status(enc_value: Optional[str]) -> bool:
    if not enc_value:
        return False
    return bool(decrypt_secret(enc_value) or enc_value.strip())


def _to_out(row) -> SettingsOut:
    return SettingsOut(
        active_provider=row.active_provider,
        openai_model=row.openai_model,
        gemini_model=row.gemini_model,
        claude_model=row.claude_model,
        analysis_interval_sec=row.analysis_interval_sec,
        cooldown_minutes=row.cooldown_minutes,
        confidence_threshold=row.confidence_threshold,
        respect_store_hours=bool(getattr(row, "respect_store_hours", True)),
        motion_enabled=bool(getattr(row, "motion_enabled", True)),
        motion_check_interval_sec=int(getattr(row, "motion_check_interval_sec", 8) or 8),
        motion_sensitivity=float(getattr(row, "motion_sensitivity", 0.02) or 0.02),
        motion_pixel_threshold=int(getattr(row, "motion_pixel_threshold", 25) or 25),
        motion_cooldown_sec=int(getattr(row, "motion_cooldown_sec", 45) or 45),
        ai_heartbeat_sec=int(getattr(row, "ai_heartbeat_sec", 300) or 0),
        rule_sem_touca=row.rule_sem_touca,
        rule_fardamento=row.rule_fardamento,
        rule_sem_epi=row.rule_sem_epi,
        base_prompt=row.base_prompt,
        openai_api_key_set=_key_status(row.openai_api_key_enc),
        gemini_api_key_set=_key_status(row.gemini_api_key_enc),
        anthropic_api_key_set=_key_status(row.anthropic_api_key_enc),
        updated_at=row.updated_at,
    )


@router.get("", response_model=SettingsOut)
def get_settings_api(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    return _to_out(get_or_create_settings(db))


@router.put("", response_model=SettingsOut)
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    row = get_or_create_settings(db)
    data = payload.model_dump(exclude_unset=True)

    def _store_key(field_name: str, attr: str) -> None:
        if field_name not in data:
            return
        key = data.pop(field_name)
        if key is None:
            return
        key = str(key).strip()
        if not key:
            return
        if set(key) <= {"•", "*"} or key.startswith("••••"):
            return
        setattr(row, attr, encrypt_secret(key))

    _store_key("openai_api_key", "openai_api_key_enc")
    _store_key("gemini_api_key", "gemini_api_key_enc")
    _store_key("anthropic_api_key", "anthropic_api_key_enc")

    for field, value in data.items():
        setattr(row, field, value)

    if row.active_provider not in {"openai", "gemini", "claude"}:
        row.active_provider = "openai"

    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.post("/test-ai")
def test_ai_connection(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    row = get_or_create_settings(db)
    provider = (row.active_provider or "openai").lower()
    key = resolve_api_key(row, provider)
    if not key:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Nenhuma API key salva para o provedor ativo '{provider}'. "
                "Cole a key e clique em Salvar."
            ),
        )
    try:
        result = analyze_frame(row, _TINY_JPEG)
        model = {
            "openai": row.openai_model,
            "gemini": row.gemini_model,
            "claude": row.claude_model,
        }.get(provider)
        return {
            "ok": True,
            "provider": provider,
            "model": model,
            "message": "Conexão com a IA OK",
            "sample": result.model_dump(),
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail=f"Falha ao falar com {provider}: {exc}",
        ) from exc
