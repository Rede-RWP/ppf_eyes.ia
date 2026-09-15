from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.db import SessionLocal
from app.models import Camera, Store
from app.services.alert_service import get_or_create_settings, process_camera
from app.services.motion import motion_detector
from app.services.retention import purge_expired_alert_images
from app.services.rtsp_capture import capture_frame_bgr
from app.services.store_hours import is_store_open

logger = logging.getLogger("ppf-eyes.worker")


class MonitorWorker:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_check: Dict[int, datetime] = {}
        self._last_ai: Dict[int, datetime] = {}
        self._last_purge: Optional[datetime] = None
        self._closed_logged: Dict[int, str] = {}

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
            env = get_settings()
            tz = env.app_timezone or "America/Sao_Paulo"

            respect_hours = bool(getattr(settings_row, "respect_store_hours", True))
            motion_enabled = bool(getattr(settings_row, "motion_enabled", True))
            motion_interval = int(
                getattr(settings_row, "motion_check_interval_sec", 8) or 8
            )
            motion_sensitivity = float(
                getattr(settings_row, "motion_sensitivity", 0.02) or 0.02
            )
            motion_pixel_threshold = int(
                getattr(settings_row, "motion_pixel_threshold", 25) or 25
            )
            motion_cooldown = int(
                getattr(settings_row, "motion_cooldown_sec", 45) or 45
            )
            ai_heartbeat = int(getattr(settings_row, "ai_heartbeat_sec", 300) or 0)

            cameras = (
                db.query(Camera)
                .options(
                    joinedload(Camera.profile),
                    joinedload(Camera.store).joinedload(Store.hours),
                )
                .filter(Camera.enabled.is_(True))
                .all()
            )
            now = datetime.utcnow()

            for camera in cameras:
                # 1) Horário da loja
                if respect_hours and camera.store_id:
                    if not is_store_open(camera.store, timezone_name=tz):
                        key = f"{camera.id}-closed"
                        if self._closed_logged.get(camera.id) != key:
                            logger.info(
                                "Camera %s fora do horário da loja — IA pausada",
                                camera.id,
                            )
                            self._closed_logged[camera.id] = key
                            camera.last_error = "Fora do horário de funcionamento da loja"
                            camera.updated_at = now
                            db.commit()
                        motion_detector.reset(camera.id)
                        continue
                    self._closed_logged.pop(camera.id, None)
                    if camera.last_error and "horário" in (camera.last_error or "").lower():
                        camera.last_error = None

                # 2) Intervalo de checagem (movimento) ou análise clássica
                if motion_enabled:
                    interval = max(3, motion_interval)
                else:
                    interval = camera.interval_sec or settings_row.analysis_interval_sec

                last_check = self._last_check.get(camera.id)
                if last_check and (now - last_check).total_seconds() < interval:
                    continue
                self._last_check[camera.id] = now

                try:
                    if not motion_enabled:
                        process_camera(db, camera, settings_row, run_ai=True)
                        self._last_ai[camera.id] = now
                        continue

                    ok, message, bgr, jpeg = capture_frame_bgr(camera.rtsp_url)
                    if not ok or not jpeg:
                        camera.status = "offline"
                        camera.last_error = message
                        camera.updated_at = now
                        db.commit()
                        motion_detector.reset(camera.id)
                        continue

                    # Atualiza preview/status sem IA
                    process_camera(
                        db, camera, settings_row, jpeg=jpeg, run_ai=False
                    )

                    should_ai = False
                    reason = ""
                    if bgr is not None:
                        result = motion_detector.detect(
                            camera.id,
                            bgr,
                            sensitivity=motion_sensitivity,
                            pixel_threshold=motion_pixel_threshold,
                        )
                        if result.baseline:
                            # Primeiro frame: só estabelece baseline
                            should_ai = False
                        elif result.motion:
                            should_ai = True
                            reason = f"motion score={result.score:.4f}"

                    last_ai = self._last_ai.get(camera.id)
                    if should_ai:
                        if last_ai and (now - last_ai).total_seconds() < motion_cooldown:
                            should_ai = False
                    elif ai_heartbeat > 0:
                        if not last_ai or (now - last_ai).total_seconds() >= ai_heartbeat:
                            should_ai = True
                            reason = "heartbeat"

                    if not should_ai:
                        continue

                    logger.info("AI camera %s (%s)", camera.id, reason or "run")
                    process_camera(db, camera, settings_row, jpeg=jpeg, run_ai=True)
                    self._last_ai[camera.id] = now
                except Exception:  # noqa: BLE001
                    logger.exception("Failed processing camera %s", camera.id)

            if not self._last_purge or (now - self._last_purge).total_seconds() >= 600:
                try:
                    purge_expired_alert_images(db)
                    self._last_purge = now
                except Exception:  # noqa: BLE001
                    logger.exception("Retention purge failed")
        finally:
            db.close()


monitor_worker = MonitorWorker()
