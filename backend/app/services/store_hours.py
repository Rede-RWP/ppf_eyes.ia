from __future__ import annotations

from datetime import datetime, time
from typing import Optional, TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from app.models import Store


def _parse_hhmm(value: Optional[str]) -> Optional[time]:
    if not value:
        return None
    parts = str(value).strip().split(":")
    if len(parts) < 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return time(hour=h, minute=m)


def local_now(timezone_name: str = "America/Sao_Paulo") -> datetime:
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("America/Sao_Paulo")
    return datetime.now(tz)


def is_store_open(
    store: Optional["Store"],
    *,
    timezone_name: str = "America/Sao_Paulo",
    now: Optional[datetime] = None,
) -> bool:
    """Retorna True se a loja está no horário de funcionamento local.

    - Sem loja / sem horários cadastrados → considera aberta (não bloqueia)
    - Loja inativa → fechada
    - Dia marcado is_closed → fechada
    """
    if store is None:
        return True
    if not getattr(store, "is_active", True):
        return False

    hours = list(getattr(store, "hours", None) or [])
    if not hours:
        return True

    now_local = now or local_now(timezone_name)
    if now_local.tzinfo is None:
        now_local = now_local.replace(tzinfo=ZoneInfo(timezone_name))

    weekday = now_local.weekday()  # 0=segunda … 6=domingo (igual StoreHour)
    by_day = {h.weekday: h for h in hours}
    row = by_day.get(weekday)
    if row is None:
        return False
    if bool(row.is_closed):
        return False

    opens = _parse_hhmm(row.opens_at)
    closes = _parse_hhmm(row.closes_at)
    if opens is None or closes is None:
        return False

    current = now_local.time().replace(second=0, microsecond=0)
    # Janela normal (ex.: 10:00–22:00)
    if opens <= closes:
        return opens <= current < closes
    # Overnight (ex.: 18:00–02:00)
    return current >= opens or current < closes
