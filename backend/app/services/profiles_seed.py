from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import MonitorProfile
from app.services.ai_common import slugify

DEFAULT_PROFILES = [
    {
        "name": "Cozinha",
        "environment_type": "cozinha",
        "description": "Área de manipulação de alimentos — exige higiene rigorosa.",
        "rule_sem_touca": True,
        "rule_fardamento": True,
        "rule_sem_epi": False,
        "rule_celular": False,
        "phone_max_minutes": 5,
        "rule_tempo_espera": False,
        "wait_max_minutes": 10,
        "uniform_expected": "Touca/rede de cabelo + farda/jaleco de cozinha (conforme padrão da loja).",
        "extra_instructions": "Qualquer pessoa na área de produção sem touca ou sem farda adequada deve gerar alerta.",
        "is_default": False,
    },
    {
        "name": "Escritório",
        "environment_type": "escritorio",
        "description": "Ambiente administrativo — sem exigência de touca.",
        "rule_sem_touca": False,
        "rule_fardamento": False,
        "rule_sem_epi": False,
        "rule_celular": True,
        "phone_max_minutes": 8,
        "rule_tempo_espera": False,
        "wait_max_minutes": 10,
        "uniform_expected": "Roupa social/casual de escritório; sem padrão rígido de farda.",
        "extra_instructions": "Não alerte por ausência de touca. Só alerte se instruções extras forem adicionadas.",
        "is_default": True,
    },
    {
        "name": "Recepção",
        "environment_type": "recepcao",
        "description": "Recepção / entrada da unidade.",
        "rule_sem_touca": False,
        "rule_fardamento": True,
        "rule_sem_epi": False,
        "rule_celular": False,
        "phone_max_minutes": 5,
        "rule_tempo_espera": True,
        "wait_max_minutes": 10,
        "uniform_expected": "Uniforme de atendimento/recepção da marca (descreva cores no campo se necessário).",
        "extra_instructions": "Clientes em geral não devem gerar alerta de fardamento; foque em colaboradores visíveis.",
        "is_default": False,
    },
    {
        "name": "Atendimento Delivery",
        "environment_type": "delivery",
        "description": "Balcão / espera de delivery.",
        "rule_sem_touca": False,
        "rule_fardamento": True,
        "rule_sem_epi": False,
        "rule_celular": False,
        "phone_max_minutes": 5,
        "rule_tempo_espera": True,
        "wait_max_minutes": 12,
        "uniform_expected": "Farda de atendimento delivery da marca.",
        "extra_instructions": "Motoboys/clientes podem aparecer; alerte fardamento só de colaboradores identificados.",
        "is_default": False,
    },
    {
        "name": "Atendimento Salão",
        "environment_type": "atendimento_salao",
        "description": "Atendimento ao público no salão.",
        "rule_sem_touca": False,
        "rule_fardamento": True,
        "rule_sem_epi": False,
        "rule_celular": False,
        "phone_max_minutes": 5,
        "rule_tempo_espera": False,
        "wait_max_minutes": 10,
        "uniform_expected": "Farda de salão/atendimento da marca.",
        "extra_instructions": "Não exija touca. Clientes sentados não são violação.",
        "is_default": False,
    },
    {
        "name": "Salão Pizzaria",
        "environment_type": "salao_pizzaria",
        "description": "Salão / mesas da pizzaria.",
        "rule_sem_touca": False,
        "rule_fardamento": True,
        "rule_sem_epi": False,
        "rule_celular": False,
        "phone_max_minutes": 5,
        "rule_tempo_espera": False,
        "wait_max_minutes": 10,
        "uniform_expected": "Farda de salão da pizzaria (ajuste cores por DVR/loja nas instruções extras).",
        "extra_instructions": "Priorize colaboradores. Público/clientes não devem gerar alerta de farda.",
        "is_default": False,
    },
    {
        "name": "Corredor / Geral",
        "environment_type": "corredor",
        "description": "Corredores e áreas de passagem.",
        "rule_sem_touca": False,
        "rule_fardamento": False,
        "rule_sem_epi": False,
        "rule_celular": False,
        "phone_max_minutes": 5,
        "rule_tempo_espera": True,
        "wait_max_minutes": 8,
        "uniform_expected": "Sem padrão fixo.",
        "extra_instructions": "Ambiente de passagem — medir tempo de espera; sem regras rígidas de farda.",
        "is_default": False,
    },
]


def ensure_default_profiles(db: Session) -> None:
    by_slug = {p.slug: p for p in db.query(MonitorProfile).all()}
    created = False
    for item in DEFAULT_PROFILES:
        slug = slugify(item["name"])
        if slug in by_slug:
            continue
        db.add(
            MonitorProfile(
                name=item["name"],
                slug=slug,
                environment_type=item["environment_type"],
                description=item.get("description"),
                rule_sem_touca=item["rule_sem_touca"],
                rule_fardamento=item["rule_fardamento"],
                rule_sem_epi=item["rule_sem_epi"],
                rule_celular=bool(item.get("rule_celular", False)),
                phone_max_minutes=int(item.get("phone_max_minutes", 5) or 5),
                rule_tempo_espera=bool(item.get("rule_tempo_espera", False)),
                wait_max_minutes=int(item.get("wait_max_minutes", 10) or 10),
                uniform_expected=item.get("uniform_expected"),
                extra_instructions=item.get("extra_instructions"),
                is_default=bool(item.get("is_default")),
            )
        )
        created = True
    if created:
        db.commit()
