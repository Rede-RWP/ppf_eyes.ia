from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Alert,
    Camera,
    FrameObservation,
    MonitorProfile,
    PresenceSession,
    ReportChatMessage,
)
from app.schemas import ParameterItem
from app.services.ai_router import resolve_api_key
from app.services.alert_service import get_or_create_settings


PARAMETERS_CATALOG: List[ParameterItem] = [
    ParameterItem(
        key="rule_sem_touca",
        label="Detectar sem touca",
        description="Alerta quando há cabelo visível sem proteção.",
        where="Ambientes (perfil da câmera)",
        default="ligado em Cozinha",
    ),
    ParameterItem(
        key="rule_fardamento",
        label="Detectar fardamento inadequado",
        description="Compara com o texto de uniforme esperado do perfil.",
        where="Ambientes",
        default="ligado em Cozinha/Recepção/Salão",
    ),
    ParameterItem(
        key="rule_sem_epi",
        label="Detectar sem EPI",
        description="Capacete, luvas etc. quando exigido.",
        where="Ambientes",
        default="desligado",
    ),
    ParameterItem(
        key="rule_celular",
        label="Detectar uso de celular",
        description="Marca uso de celular no frame; alerta após tempo contínuo.",
        where="Ambientes",
        default="desligado (ative por perfil)",
    ),
    ParameterItem(
        key="phone_max_minutes",
        label="Limite de celular (minutos)",
        description="Tempo contínuo no celular para gerar alerta celular_excessivo.",
        where="Ambientes",
        default="5",
    ),
    ParameterItem(
        key="rule_tempo_espera",
        label="Detectar tempo de espera",
        description="Pessoas aguardando em recepção/corredor/fila.",
        where="Ambientes",
        default="desligado (ative em Recepção/Corredor)",
    ),
    ParameterItem(
        key="wait_max_minutes",
        label="Limite de espera (minutos)",
        description="Tempo contínuo aguardando para gerar tempo_espera_excessivo.",
        where="Ambientes",
        default="10",
    ),
    ParameterItem(
        key="uniform_expected",
        label="Uniforme esperado",
        description="Cores/peças da farda daquele DVR/loja.",
        where="Ambientes",
        default="texto livre",
    ),
    ParameterItem(
        key="extra_instructions",
        label="Instruções extras",
        description="Exceções e detalhes para a IA.",
        where="Ambientes",
        default="texto livre",
    ),
    ParameterItem(
        key="analysis_interval_sec",
        label="Intervalo de análise (seg)",
        description="A cada quanto tempo puxa frame (global ou por câmera).",
        where="Configurações / Câmeras",
        default="30",
    ),
    ParameterItem(
        key="cooldown_minutes",
        label="Cooldown de alerta (min)",
        description="Evita spam do mesmo tipo de alerta.",
        where="Configurações",
        default="5",
    ),
    ParameterItem(
        key="confidence_threshold",
        label="Confiança mínima",
        description="Só grava alerta de frame se confiança >= limiar.",
        where="Configurações",
        default="0.6",
    ),
    ParameterItem(
        key="active_provider",
        label="Provedor de IA",
        description="openai | gemini | claude + API key + modelo.",
        where="Configurações",
        default="claude / openai",
    ),
]


def build_reports_context(db: Session) -> str:
    now = datetime.utcnow()
    since = now - timedelta(hours=24)
    cameras = db.query(Camera).options(joinedload(Camera.profile)).all()
    alerts = (
        db.query(Alert)
        .options(joinedload(Alert.camera))
        .filter(Alert.created_at >= since)
        .order_by(Alert.id.desc())
        .limit(40)
        .all()
    )
    sessions = (
        db.query(PresenceSession)
        .filter(PresenceSession.last_seen_at >= since)
        .order_by(PresenceSession.id.desc())
        .limit(40)
        .all()
    )
    obs = (
        db.query(FrameObservation)
        .filter(FrameObservation.created_at >= since)
        .order_by(FrameObservation.id.desc())
        .limit(30)
        .all()
    )

    cam_lines = []
    for c in cameras:
        pname = c.profile.name if c.profile else "sem perfil"
        cam_lines.append(
            f"- #{c.id} {c.name} | local={c.location or '—'} | status={c.status} | perfil={pname} | enabled={c.enabled}"
        )

    alert_lines = []
    for a in alerts:
        try:
            viol = json.loads(a.violations)
        except Exception:
            viol = [a.violations]
        cname = a.camera.name if a.camera else f"cam {a.camera_id}"
        alert_lines.append(
            f"- [{a.created_at.isoformat()}] {cname}: {viol} | {a.description} | fb={a.feedback or '-'}"
        )

    sess_lines = []
    for s in sessions:
        mins = s.duration_sec // 60
        sess_lines.append(
            f"- cam={s.camera_id} kind={s.kind} active={s.active} ~{mins}min alerted={s.alerted} start={s.started_at.isoformat()}"
        )

    phone_obs = sum(1 for o in obs if o.phone_in_use)
    wait_obs = sum(1 for o in obs if o.people_waiting)

    return (
        f"Agora (UTC): {now.isoformat()}\n"
        f"Câmeras ({len(cameras)}):\n"
        + ("\n".join(cam_lines) or "- nenhuma")
        + f"\n\nAlertas 24h ({len(alerts)}):\n"
        + ("\n".join(alert_lines) or "- nenhum")
        + f"\n\nSessões presença/celular 24h ({len(sessions)}):\n"
        + ("\n".join(sess_lines) or "- nenhuma")
        + f"\n\nObservações recentes: {len(obs)} frames | phone_in_use={phone_obs} | people_waiting={wait_obs}\n"
    )


def ask_reports_ai(db: Session, user_message: str) -> str:
    settings = get_or_create_settings(db)
    provider = (settings.active_provider or "openai").lower()
    api_key = resolve_api_key(settings, provider)
    if not api_key:
        raise RuntimeError(f"API key não configurada para '{provider}'")

    context = build_reports_context(db)
    history = (
        db.query(ReportChatMessage)
        .order_by(ReportChatMessage.id.desc())
        .limit(12)
        .all()
    )
    history = list(reversed(history))

    system = (
        "Você é o analista do Pizza Pizza Eyes. Responda em português do Brasil, com base APENAS "
        "no contexto operacional das câmeras fornecido. Se não houver dado, diga que não há "
        "informação suficiente. Seja objetivo, use listas quando útil, cite câmeras e horários."
    )
    user_block = f"CONTEXTO DAS CÂMERAS:\n{context}\n\nPERGUNTA DO USUÁRIO:\n{user_message}"

    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        messages = [{"role": "system", "content": system}]
        for h in history[-8:]:
            messages.append({"role": h.role if h.role in {"user", "assistant"} else "user", "content": h.content})
        messages.append({"role": "user", "content": user_block})
        resp = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.2,
            messages=messages,
        )
        return (resp.choices[0].message.content or "").strip()

    if provider == "claude":
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        msgs = []
        for h in history[-8:]:
            role = "user" if h.role == "user" else "assistant"
            msgs.append({"role": role, "content": h.content})
        msgs.append({"role": "user", "content": user_block})
        resp = client.messages.create(
            model=settings.claude_model,
            max_tokens=1200,
            temperature=0.2,
            system=system,
            messages=msgs,
        )
        parts = []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "\n".join(parts).strip()

    if provider == "gemini":
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(settings.gemini_model, system_instruction=system)
        hist_txt = "\n".join(f"{h.role}: {h.content}" for h in history[-8:])
        prompt = f"{hist_txt}\n\n{user_block}" if hist_txt else user_block
        resp = model.generate_content(prompt)
        return (resp.text or "").strip()

    raise RuntimeError(f"Provedor não suportado: {provider}")
