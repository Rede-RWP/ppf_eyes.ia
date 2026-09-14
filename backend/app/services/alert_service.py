from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Alert, AnalysisLog, AppSettings, Camera
from app.schemas import AlertOut, VisionResult
from app.services.ai_router import analyze_frame
from app.services.rtsp_capture import capture_frame, save_jpeg


def camera_to_out(camera: Camera) -> dict:
    from app.security import mask_rtsp

    profile = getattr(camera, "profile", None)
    return {
        "id": camera.id,
        "name": camera.name,
        "rtsp_url_masked": mask_rtsp(camera.rtsp_url),
        "location": camera.location,
        "profile_id": camera.profile_id,
        "profile_name": profile.name if profile else None,
        "enabled": camera.enabled,
        "interval_sec": camera.interval_sec,
        "status": camera.status,
        "last_seen_at": camera.last_seen_at,
        "last_frame_path": camera.last_frame_path,
        "last_error": camera.last_error,
        "created_at": camera.created_at,
        "updated_at": camera.updated_at,
    }


def alert_to_out(alert: Alert, camera_name: Optional[str] = None) -> AlertOut:
    try:
        violations = json.loads(alert.violations)
    except json.JSONDecodeError:
        violations = [alert.violations]
    return AlertOut(
        id=alert.id,
        camera_id=alert.camera_id,
        camera_name=camera_name or (alert.camera.name if alert.camera else None),
        violations=violations,
        description=alert.description,
        confidence=alert.confidence,
        snapshot_path=alert.snapshot_path,
        feedback=alert.feedback,
        feedback_comment=getattr(alert, "feedback_comment", None),
        favorited=bool(getattr(alert, "favorited", False)),
        favorite_path=getattr(alert, "favorite_path", None),
        favorited_at=getattr(alert, "favorited_at", None),
        created_at=alert.created_at,
    )


def get_or_create_settings(db: Session) -> AppSettings:
    from app.services.ai_common import load_default_prompt

    row = db.query(AppSettings).first()
    if row:
        # Atualiza prompt legado sem seção de detections (caixa na foto do alerta)
        prompt = row.base_prompt or ""
        if '"detections"' not in prompt and "detections" not in prompt:
            row.base_prompt = load_default_prompt()
            db.commit()
            db.refresh(row)
        return row
    from app.config import get_settings

    env = get_settings()
    row = AppSettings(
        active_provider=env.default_ai_provider,
        base_prompt=load_default_prompt(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _in_cooldown(
    db: Session,
    camera_id: int,
    violations: List[str],
    cooldown_minutes: int,
) -> bool:
    if cooldown_minutes <= 0:
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


def process_camera(db: Session, camera: Camera, settings_row: AppSettings) -> None:
    ok, message, jpeg = capture_frame(camera.rtsp_url)
    now = datetime.utcnow()
    if not ok or not jpeg:
        camera.status = "offline"
        camera.last_error = message
        camera.updated_at = now
        db.add(
            AnalysisLog(
                camera_id=camera.id,
                provider=settings_row.active_provider,
                success=False,
                message=message,
            )
        )
        db.commit()
        return

    frame_name = f"cam_{camera.id}_{int(now.timestamp())}.jpg"
    relative = save_jpeg(jpeg, frame_name)
    camera.last_frame_path = relative
    camera.status = "online"
    camera.last_seen_at = now
    camera.last_error = None
    camera.updated_at = now

    try:
        # Reload relationship if needed
        profile = camera.profile
        if camera.profile_id and profile is None:
            from app.models import MonitorProfile

            profile = (
                db.query(MonitorProfile)
                .filter(MonitorProfile.id == camera.profile_id)
                .first()
            )
        result: VisionResult = analyze_frame(
            settings_row, jpeg, camera=camera, profile=profile, db=db
        )
        db.add(
            AnalysisLog(
                camera_id=camera.id,
                provider=settings_row.active_provider,
                success=True,
                message=result.description or "ok",
            )
        )
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        # Keep message short and explicit that stream is fine
        if "not_found_error" in err or "model:" in err:
            camera.last_error = (
                f"Modelo IA inválido ({settings_row.active_provider}). "
                "Ajuste em Configurações → modelo."
            )
        elif "Incorrect API key" in err or "invalid_api_key" in err or "401" in err:
            camera.last_error = (
                f"API key inválida ({settings_row.active_provider}). "
                "Cole a key correta em Configurações e salve."
            )
        else:
            camera.last_error = f"IA ({settings_row.active_provider}): {err[:180]}"
        db.add(
            AnalysisLog(
                camera_id=camera.id,
                provider=settings_row.active_provider,
                success=False,
                message=err[:500],
            )
        )
        db.commit()
        return

    interval = camera.interval_sec or settings_row.analysis_interval_sec
    from app.services.presence_service import update_presence_and_alerts

    update_presence_and_alerts(
        db,
        camera_id=camera.id,
        profile=profile,
        result=result,
        jpeg=jpeg,
        interval_sec=interval,
        cooldown_minutes=settings_row.cooldown_minutes,
        confidence_threshold=settings_row.confidence_threshold,
    )

    db.commit()
