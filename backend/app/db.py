from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
settings.data_path.mkdir(parents=True, exist_ok=True)
settings.snapshots_path.mkdir(parents=True, exist_ok=True)
settings.favorites_path.mkdir(parents=True, exist_ok=True)

url = settings.database_url
connect_args = {}
engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 28000,
}

if url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine_kwargs = {"connect_args": connect_args}
elif url.startswith("mysql"):
    engine_kwargs["connect_args"] = {"charset": "utf8mb4"}

engine = create_engine(url, **engine_kwargs)


@event.listens_for(engine, "connect")
def _on_connect(dbapi_connection, connection_record):  # noqa: ARG001
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
