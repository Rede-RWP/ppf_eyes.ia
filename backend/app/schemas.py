from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str = "admin"
    display_name: Optional[str] = None
    store_ids: List[int] = Field(default_factory=list)
    is_active: bool = True

    class Config:
        from_attributes = True


class StoreHourIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    opens_at: Optional[str] = None
    closes_at: Optional[str] = None
    is_closed: bool = False


class StoreHourOut(BaseModel):
    weekday: int
    label: str
    opens_at: Optional[str] = None
    closes_at: Optional[str] = None
    is_closed: bool = False


class StoreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    cnpj: Optional[str] = None
    is_active: bool = True
    hours: Optional[List[StoreHourIn]] = None


class StoreUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    cnpj: Optional[str] = None
    is_active: Optional[bool] = None
    hours: Optional[List[StoreHourIn]] = None


class StoreOut(BaseModel):
    id: int
    name: str
    cnpj: Optional[str] = None
    is_active: bool
    hours: List[StoreHourOut] = Field(default_factory=list)
    cameras_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="operador")
    display_name: Optional[str] = Field(default=None, max_length=120)
    store_ids: List[int] = Field(default_factory=list)
    is_active: bool = True


class UserUpdate(BaseModel):
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)
    role: Optional[str] = None
    display_name: Optional[str] = Field(default=None, max_length=120)
    store_ids: Optional[List[int]] = None
    is_active: Optional[bool] = None


class UserAdminOut(BaseModel):
    id: int
    username: str
    role: str
    display_name: Optional[str] = None
    store_ids: List[int] = Field(default_factory=list)
    store_names: List[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SettingsOut(BaseModel):
    active_provider: str
    openai_model: str
    gemini_model: str
    claude_model: str
    analysis_interval_sec: int
    cooldown_minutes: int
    confidence_threshold: float
    respect_store_hours: bool = True
    motion_enabled: bool = True
    motion_check_interval_sec: int = 8
    motion_sensitivity: float = 0.02
    motion_pixel_threshold: int = 25
    motion_cooldown_sec: int = 45
    ai_heartbeat_sec: int = 300
    rule_sem_touca: bool
    rule_fardamento: bool
    rule_sem_epi: bool
    base_prompt: str
    openai_api_key_set: bool
    gemini_api_key_set: bool
    anthropic_api_key_set: bool
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SettingsUpdate(BaseModel):
    active_provider: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    gemini_model: Optional[str] = None
    claude_model: Optional[str] = None
    analysis_interval_sec: Optional[int] = Field(default=None, ge=5, le=3600)
    cooldown_minutes: Optional[int] = Field(default=None, ge=0, le=240)
    confidence_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    respect_store_hours: Optional[bool] = None
    motion_enabled: Optional[bool] = None
    motion_check_interval_sec: Optional[int] = Field(default=None, ge=3, le=120)
    motion_sensitivity: Optional[float] = Field(default=None, ge=0.001, le=0.2)
    motion_pixel_threshold: Optional[int] = Field(default=None, ge=5, le=80)
    motion_cooldown_sec: Optional[int] = Field(default=None, ge=5, le=600)
    ai_heartbeat_sec: Optional[int] = Field(default=None, ge=0, le=3600)
    rule_sem_touca: Optional[bool] = None
    rule_fardamento: Optional[bool] = None
    rule_sem_epi: Optional[bool] = None
    base_prompt: Optional[str] = None


class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    rtsp_url: str = Field(min_length=8)
    location: Optional[str] = None
    store_id: int
    profile_id: Optional[int] = None
    enabled: bool = True
    interval_sec: Optional[int] = Field(default=None, ge=5, le=3600)


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    rtsp_url: Optional[str] = Field(default=None, min_length=8)
    location: Optional[str] = None
    store_id: Optional[int] = None
    profile_id: Optional[int] = None
    enabled: Optional[bool] = None
    interval_sec: Optional[int] = Field(default=None, ge=5, le=3600)


class CameraOut(BaseModel):
    id: int
    name: str
    rtsp_url_masked: str
    location: Optional[str]
    store_id: Optional[int] = None
    store_name: Optional[str] = None
    profile_id: Optional[int] = None
    profile_name: Optional[str] = None
    enabled: bool
    interval_sec: Optional[int]
    status: str
    last_seen_at: Optional[datetime]
    last_frame_path: Optional[str]
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CameraTestOut(BaseModel):
    ok: bool
    message: str
    preview_path: Optional[str] = None


class AlertOut(BaseModel):
    id: int
    camera_id: int
    camera_name: Optional[str] = None
    violations: List[str]
    description: str
    confidence: float
    snapshot_path: Optional[str]
    feedback: Optional[str]
    feedback_comment: Optional[str] = None
    favorited: bool = False
    favorite_path: Optional[str] = None
    favorited_at: Optional[datetime] = None
    created_at: datetime


class AlertFeedbackIn(BaseModel):
    feedback: str  # tp | fp | clear
    comment: Optional[str] = None  # obrigatório para fp


class AlertFavoriteIn(BaseModel):
    favorited: bool


class DashboardOut(BaseModel):
    cameras_total: int
    cameras_online: int
    cameras_offline: int
    alerts_today: int
    recent_alerts: List[AlertOut]


class DetectionBox(BaseModel):
    """Caixa da pessoa fora do padrão (coordenadas normalizadas 0–1: x1,y1,x2,y2)."""

    label: str = "pessoa"
    confidence: float = 0.0
    box: List[float] = Field(default_factory=list)  # [x1, y1, x2, y2]
    flagged: bool = True


class VisionResult(BaseModel):
    is_anomaly: bool = False
    violations: List[str] = Field(default_factory=list)
    description: str = ""
    confidence: float = 0.0
    person_count: int = 0
    phone_in_use: bool = False
    people_waiting: bool = False
    detections: List[DetectionBox] = Field(default_factory=list)

class ReportChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ReportChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ReportChatOut(BaseModel):
    reply: str
    messages: List[ReportChatMessageOut]


class ParameterItem(BaseModel):
    key: str
    label: str
    description: str
    where: str
    default: str


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    environment_type: str = Field(default="geral", max_length=80)
    description: Optional[str] = None
    rule_sem_touca: bool = False
    rule_fardamento: bool = False
    rule_sem_epi: bool = False
    rule_celular: bool = False
    phone_max_minutes: int = Field(default=5, ge=1, le=240)
    rule_tempo_espera: bool = False
    wait_max_minutes: int = Field(default=10, ge=1, le=480)
    uniform_expected: Optional[str] = None
    extra_instructions: Optional[str] = None
    custom_prompt: Optional[str] = None
    is_default: bool = False


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    environment_type: Optional[str] = Field(default=None, max_length=80)
    description: Optional[str] = None
    rule_sem_touca: Optional[bool] = None
    rule_fardamento: Optional[bool] = None
    rule_sem_epi: Optional[bool] = None
    rule_celular: Optional[bool] = None
    phone_max_minutes: Optional[int] = Field(default=None, ge=1, le=240)
    rule_tempo_espera: Optional[bool] = None
    wait_max_minutes: Optional[int] = Field(default=None, ge=1, le=480)
    uniform_expected: Optional[str] = None
    extra_instructions: Optional[str] = None
    custom_prompt: Optional[str] = None
    is_default: Optional[bool] = None


class ProfileOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    environment_type: str
    rule_sem_touca: bool
    rule_fardamento: bool
    rule_sem_epi: bool
    rule_celular: bool = False
    phone_max_minutes: int = 5
    rule_tempo_espera: bool = False
    wait_max_minutes: int = 10
    uniform_expected: Optional[str]
    extra_instructions: Optional[str]
    custom_prompt: Optional[str]
    is_default: bool
    cameras_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
