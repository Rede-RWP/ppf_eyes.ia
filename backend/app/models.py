from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # admin | gestor | operador
    role: Mapped[str] = mapped_column(String(32), default="admin", nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user")
    store_links: Mapped[list["StoreUser"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Store(Base):
    """Loja física (franquia / unidade)."""

    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    cnpj: Mapped[Optional[str]] = mapped_column(String(18), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    hours: Mapped[list["StoreHour"]] = relationship(
        back_populates="store", cascade="all, delete-orphan", order_by="StoreHour.weekday"
    )
    user_links: Mapped[list["StoreUser"]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )
    cameras: Mapped[list["Camera"]] = relationship(back_populates="store")


class StoreHour(Base):
    """Horário de funcionamento por dia (0=segunda … 6=domingo)."""

    __tablename__ = "store_hours"
    __table_args__ = (UniqueConstraint("store_id", "weekday", name="uq_store_weekday"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False, index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=seg … 6=dom
    opens_at: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # HH:MM
    closes_at: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)

    store: Mapped["Store"] = relationship(back_populates="hours")


class StoreUser(Base):
    """Lojas às quais o usuário tem acesso (gestor / operador)."""

    __tablename__ = "store_users"
    __table_args__ = (UniqueConstraint("user_id", "store_id", name="uq_user_store"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="store_links")
    store: Mapped["Store"] = relationship(back_populates="user_links")


class AuthSession(Base):
    """Sessão JWT revogável (jti)."""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    active_provider: Mapped[str] = mapped_column(String(32), default="openai")
    openai_api_key_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gemini_api_key_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    anthropic_api_key_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    openai_model: Mapped[str] = mapped_column(String(80), default="gpt-4o")
    gemini_model: Mapped[str] = mapped_column(String(80), default="gemini-2.0-flash")
    claude_model: Mapped[str] = mapped_column(String(80), default="claude-sonnet-4-5-20250929")
    analysis_interval_sec: Mapped[int] = mapped_column(Integer, default=30)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=5)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.6)
    # Monitoramento inteligente
    respect_store_hours: Mapped[bool] = mapped_column(Boolean, default=True)
    motion_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    motion_check_interval_sec: Mapped[int] = mapped_column(Integer, default=8)
    motion_sensitivity: Mapped[float] = mapped_column(Float, default=0.02)
    motion_pixel_threshold: Mapped[int] = mapped_column(Integer, default=25)
    motion_cooldown_sec: Mapped[int] = mapped_column(Integer, default=45)
    ai_heartbeat_sec: Mapped[int] = mapped_column(Integer, default=300)
    # Global defaults (used when camera has no profile)
    rule_sem_touca: Mapped[bool] = mapped_column(Boolean, default=True)
    rule_fardamento: Mapped[bool] = mapped_column(Boolean, default=True)
    rule_sem_epi: Mapped[bool] = mapped_column(Boolean, default=False)
    base_prompt: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class MonitorProfile(Base):
    """Perfil de ambiente: regras e fardamento específicos por tipo de local."""

    __tablename__ = "monitor_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Ambiente livre: cozinha, escritorio, recepcao, delivery, salao, etc.
    environment_type: Mapped[str] = mapped_column(String(80), default="geral")
    rule_sem_touca: Mapped[bool] = mapped_column(Boolean, default=False)
    rule_fardamento: Mapped[bool] = mapped_column(Boolean, default=False)
    rule_sem_epi: Mapped[bool] = mapped_column(Boolean, default=False)
    # Celular / tempo de espera
    rule_celular: Mapped[bool] = mapped_column(Boolean, default=False)
    phone_max_minutes: Mapped[int] = mapped_column(Integer, default=5)
    rule_tempo_espera: Mapped[bool] = mapped_column(Boolean, default=False)
    wait_max_minutes: Mapped[int] = mapped_column(Integer, default=10)
    # Ex.: "camisa preta Pizza Pizza + calça preta" / "jaleco branco + touca"
    uniform_expected: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Notas extras injetadas no prompt (cores da marca, exceções, etc.)
    extra_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Se preenchido, substitui o prompt global só para este perfil
    custom_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    cameras: Mapped[list["Camera"]] = relationship(back_populates="profile")


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    rtsp_url: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    store_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("stores.id"), nullable=True, index=True
    )
    profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("monitor_profiles.id"), nullable=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    interval_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="unknown")
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_frame_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    store: Mapped[Optional["Store"]] = relationship(back_populates="cameras")
    profile: Mapped[Optional["MonitorProfile"]] = relationship(back_populates="cameras")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="camera")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), nullable=False)
    violations: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    snapshot_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # tp | fp
    feedback_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    favorited: Mapped[bool] = mapped_column(Boolean, default=False)
    favorite_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    favorited_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Quando apagar as imagens deste alerta (favoritos ignoram até desfavoritar)
    images_expire_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    camera: Mapped["Camera"] = relationship(back_populates="alerts")


class PromptExample(Base):
    __tablename__ = "prompt_examples"
    __table_args__ = (UniqueConstraint("label", "kind", name="uq_example_label_kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    image_path: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AnalysisLog(Base):
    __tablename__ = "analysis_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FrameObservation(Base):
    """Snapshot estruturado de cada análise (para relatórios e tempo)."""

    __tablename__ = "frame_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), nullable=False)
    person_count: Mapped[int] = mapped_column(Integer, default=0)
    phone_in_use: Mapped[bool] = mapped_column(Boolean, default=False)
    people_waiting: Mapped[bool] = mapped_column(Boolean, default=False)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    violations: Mapped[str] = mapped_column(Text, default="[]")
    description: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    snapshot_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PresenceSession(Base):
    """Sessão contínua de presença / uso de celular por câmera."""

    __tablename__ = "presence_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # waiting | phone
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    alerted: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ReportChatMessage(Base):
    __tablename__ = "report_chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
