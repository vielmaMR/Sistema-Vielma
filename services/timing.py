"""Cálculo de tiempos de una orden a partir del historial de estados y sesiones.

Los tiempos NO se derivan del estado actual, sino del historial completo:
- status_history para los periodos en cada estado (tiempo calendario / espera).
- work_sessions para el tiempo efectivo de trabajo (suma de intervalos).
"""
from __future__ import annotations

from utils.timezone import utcnow
import constants as C


def effective_work_seconds(order, now=None) -> float:
    """Suma del tiempo efectivo de trabajo (todas las sesiones, todos los empleados)."""
    now = now or utcnow()
    total = 0.0
    for s in order.sessions:
        total += s.duration_seconds(now)
    return total


def effective_work_seconds_by_user(order, now=None) -> dict:
    now = now or utcnow()
    result = {}
    for s in order.sessions:
        result[s.user_id] = result.get(s.user_id, 0.0) + s.duration_seconds(now)
    return result


def _status_intervals(order, now=None):
    """Devuelve lista de (estado, segundos) para cada periodo del historial."""
    now = now or utcnow()
    history = sorted(order.status_history, key=lambda h: h.changed_at)
    intervals = []
    for i, h in enumerate(history):
        start = h.changed_at
        end = history[i + 1].changed_at if i + 1 < len(history) else now
        # Una orden cerrada no sigue acumulando tiempo del último estado abierto.
        if i + 1 == len(history) and order.status in C.CLOSED_STATES:
            # El último tramo se congela en el momento del cierre.
            end = order.delivered_at or order.finished_at or h.changed_at
            if end < start:
                end = start
        intervals.append((h.to_status, max(0.0, (end - start).total_seconds())))
    return intervals


def seconds_in_status(order, status, now=None) -> float:
    total = 0.0
    for st, secs in _status_intervals(order, now):
        if st == status:
            total += secs
    return total


def total_pause_seconds(order, now=None) -> float:
    """Tiempo total en estado pausado."""
    return seconds_in_status(order, C.ST_PAUSADO, now)


def waiting_approval_seconds(order, now=None) -> float:
    return seconds_in_status(order, C.ST_ESPERA_APROBACION, now)


def pending_start_seconds(order, now=None) -> float:
    return seconds_in_status(order, C.ST_CONFIRMADO, now)


def calendar_seconds(order, now=None) -> float:
    """Tiempo total desde la creación hasta ahora (o hasta el cierre)."""
    now = now or utcnow()
    end = now
    if order.status in C.CLOSED_STATES:
        end = order.delivered_at or order.finished_at or now
    return max(0.0, (end - order.created_at).total_seconds())


def created_to_finished_seconds(order) -> float | None:
    if order.finished_at is None:
        return None
    return max(0.0, (order.finished_at - order.created_at).total_seconds())


def finished_to_delivered_seconds(order) -> float | None:
    if order.finished_at is None or order.delivered_at is None:
        return None
    return max(0.0, (order.delivered_at - order.finished_at).total_seconds())


def created_to_delivered_seconds(order) -> float | None:
    if order.delivered_at is None:
        return None
    return max(0.0, (order.delivered_at - order.created_at).total_seconds())


def order_timing_summary(order, now=None) -> dict:
    """Resumen completo de tiempos para mostrar en la ficha de la orden."""
    now = now or utcnow()
    return {
        "effective_work": effective_work_seconds(order, now),
        "pause": total_pause_seconds(order, now),
        "waiting_approval": waiting_approval_seconds(order, now),
        "pending_start": pending_start_seconds(order, now),
        "calendar": calendar_seconds(order, now),
        "created_to_finished": created_to_finished_seconds(order),
        "finished_to_delivered": finished_to_delivered_seconds(order),
        "created_to_delivered": created_to_delivered_seconds(order),
    }


def active_session_for(order, user_id):
    """Devuelve la sesión activa (sin cerrar) del usuario en la orden, si existe."""
    for s in order.sessions:
        if s.user_id == user_id and s.ended_at is None:
            return s
    return None


def any_active_session(order):
    for s in order.sessions:
        if s.ended_at is None:
            return s
    return None
