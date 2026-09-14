from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app.schemas import DetectionBox, VisionResult


def build_rules_text(
    rule_sem_touca: bool,
    rule_fardamento: bool,
    rule_sem_epi: bool,
    rule_celular: bool = False,
    rule_tempo_espera: bool = False,
    phone_max_minutes: int = 5,
    wait_max_minutes: int = 10,
) -> str:
    rules: List[str] = []
    if rule_sem_touca:
        rules.append("- sem_touca")
    if rule_fardamento:
        rules.append("- fardamento_inadequado")
    if rule_sem_epi:
        rules.append("- sem_epi")
    if rule_celular:
        rules.append(
            f"- observar uso de celular (phone_in_use); alerta de tempo após ~{phone_max_minutes} min contínuos"
        )
    if rule_tempo_espera:
        rules.append(
            f"- observar pessoas aguardando (people_waiting); alerta após ~{wait_max_minutes} min contínuos"
        )
    if not rules:
        return "- (nenhuma regra ativa — reporte is_anomaly=false e person_count)"
    return "\n".join(rules)


def render_prompt(
    template: str,
    *,
    rules_text: str,
    environment: str = "geral",
    camera_name: str = "",
    uniform: str = "não especificado",
    notes: str = "nenhuma",
    lessons: str = "nenhuma",
) -> str:
    return (
        template.replace("{{RULES}}", rules_text)
        .replace("{{ENVIRONMENT}}", environment or "geral")
        .replace("{{CAMERA_NAME}}", camera_name or "—")
        .replace("{{UNIFORM}}", uniform or "não especificado")
        .replace("{{NOTES}}", notes or "nenhuma")
        .replace("{{LESSONS}}", lessons or "nenhuma")
    )


def extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise
        return json.loads(match.group(0))


def _parse_detections(payload: Dict[str, Any]) -> List[DetectionBox]:
    raw = payload.get("detections") or payload.get("boxes") or []
    if not isinstance(raw, list):
        return []
    out: List[DetectionBox] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        box = item.get("box") or item.get("bbox") or item.get("xyxy") or []
        if isinstance(box, dict):
            box = [
                box.get("x1", box.get("left", 0)),
                box.get("y1", box.get("top", 0)),
                box.get("x2", box.get("right", 0)),
                box.get("y2", box.get("bottom", 0)),
            ]
        try:
            nums = [float(v) for v in list(box)[:4]]
        except (TypeError, ValueError):
            continue
        if len(nums) < 4:
            continue
        conf = item.get("confidence", item.get("score", payload.get("confidence", 0.7)))
        try:
            conf_f = float(conf)
        except (TypeError, ValueError):
            conf_f = 0.7
        conf_f = max(0.0, min(1.0, conf_f))
        label = str(item.get("label") or item.get("class") or item.get("violation") or "pessoa")
        flagged = item.get("flagged")
        if flagged is None:
            flagged = True
        out.append(
            DetectionBox(
                label=label.strip() or "pessoa",
                confidence=conf_f,
                box=nums,
                flagged=bool(flagged),
            )
        )
    return out[:12]


def normalize_vision_result(payload: Dict[str, Any]) -> VisionResult:
    violations = payload.get("violations") or []
    if isinstance(violations, str):
        violations = [violations]
    violations = [str(v).strip() for v in violations if str(v).strip()]
    # Backend calcula tempo; remove se a IA inventar
    violations = [
        v
        for v in violations
        if v not in {"celular_excessivo", "tempo_espera_excessivo"}
    ]
    confidence = float(payload.get("confidence") or 0.0)
    confidence = max(0.0, min(1.0, confidence))
    is_anomaly = bool(payload.get("is_anomaly"))
    description = str(payload.get("description") or "").strip()
    if is_anomaly and not description:
        description = "Anomalia detectada."
    try:
        person_count = int(payload.get("person_count") or 0)
    except (TypeError, ValueError):
        person_count = 0
    person_count = max(0, min(50, person_count))
    return VisionResult(
        is_anomaly=is_anomaly,
        violations=violations,
        description=description,
        confidence=confidence,
        person_count=person_count,
        phone_in_use=bool(payload.get("phone_in_use")),
        people_waiting=bool(payload.get("people_waiting")),
        detections=_parse_detections(payload),
    )


def load_default_prompt() -> str:
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "prompts" / "ppe_rules_pt.md"
    return path.read_text(encoding="utf-8")


def mask_key(value: Optional[str]) -> bool:
    return bool(value and value.strip())


def slugify(name: str) -> str:
    import re as _re
    import unicodedata

    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().strip()
    text = _re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "perfil"
