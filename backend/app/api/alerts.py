from __future__ import annotations

import shutil
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db import get_db
from app.models import Alert, Camera, User
from app.schemas import AlertFavoriteIn, AlertFeedbackIn, AlertOut, DashboardOut
from app.security import get_current_user
from app.services.alert_service import alert_to_out

router = APIRouter(prefix="/api", tags=["alerts"])


@router.get("/alerts", response_model=List[AlertOut])
def list_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    camera_id: Optional[int] = None,
    favorited: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Alert).options(joinedload(Alert.camera)).order_by(Alert.id.desc())
    if camera_id:
        q = q.filter(Alert.camera_id == camera_id)
    if favorited is True:
        q = q.filter(Alert.favorited.is_(True)).order_by(Alert.favorited_at.desc())
    alerts = q.limit(limit).all()
    return [alert_to_out(a) for a in alerts]


@router.get("/favorites", response_model=List[AlertOut])
def list_favorites(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    alerts = (
        db.query(Alert)
        .options(joinedload(Alert.camera))
        .filter(Alert.favorited.is_(True))
        .order_by(Alert.favorited_at.desc(), Alert.id.desc())
        .limit(limit)
        .all()
    )
    return [alert_to_out(a) for a in alerts]


@router.get("/alerts/{alert_id}", response_model=AlertOut)
def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    alert = (
        db.query(Alert)
        .options(joinedload(Alert.camera))
        .filter(Alert.id == alert_id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    return alert_to_out(alert)


@router.post("/alerts/{alert_id}/feedback", response_model=AlertOut)
def set_feedback(
    alert_id: int,
    payload: AlertFeedbackIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    alert = (
        db.query(Alert)
        .options(joinedload(Alert.camera))
        .filter(Alert.id == alert_id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    fb = payload.feedback.lower().strip()
    if fb == "clear":
        alert.feedback = None
        alert.feedback_comment = None
    elif fb == "tp":
        alert.feedback = "tp"
        alert.feedback_comment = (payload.comment or "").strip() or None
    elif fb == "fp":
        comment = (payload.comment or "").strip()
        if len(comment) < 5:
            raise HTTPException(
                status_code=400,
                detail="No dislike, explique o erro da IA (mín. 5 caracteres).",
            )
        alert.feedback = "fp"
        alert.feedback_comment = comment
    else:
        raise HTTPException(status_code=400, detail="feedback deve ser tp, fp ou clear")
    db.commit()
    db.refresh(alert)
    return alert_to_out(alert)


@router.post("/alerts/{alert_id}/favorite", response_model=AlertOut)
def set_favorite(
    alert_id: int,
    payload: AlertFavoriteIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    alert = (
        db.query(Alert)
        .options(joinedload(Alert.camera))
        .filter(Alert.id == alert_id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")

    settings = get_settings()
    settings.favorites_path.mkdir(parents=True, exist_ok=True)

    from app.services.retention import default_expire_at

    if payload.favorited:
        src_rel = alert.snapshot_path or alert.favorite_path
        if not src_rel:
            raise HTTPException(status_code=400, detail="Alerta sem snapshot para favoritar")
        src = settings.data_path / src_rel
        if not src.exists():
            raise HTTPException(status_code=404, detail="Arquivo do snapshot não encontrado")
        dest_name = f"favorite_alert_{alert.id}{src.suffix or '.jpg'}"
        dest = settings.favorites_path / dest_name
        if str(src.resolve()) != str(dest.resolve()):
            shutil.copy2(src, dest)
        alert.favorited = True
        alert.favorite_path = f"favorites/{dest_name}"
        alert.favorited_at = datetime.utcnow()
        alert.images_expire_at = None  # favorito não expira
    else:
        # Entra no ciclo de 24h a partir de agora; mantém o arquivo até o purge
        alert.favorited = False
        alert.favorited_at = None
        alert.images_expire_at = default_expire_at()
        if not alert.favorite_path and alert.snapshot_path:
            # garante que há arquivo rastreável até expirar
            pass

    db.commit()
    db.refresh(alert)
    return alert_to_out(alert)


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cameras = db.query(Camera).all()
    online = sum(1 for c in cameras if c.status == "online")
    offline = sum(1 for c in cameras if c.status == "offline")
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    alerts_today = db.query(Alert).filter(Alert.created_at >= start).count()
    recent = (
        db.query(Alert)
        .options(joinedload(Alert.camera))
        .order_by(Alert.id.desc())
        .limit(8)
        .all()
    )
    return DashboardOut(
        cameras_total=len(cameras),
        cameras_online=online,
        cameras_offline=offline,
        alerts_today=alerts_today,
        recent_alerts=[alert_to_out(a) for a in recent],
    )
