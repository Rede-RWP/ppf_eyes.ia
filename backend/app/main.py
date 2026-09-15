from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api import alerts, auth, cameras, profiles, reports, settings as settings_api, stores, users
from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.middleware_security import SecurityHeadersMiddleware
from app.models import Store, StoreHour, User
from app.permissions import ROLE_ADMIN, default_hours_payload
from app.security import get_current_user, hash_password
from app.services.alert_service import get_or_create_settings
from app.services.profiles_seed import ensure_default_profiles
from app.worker.monitor_loop import monitor_worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ppf-eyes")


def _column_names(conn, table: str) -> set[str]:
    url = str(engine.url)
    if url.startswith("sqlite"):
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        return {r[1] for r in rows}
    # MySQL / MariaDB — table name is internal only
    safe = "".join(ch for ch in table if ch.isalnum() or ch == "_")
    rows = conn.exec_driver_sql(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
        f"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{safe}'"
    ).fetchall()
    return {r[0] for r in rows}


def _migrate_schema() -> None:
    """Add missing columns on existing DBs (SQLite legado + MySQL)."""
    with engine.begin() as conn:
        url = str(engine.url)
        alert_cols = _column_names(conn, "alerts")
        if alert_cols and "images_expire_at" not in alert_cols:
            conn.exec_driver_sql(
                "ALTER TABLE alerts ADD COLUMN images_expire_at DATETIME NULL"
            )
            logger.info("Migrated alerts.images_expire_at")
            if url.startswith("sqlite"):
                conn.exec_driver_sql(
                    "UPDATE alerts SET images_expire_at = datetime(created_at, '+24 hours') "
                    "WHERE favorited = 0 OR favorited IS NULL"
                )
            else:
                conn.exec_driver_sql(
                    "UPDATE alerts SET images_expire_at = DATE_ADD(created_at, INTERVAL 24 HOUR) "
                    "WHERE favorited = 0 OR favorited IS NULL"
                )
            conn.exec_driver_sql(
                "UPDATE alerts SET images_expire_at = NULL WHERE favorited = 1"
            )

        user_cols = _column_names(conn, "users")
        if user_cols and "role" not in user_cols:
            if url.startswith("sqlite"):
                conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN role VARCHAR(32) DEFAULT 'admin'"
                )
            else:
                conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN role VARCHAR(32) NOT NULL DEFAULT 'admin'"
                )
            conn.exec_driver_sql("UPDATE users SET role = 'admin' WHERE role IS NULL OR role = ''")
            logger.info("Migrated users.role")
        if user_cols and "display_name" not in user_cols:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN display_name VARCHAR(120) NULL"
            )
            logger.info("Migrated users.display_name")
        if user_cols and "is_active" not in user_cols:
            if url.startswith("sqlite"):
                conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1"
                )
            else:
                conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1"
                )
            logger.info("Migrated users.is_active")

        cam_cols = _column_names(conn, "cameras")
        if cam_cols and "store_id" not in cam_cols:
            if url.startswith("sqlite"):
                conn.exec_driver_sql(
                    "ALTER TABLE cameras ADD COLUMN store_id INTEGER REFERENCES stores(id)"
                )
            else:
                conn.exec_driver_sql(
                    "ALTER TABLE cameras ADD COLUMN store_id INT NULL"
                )
                try:
                    conn.exec_driver_sql(
                        "ALTER TABLE cameras ADD INDEX ix_cameras_store_id (store_id)"
                    )
                except Exception:  # noqa: BLE001
                    pass
            logger.info("Migrated cameras.store_id")

        settings_cols = _column_names(conn, "app_settings")
        settings_migrations = {
            "respect_store_hours": (
                "ALTER TABLE app_settings ADD COLUMN respect_store_hours "
                + ("BOOLEAN DEFAULT 1" if url.startswith("sqlite") else "TINYINT(1) NOT NULL DEFAULT 1")
            ),
            "motion_enabled": (
                "ALTER TABLE app_settings ADD COLUMN motion_enabled "
                + ("BOOLEAN DEFAULT 1" if url.startswith("sqlite") else "TINYINT(1) NOT NULL DEFAULT 1")
            ),
            "motion_check_interval_sec": (
                "ALTER TABLE app_settings ADD COLUMN motion_check_interval_sec INTEGER DEFAULT 8"
            ),
            "motion_sensitivity": (
                "ALTER TABLE app_settings ADD COLUMN motion_sensitivity FLOAT DEFAULT 0.02"
            ),
            "motion_pixel_threshold": (
                "ALTER TABLE app_settings ADD COLUMN motion_pixel_threshold INTEGER DEFAULT 25"
            ),
            "motion_cooldown_sec": (
                "ALTER TABLE app_settings ADD COLUMN motion_cooldown_sec INTEGER DEFAULT 45"
            ),
            "ai_heartbeat_sec": (
                "ALTER TABLE app_settings ADD COLUMN ai_heartbeat_sec INTEGER DEFAULT 300"
            ),
        }
        for col, sql in settings_migrations.items():
            if settings_cols and col not in settings_cols:
                conn.exec_driver_sql(sql)
                logger.info("Migrated app_settings.%s", col)

        if url.startswith("sqlite"):
            if cam_cols and "profile_id" not in cam_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE cameras ADD COLUMN profile_id INTEGER REFERENCES monitor_profiles(id)"
                )
                logger.info("Migrated cameras.profile_id")

            alert_cols = _column_names(conn, "alerts")
            migrations = {
                "feedback_comment": "ALTER TABLE alerts ADD COLUMN feedback_comment TEXT",
                "favorited": "ALTER TABLE alerts ADD COLUMN favorited BOOLEAN DEFAULT 0",
                "favorite_path": "ALTER TABLE alerts ADD COLUMN favorite_path VARCHAR(255)",
                "favorited_at": "ALTER TABLE alerts ADD COLUMN favorited_at DATETIME",
            }
            for col, sql in migrations.items():
                if alert_cols and col not in alert_cols:
                    conn.exec_driver_sql(sql)
                    logger.info("Migrated alerts.%s", col)

            profile_cols = _column_names(conn, "monitor_profiles")
            profile_migrations = {
                "rule_celular": "ALTER TABLE monitor_profiles ADD COLUMN rule_celular BOOLEAN DEFAULT 0",
                "phone_max_minutes": "ALTER TABLE monitor_profiles ADD COLUMN phone_max_minutes INTEGER DEFAULT 5",
                "rule_tempo_espera": "ALTER TABLE monitor_profiles ADD COLUMN rule_tempo_espera BOOLEAN DEFAULT 0",
                "wait_max_minutes": "ALTER TABLE monitor_profiles ADD COLUMN wait_max_minutes INTEGER DEFAULT 10",
            }
            added_behavior = False
            for col, sql in profile_migrations.items():
                if profile_cols and col not in profile_cols:
                    conn.exec_driver_sql(sql)
                    logger.info("Migrated monitor_profiles.%s", col)
                    added_behavior = True
            if added_behavior:
                conn.exec_driver_sql(
                    "UPDATE monitor_profiles SET rule_celular=1, phone_max_minutes=8 "
                    "WHERE environment_type='escritorio'"
                )
                conn.exec_driver_sql(
                    "UPDATE monitor_profiles SET rule_tempo_espera=1, wait_max_minutes=10 "
                    "WHERE environment_type='recepcao'"
                )
                conn.exec_driver_sql(
                    "UPDATE monitor_profiles SET rule_tempo_espera=1, wait_max_minutes=8 "
                    "WHERE environment_type='corredor'"
                )


def _ensure_default_store(db) -> None:
    """Cria loja padrão e vincula câmeras sem store_id."""
    store = db.query(Store).order_by(Store.id.asc()).first()
    if not store:
        store = Store(name="Loja principal", cnpj=None, is_active=True)
        db.add(store)
        db.flush()
        for item in default_hours_payload():
            store.hours.append(
                StoreHour(
                    weekday=item["weekday"],
                    opens_at=item["opens_at"],
                    closes_at=item["closes_at"],
                    is_closed=item["is_closed"],
                )
            )
        db.commit()
        logger.info("Default store created: %s", store.name)

    from app.models import Camera

    orphan = db.query(Camera).filter(Camera.store_id.is_(None)).all()
    if orphan:
        for cam in orphan:
            cam.store_id = store.id
        db.commit()
        logger.info("Backfilled store_id on %s camera(s)", len(orphan))


def seed_db() -> None:
    settings = get_settings()
    if "change-me" in settings.app_secret_key.lower() or len(settings.app_secret_key) < 32:
        logger.warning(
            "APP_SECRET_KEY fraca ou padrão — defina uma chave longa no .env antes de produção."
        )

    logger.info("Database: %s", str(engine.url).split("@")[-1] if "@" in str(engine.url) else engine.url)
    Base.metadata.create_all(bind=engine)
    _migrate_schema()
    settings.data_path.mkdir(parents=True, exist_ok=True)
    settings.snapshots_path.mkdir(parents=True, exist_ok=True)
    settings.favorites_path.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == settings.admin_username).first()
        if not user:
            user = User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                role=ROLE_ADMIN,
                is_active=True,
            )
            db.add(user)
            db.commit()
            logger.info("Admin user created: %s", settings.admin_username)
        elif not getattr(user, "role", None):
            user.role = ROLE_ADMIN
            db.commit()
        get_or_create_settings(db)
        ensure_default_profiles(db)
        _ensure_default_store(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    seed_db()
    await monitor_worker.start()
    yield
    await monitor_worker.stop()


app = FastAPI(title="Pizza Pizza Eyes", version="1.1.0", lifespan=lifespan)
cfg = get_settings()

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(auth.router)
app.include_router(settings_api.router)
app.include_router(profiles.router)
app.include_router(stores.router)
app.include_router(users.router)
app.include_router(cameras.router)
app.include_router(alerts.router)
app.include_router(reports.router)

cfg.snapshots_path.mkdir(parents=True, exist_ok=True)
cfg.favorites_path.mkdir(parents=True, exist_ok=True)


@app.get("/api/health")
def health():
    return {"ok": True, "worker": monitor_worker.running, "db": "mysql" if "mysql" in cfg.database_url else "other"}


def _safe_media(path: str):
    full = (cfg.data_path / path).resolve()
    if not str(full).startswith(str(cfg.data_path.resolve())) or not full.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return FileResponse(full)


@app.get("/api/media/{path:path}")
def media_file(path: str, _: User = Depends(get_current_user)):
    return _safe_media(path)


@app.get("/media/snapshots/{path:path}")
def media_snapshots(path: str, _: User = Depends(get_current_user)):
    return _safe_media(f"snapshots/{path}")


@app.get("/media/favorites/{path:path}")
def media_favorites(path: str, _: User = Depends(get_current_user)):
    return _safe_media(f"favorites/{path}")
