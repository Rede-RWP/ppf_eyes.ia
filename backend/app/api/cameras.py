from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Camera, MonitorProfile, User
from app.schemas import CameraCreate, CameraOut, CameraTestOut, CameraUpdate
from app.security import get_current_user, mask_rtsp
from app.services.alert_service import camera_to_out
from app.services.profiles_seed import ensure_default_profiles
from app.services.rtsp_capture import capture_frame, normalize_rtsp_url, save_jpeg
from sqlalchemy.orm import joinedload

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


def _validate_profile(db, profile_id):
    if profile_id is None:
        return
    if not db.query(MonitorProfile).filter(MonitorProfile.id == profile_id).first():
        raise HTTPException(status_code=400, detail="Perfil de ambiente inválido")


@router.get("", response_model=List[CameraOut])
def list_cameras(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ensure_default_profiles(db)
    cameras = (
        db.query(Camera)
        .options(joinedload(Camera.profile))
        .order_by(Camera.id.desc())
        .all()
    )
    return [CameraOut(**camera_to_out(c)) for c in cameras]


@router.post("", response_model=CameraOut)
def create_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ensure_default_profiles(db)
    if not payload.rtsp_url.lower().startswith("rtsp://"):
        raise HTTPException(status_code=400, detail="URL deve começar com rtsp://")
    _validate_profile(db, payload.profile_id)
    camera = Camera(
        name=payload.name.strip(),
        rtsp_url=normalize_rtsp_url(payload.rtsp_url),
        location=(payload.location or "").strip() or None,
        profile_id=payload.profile_id,
        enabled=payload.enabled,
        interval_sec=payload.interval_sec,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    camera = (
        db.query(Camera)
        .options(joinedload(Camera.profile))
        .filter(Camera.id == camera.id)
        .first()
    )
    return CameraOut(**camera_to_out(camera))


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    camera = (
        db.query(Camera)
        .options(joinedload(Camera.profile))
        .filter(Camera.id == camera_id)
        .first()
    )
    if not camera:
        raise HTTPException(status_code=404, detail="Câmera não encontrada")
    return CameraOut(**camera_to_out(camera))


@router.put("/{camera_id}", response_model=CameraOut)
def update_camera(
    camera_id: int,
    payload: CameraUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Câmera não encontrada")
    data = payload.model_dump(exclude_unset=True)
    if "rtsp_url" in data and data["rtsp_url"]:
        if not data["rtsp_url"].lower().startswith("rtsp://"):
            raise HTTPException(status_code=400, detail="URL deve começar com rtsp://")
        data["rtsp_url"] = normalize_rtsp_url(data["rtsp_url"])
    if "profile_id" in data:
        _validate_profile(db, data["profile_id"])
    for field, value in data.items():
        setattr(camera, field, value)
    camera.updated_at = datetime.utcnow()
    db.commit()
    camera = (
        db.query(Camera)
        .options(joinedload(Camera.profile))
        .filter(Camera.id == camera_id)
        .first()
    )
    return CameraOut(**camera_to_out(camera))


@router.delete("/{camera_id}")
def delete_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Câmera não encontrada")
    db.delete(camera)
    db.commit()
    return {"ok": True}


@router.post("/{camera_id}/test", response_model=CameraTestOut)
def test_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Câmera não encontrada")

    ok, message, jpeg = capture_frame(camera.rtsp_url)
    now = datetime.utcnow()
    if not ok or not jpeg:
        camera.status = "offline"
        camera.last_error = message
        camera.updated_at = now
        db.commit()
        return CameraTestOut(ok=False, message=message)

    relative = save_jpeg(jpeg, f"preview_cam_{camera.id}_{int(now.timestamp())}.jpg")
    camera.status = "online"
    camera.last_seen_at = now
    camera.last_frame_path = relative
    camera.last_error = None
    camera.updated_at = now
    db.commit()
    return CameraTestOut(ok=True, message=f"OK ({mask_rtsp(camera.rtsp_url)})", preview_path=relative)
