from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from app.config import get_settings
from app.models import AppSettings
from app.schemas import VisionResult
from app.security import decrypt_secret
from app.services.ai_common import build_rules_text, load_default_prompt, render_prompt
from app.services.providers.claude_vision import analyze_claude
from app.services.providers.gemini_vision import analyze_gemini
from app.services.providers.openai_vision import analyze_openai

if TYPE_CHECKING:
    from app.models import Camera, MonitorProfile


def resolve_api_key(settings_row: AppSettings, provider: str) -> Optional[str]:
    env = get_settings()
    if provider == "openai":
        return decrypt_secret(settings_row.openai_api_key_enc) or env.openai_api_key or None
    if provider == "gemini":
        return decrypt_secret(settings_row.gemini_api_key_enc) or env.gemini_api_key or None
    if provider == "claude":
        return decrypt_secret(settings_row.anthropic_api_key_enc) or env.anthropic_api_key or None
    return None


def build_analysis_prompt(
    settings_row: AppSettings,
    *,
    camera: Optional["Camera"] = None,
    profile: Optional["MonitorProfile"] = None,
    db=None,
) -> str:
    if profile and profile.custom_prompt and profile.custom_prompt.strip():
        template = profile.custom_prompt.strip()
    else:
        template = settings_row.base_prompt.strip() or load_default_prompt()

    if profile:
        rule_touca = profile.rule_sem_touca
        rule_farda = profile.rule_fardamento
        rule_epi = profile.rule_sem_epi
        rule_celular = bool(getattr(profile, "rule_celular", False))
        rule_espera = bool(getattr(profile, "rule_tempo_espera", False))
        phone_max = int(getattr(profile, "phone_max_minutes", 5) or 5)
        wait_max = int(getattr(profile, "wait_max_minutes", 10) or 10)
        environment = profile.environment_type or profile.name
        uniform = profile.uniform_expected or "não especificado para este ambiente"
        notes = profile.extra_instructions or "nenhuma"
    else:
        rule_touca = settings_row.rule_sem_touca
        rule_farda = settings_row.rule_fardamento
        rule_epi = settings_row.rule_sem_epi
        rule_celular = False
        rule_espera = False
        phone_max = 5
        wait_max = 10
        environment = "padrão global"
        uniform = "conforme regras globais"
        notes = "câmera sem perfil de ambiente — usando regras globais"

    camera_name = ""
    if camera:
        parts = [camera.name]
        if camera.location:
            parts.append(f"({camera.location})")
        camera_name = " ".join(parts)

    lessons = "nenhuma"
    if db is not None:
        from app.models import Alert

        rows = []
        if camera is not None:
            rows.extend(
                db.query(Alert)
                .filter(
                    Alert.camera_id == camera.id,
                    Alert.feedback == "fp",
                    Alert.feedback_comment.isnot(None),
                )
                .order_by(Alert.id.desc())
                .limit(8)
                .all()
            )
        seen = {a.id for a in rows}
        for a in (
            db.query(Alert)
            .filter(Alert.feedback == "fp", Alert.feedback_comment.isnot(None))
            .order_by(Alert.id.desc())
            .limit(12)
            .all()
        ):
            if a.id not in seen:
                rows.append(a)
                seen.add(a.id)
            if len(rows) >= 12:
                break
        bullets = []
        for a in rows:
            comment = (a.feedback_comment or "").strip()
            if comment:
                bullets.append(f"- {comment}")
        if bullets:
            lessons = "\n".join(bullets)

    rules = build_rules_text(
        rule_touca,
        rule_farda,
        rule_epi,
        rule_celular=rule_celular,
        rule_tempo_espera=rule_espera,
        phone_max_minutes=phone_max,
        wait_max_minutes=wait_max,
    )
    return render_prompt(
        template,
        rules_text=rules,
        environment=environment,
        camera_name=camera_name,
        uniform=uniform,
        notes=notes,
        lessons=lessons,
    )


def analyze_frame(
    settings_row: AppSettings,
    image_jpeg: bytes,
    *,
    camera: Optional["Camera"] = None,
    profile: Optional["MonitorProfile"] = None,
    db=None,
) -> VisionResult:
    provider = (settings_row.active_provider or "openai").lower().strip()
    api_key = resolve_api_key(settings_row, provider)
    if not api_key:
        raise RuntimeError(f"API key não configurada para o provedor '{provider}'")

    prompt = build_analysis_prompt(
        settings_row, camera=camera, profile=profile, db=db
    )

    if provider == "openai":
        return analyze_openai(api_key, settings_row.openai_model, prompt, image_jpeg)
    if provider == "gemini":
        return analyze_gemini(api_key, settings_row.gemini_model, prompt, image_jpeg)
    if provider == "claude":
        return analyze_claude(api_key, settings_row.claude_model, prompt, image_jpeg)
    raise RuntimeError(f"Provedor não suportado: {provider}")
