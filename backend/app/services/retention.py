from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Alert, Camera

logger = logging.getLogger("ppf-eyes.retention")


def retention_delta() -> timedelta:
    hours = max(1, int(get_settings().snapshot_retention_hours))
    return timedelta(hours=hours)


def default_expire_at(from_dt: Optional[datetime] = None) -> datetime:
    return (from_dt or datetime.utcnow()) + retention_delta()


def _unlink_rel(rel: Optional[str]) -> bool:
    if not rel:
        return False
    settings = get_settings()
    path = (settings.data_path / rel).resolve()
    root = settings.data_path.resolve()
    if not str(path).startswith(str(root)):
        return False
    if not path.exists() or not path.is_file():
        return False
    try:
        path.unlink()
        return True
    except OSError as exc:
        logger.warning("Falha ao apagar %s: %s", path, exc)
        return False


def purge_expired_alert_images(db: Session) -> Tuple[int, int]:
    """
    Apaga imagens de alertas expirados.
    - Favoritos: nunca apaga favorite_path; pode limpar snapshot antigo.
    - Não favoritos: apaga snapshot e cópia de favorito após images_expire_at.
    """
    now = datetime.utcnow()
    deleted_files = 0
    touched = 0

    # 1) Não favoritos com prazo vencido
    expired = (
        db.query(Alert)
        .filter(
            Alert.favorited.is_(False),
            Alert.images_expire_at.isnot(None),
            Alert.images_expire_at <= now,
        )
        .limit(500)
        .all()
    )
    for alert in expired:
        changed = False
        if _unlink_rel(alert.snapshot_path):
            deleted_files += 1
            changed = True
        if alert.snapshot_path:
            alert.snapshot_path = None
            changed = True
        if _unlink_rel(alert.favorite_path):
            deleted_files += 1
            changed = True
        if alert.favorite_path:
            alert.favorite_path = None
            changed = True
        if changed:
            touched += 1

    # 2) Favoritos: snapshot original pode ir embora após 24h da criação;
    #    a cópia em favorites/ permanece.
    fav_cutoff = now - retention_delta()
    favorited = (
        db.query(Alert)
        .filter(
            Alert.favorited.is_(True),
            Alert.snapshot_path.isnot(None),
            Alert.created_at <= fav_cutoff,
        )
        .limit(500)
        .all()
    )
    for alert in favorited:
        # só remove snapshot se já existe cópia favorita
        if not alert.favorite_path:
            continue
        if _unlink_rel(alert.snapshot_path):
            deleted_files += 1
            alert.snapshot_path = None
            touched += 1

    # 3) Backfill: alertas antigos sem images_expire_at
    missing = (
        db.query(Alert)
        .filter(Alert.favorited.is_(False), Alert.images_expire_at.is_(None))
        .limit(500)
        .all()
    )
    for alert in missing:
        alert.images_expire_at = default_expire_at(alert.created_at)

    if touched or missing:
        db.commit()

    # 4) Frames de câmera órfãos / muito antigos (preview), sem tocar favorites/
    deleted_files += _purge_orphan_snapshots(db, now)

    if deleted_files:
        logger.info(
            "Retention: %s arquivo(s) removido(s), %s alerta(s) atualizado(s)",
            deleted_files,
            touched,
        )
    return deleted_files, touched


def _purge_orphan_snapshots(db: Session, now: datetime) -> int:
    settings = get_settings()
    snap_dir = settings.snapshots_path
    if not snap_dir.exists():
        return 0

    protected = set()
    for rel, in db.query(Alert.snapshot_path).filter(Alert.snapshot_path.isnot(None)):
        if rel:
            protected.add(Path(rel).name)
    for rel, in db.query(Camera.last_frame_path).filter(Camera.last_frame_path.isnot(None)):
        if rel:
            protected.add(Path(rel).name)

    cutoff = now - retention_delta()
    removed = 0
    for path in snap_dir.glob("*"):
        if not path.is_file():
            continue
        if path.name in protected:
            continue
        try:
            mtime = datetime.utcfromtimestamp(path.stat().st_mtime)
        except OSError:
            continue
        if mtime > cutoff:
            continue
        try:
            path.unlink()
            removed += 1
        except OSError:
            continue
    return removed
