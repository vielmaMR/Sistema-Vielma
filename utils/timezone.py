"""Utilidades de fecha/hora.

Regla del sistema: TODAS las marcas de tiempo se almacenan en UTC (naive, es
decir, sin tzinfo pero representando UTC) para que los cálculos de duración sean
correctos y no dependan del horario de verano. Para mostrar al usuario se
convierten a la zona horaria del taller (America/Asuncion por defecto).
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

try:
    # Python 3.9+ incluye zoneinfo en la librería estándar.
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

_DEFAULT_TZ = "America/Asuncion"
# Asunción usa UTC-3 (sin DST desde 2024 según decisión gubernamental; antes UTC-4/-3).
# zoneinfo maneja esto automáticamente si hay base de datos tz; si no, usamos -3 fijo.
_FALLBACK_OFFSET = timedelta(hours=-3)


def _get_zone(tz_name: str):
    if ZoneInfo is not None:
        try:
            return ZoneInfo(tz_name)
        except Exception:
            return None
    return None


def utcnow() -> datetime:
    """Marca de tiempo actual en UTC, naive (sin tzinfo). Es lo que se guarda."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_local(dt: datetime | None, tz_name: str = _DEFAULT_TZ) -> datetime | None:
    """Convierte una marca UTC naive (guardada) a la zona local del taller."""
    if dt is None:
        return None
    aware = dt.replace(tzinfo=timezone.utc)
    zone = _get_zone(tz_name)
    if zone is not None:
        return aware.astimezone(zone)
    return aware.astimezone(timezone(_FALLBACK_OFFSET))


def format_local(dt: datetime | None, tz_name: str = _DEFAULT_TZ,
                 fmt: str = "%d/%m/%Y %H:%M") -> str:
    local = to_local(dt, tz_name)
    if local is None:
        return "—"
    return local.strftime(fmt)


def local_day_bounds(local_date, tz_name: str = _DEFAULT_TZ):
    """Dado un date local, devuelve (inicio_utc, fin_utc) naive para filtrar.

    Devuelve el rango [00:00, 24:00) de ese día local, expresado en UTC naive.
    """
    zone = _get_zone(tz_name)
    if zone is not None:
        start_local = datetime(local_date.year, local_date.month, local_date.day,
                               0, 0, 0, tzinfo=zone)
    else:
        start_local = datetime(local_date.year, local_date.month, local_date.day,
                               0, 0, 0, tzinfo=timezone(_FALLBACK_OFFSET))
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def local_month_bounds(year: int, month: int, tz_name: str = _DEFAULT_TZ):
    """Rango [inicio, fin) UTC naive que cubre un mes local completo."""
    zone = _get_zone(tz_name)
    tzinfo = zone if zone is not None else timezone(_FALLBACK_OFFSET)
    start_local = datetime(year, month, 1, 0, 0, 0, tzinfo=tzinfo)
    if month == 12:
        end_local = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=tzinfo)
    else:
        end_local = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=tzinfo)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def format_duration(seconds: float | int | None) -> str:
    """Formatea segundos a '2h 15m' / '45m' / '30s' para la interfaz."""
    if seconds is None:
        return "—"
    seconds = int(seconds)
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return f"{seconds}s"
    minutes, _ = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours == 0:
        return f"{minutes}m"
    return f"{hours}h {minutes:02d}m"
