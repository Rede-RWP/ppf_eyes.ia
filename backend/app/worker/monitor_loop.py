from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Dict

from app.db import SessionLocal
from app.models import Camera
from app.services.alert_service import get_or_create_settings, process_camera
from app.services.retention import purge_expired_alert_images
from sqlalchemy.orm import joinedload

logger = logging.getLogger("ppf-eyes.worker")


class MonitorWorker:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_run: Dict[int, datetime] = {}
        self._last_purge: datetime | None = None

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        logger.info("Monitor worker started")
        while self._running:
            try:
                await asyncio.to_thread(self._tick)
            except Exception:  # noqa: BLE001
                logger.exception("Worker tick failed")
            await asyncio.sleep(2)
        logger.info("Monitor worker stopped")

    def _tick(self) -> None:
        db = SessionLocal()
        try:
            settings_row = get_or_create_settings(db)
            cameras = (
                db.query(Camera)
                .options(joinedload(Camera.profile))
                .filter(Camera.enabled.is_(True))
                .all()
            )
            now = datetime.utcnow()
            for camera in cameras:
                interval = camera.interval_sec or settings_row.analysis_interval_sec
                last = self._last_run.get(camera.id)
                if last and (now - last).total_seconds() < interval:
                    continue
                self._last_run[camera.id] = now
                try:
                    process_camera(db, camera, settings_row)
                except Exception:  # noqa: BLE001
                    logger.exception("Failed processing camera %s", camera.id)

            # Limpeza de imagens a cada ~10 min
            if not self._last_purge or (now - self._last_purge).total_seconds() >= 600:
                try:
                    purge_expired_alert_images(db)
                    self._last_purge = now
                except Exception:  # noqa: BLE001
                    logger.exception("Retention purge failed")
        finally:
            db.close()


monitor_worker = MonitorWorker()
