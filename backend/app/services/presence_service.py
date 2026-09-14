from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Alert, FrameObservation, MonitorProfile, PresenceSession
from app.schemas import VisionResult
from app.services.rtsp_capture import save_jpeg


def _gap_limit_sec(interval_sec: int) -> int:
    # close session if no confirming frame for ~2.5 intervals
    return max(90, int(interval_sec * 2.5))


def _upsert_session(
    db: Session,
    *,
    camera_id: int,
    kind: str,
    active_signal: bool,
    now: datetime,
    interval_sec: int,
) -> Optional[PresenceSession]:
    session = (
        db.query(PresenceSession)
        .filter(
            PresenceSession.camera_id == camera_id,
            PresenceSession.kind == kind,
            PresenceSession.active.is_(True),
        )
        .order_by(PresenceSession.id.desc())
        .first()
    )
    if active_signal:
        if session:
            session.last_seen_at = now
            session.duration_sec = max(0, int((now - session.started_at).total_seconds()))
            return session
        session = PresenceSession(
            camera_id=camera_id,
            kind=kind,
            started_at=now,
            last_seen_at=now,
            duration_sec=0,
            alerted=False,
            active=True,
        )
        db.add(session)
        db.flush()
        return session

    if session:
        gap = (now - session.last_seen_at).total_seconds()
        if gap > _gap_limit_sec(interval_sec):
            session.active = False
            session.ended_at = session.last_seen_at
            session.duration_sec = max(
                0, int((session.last_seen_at - session.started_at).total_seconds())
            )
    return None


def update_presence_and_alerts(
    db: Session,
    *,
    camera_id: int,
    profile: Optional[MonitorProfile],
    result: VisionResult,
    jpeg: bytes,
    interval_sec: int,
    cooldown_minutes: int,
    confidence_threshold: float,
) -> List[Alert]:
    now = datetime.utcnow()
    created: List[Alert] = []

    db.add(
        FrameObservation(
            camera_id=camera_id,
            person_count=result.person_count,
            phone_in_use=result.phone_in_use,
            people_waiting=result.people_waiting,
            is_anomaly=result.is_anomaly,
            violations=json.dumps(result.violations, ensure_ascii=False),
            description=result.description,
            confidence=result.confidence,
        )
    )

    rule_celular = bool(profile and getattr(profile, "rule_celular", False))
    rule_espera = bool(profile and getattr(profile, "rule_tempo_espera", False))
    phone_max = int(getattr(profile, "phone_max_minutes", 5) or 5) if profile else 5
    wait_max = int(getattr(profile, "wait_max_minutes", 10) or 10) if profile else 10

    phone_session = _upsert_session(
        db,
        camera_id=camera_id,
        kind="phone",
        active_signal=bool(rule_celular and result.phone_in_use),
        now=now,
        interval_sec=interval_sec,
    )
    wait_session = _upsert_session(
        db,
        camera_id=camera_id,
        kind="waiting",
        active_signal=bool(rule_espera and result.people_waiting),
        now=now,
        interval_sec=interval_sec,
    )

    duration_violations: List[str] = []
    descriptions: List[str] = []

    if (
        phone_session
        and rule_celular
        and not phone_session.alerted
        and phone_session.duration_sec >= phone_max * 60
    ):
        mins = max(1, phone_session.duration_sec // 60)
        duration_violations.append("celular_excessivo")
        descriptions.append(f"Pessoa no celular por cerca de {mins} min (limite {phone_max} min).")
        phone_session.alerted = True

    if (
        wait_session
        and rule_espera
        and not wait_session.alerted
        and wait_session.duration_sec >= wait_max * 60
    ):
        mins = max(1, wait_session.duration_sec // 60)
        duration_violations.append("tempo_espera_excessivo")
        descriptions.append(
            f"Pessoa aguardando por cerca de {mins} min (limite {wait_max} min)."
        )
        wait_session.alerted = True

    # PPE / frame violations
    frame_violations = list(result.violations or [])
    should_alert_frame = (
        result.is_anomaly
        and bool(frame_violations)
        and result.confidence >= confidence_threshold
    )
    should_alert_duration = bool(duration_violations)

    if not (should_alert_frame or should_alert_duration):
        return created

    final_violations: List[str] = []
    if should_alert_frame:
        final_violations.extend(frame_violations)
    if should_alert_duration:
        final_violations.extend(duration_violations)

    if _in_cooldown_local(db, camera_id, final_violations, cooldown_minutes):
        return created

    snap_name = f"alert_cam_{camera_id}_{int(now.timestamp())}.jpg"
    from app.services.annotate import annotate_jpeg, filter_detections_for_alert
    from app.services.retention import default_expire_at

    phone_alert = "celular_excessivo" in duration_violations
    wait_alert = "tempo_espera_excessivo" in duration_violations
    boxes = filter_detections_for_alert(
        result.detections,
        violations=final_violations,
        phone_alert=phone_alert or result.phone_in_use,
        wait_alert=wait_alert or result.people_waiting,
    )
    annotated = annotate_jpeg(jpeg, boxes) if boxes else jpeg
    snap_rel = save_jpeg(annotated, snap_name)
    desc_parts = []
    if should_alert_frame and result.description:
        desc_parts.append(result.description)
    desc_parts.extend(descriptions)
    alert = Alert(
        camera_id=camera_id,
        violations=json.dumps(final_violations, ensure_ascii=False),
        description=" ".join(desc_parts).strip() or "Alerta gerado pelo monitoramento.",
        confidence=result.confidence if should_alert_frame else 0.85,
        snapshot_path=snap_rel,
        images_expire_at=default_expire_at(now),
    )
    db.add(alert)
    created.append(alert)
    return created


def _in_cooldown_local(
    db: Session,
    camera_id: int,
    violations: List[str],
    cooldown_minutes: int,
) -> bool:
    if cooldown_minutes <= 0 or not violations:
        return False
    since = datetime.utcnow() - timedelta(minutes=cooldown_minutes)
    recent = (
        db.query(Alert)
        .filter(Alert.camera_id == camera_id, Alert.created_at >= since)
        .order_by(Alert.created_at.desc())
        .limit(20)
        .all()
    )
    target = set(violations)
    for alert in recent:
        try:
            prev = set(json.loads(alert.violations))
        except json.JSONDecodeError:
            prev = {alert.violations}
        if target & prev:
            return True
    return False
