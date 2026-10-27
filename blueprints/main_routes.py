"""Rutas principales: enrutado al panel según rol y panel del empleado."""
from __future__ import annotations

from flask import Blueprint, render_template, redirect, url_for

from extensions import db
from models import WorkOrder
from auth import login_required, current_user
from services import timing
from utils.timezone import utcnow, local_day_bounds
from datetime import date
import constants as C

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    user = current_user()
    if user.is_jefe:
        return redirect(url_for("jefe.dashboard"))
    return redirect(url_for("main.employee_dashboard"))


@bp.route("/panel")
@login_required
def employee_dashboard():
    user = current_user()
    # Órdenes del empleado: creadas por él o asignadas a él.
    orders = (WorkOrder.query
              .filter((WorkOrder.assigned_to_id == user.id) |
                      (WorkOrder.created_by_id == user.id))
              .order_by(WorkOrder.updated_at.desc())
              .all())

    buckets = {
        "pendiente_inicio": [],
        "en_curso": [],
        "pausado": [],
        "espera": [],
        "finalizado": [],
        "otros": [],
    }
    for o in orders:
        if o.status == C.ST_CONFIRMADO:
            buckets["pendiente_inicio"].append(o)
        elif o.status == C.ST_EN_TRABAJO:
            buckets["en_curso"].append(o)
        elif o.status == C.ST_PAUSADO:
            buckets["pausado"].append(o)
        elif o.status in (C.ST_SOLICITADO, C.ST_ESPERA_APROBACION, C.ST_APROBADO_CLIENTE):
            buckets["espera"].append(o)
        elif o.status in (C.ST_FINALIZADO, C.ST_ENTREGADO):
            buckets["finalizado"].append(o)
        else:
            buckets["otros"].append(o)

    # Tiempo efectivo trabajado hoy por el empleado.
    today = date.today()
    start_utc, end_utc = local_day_bounds(today)
    effective_today = _effective_today(user.id, start_utc, end_utc)

    # Orden activa (sesión abierta) para mostrar cronómetro destacado.
    active_order = None
    for o in orders:
        if timing.active_session_for(o, user.id) is not None:
            active_order = o
            break

    return render_template("employee/dashboard.html",
                           buckets=buckets, effective_today=effective_today,
                           active_order=active_order)


def _effective_today(user_id, start_utc, end_utc):
    """Suma el tiempo efectivo de las sesiones del usuario que se solapan con hoy."""
    from models import WorkSession
    now = utcnow()
    total = 0.0
    sessions = (WorkSession.query
                .filter(WorkSession.user_id == user_id)
                .filter(WorkSession.started_at < end_utc)
                .all())
    for s in sessions:
        s_end = s.ended_at or now
        # Recorta el intervalo al rango del día.
        lo = max(s.started_at, start_utc)
        hi = min(s_end, end_utc)
        if hi > lo:
            total += (hi - lo).total_seconds()
    return total
