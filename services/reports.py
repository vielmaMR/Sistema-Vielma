"""Cálculo de indicadores para reportes diarios y mensuales.

Diferencia órdenes creadas vs finalizadas vs entregadas en el periodo, excluye
nulos en promedios y separa montos aprobados de montos cobrados.
"""
from __future__ import annotations

from collections import Counter

from extensions import db
from models import WorkOrder, WorkSession, User
from services import timing
from utils.timezone import utcnow
import constants as C


def _avg(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None, 0
    return sum(vals) / len(vals), len(vals)


def build_report(start, end):
    """Construye el diccionario de indicadores para el rango [start, end) UTC."""
    now = utcnow()

    created = WorkOrder.query.filter(
        WorkOrder.created_at >= start, WorkOrder.created_at < end).all()
    finished = WorkOrder.query.filter(
        WorkOrder.finished_at >= start, WorkOrder.finished_at < end).all()
    delivered = WorkOrder.query.filter(
        WorkOrder.delivered_at >= start, WorkOrder.delivered_at < end).all()

    # Conteos basados en la fecha de ENTRADA a cada estado (status_history).
    from models import WorkOrderStatusHistory as H
    def count_entered(status):
        return (db.session.query(H.order_id)
                .filter(H.to_status == status, H.changed_at >= start, H.changed_at < end)
                .distinct().count())

    counts = {
        "created": len(created),
        "approved_client": count_entered(C.ST_APROBADO_CLIENTE),
        "confirmed": count_entered(C.ST_CONFIRMADO),
        "started": count_entered(C.ST_EN_TRABAJO),
        "finished": len(finished),
        "delivered": len(delivered),
        "rejected_cancelled": (count_entered(C.ST_RECHAZADO_CLIENTE) +
                               count_entered(C.ST_CANCELADO)),
    }

    # --- Tiempos (sobre órdenes finalizadas en el periodo con datos válidos) ---
    eff = []
    total_repair = []
    wait_approval = []
    pending_start = []
    finish_to_deliver = []
    for o in finished:
        eff.append(timing.effective_work_seconds(o, now))
        total_repair.append(timing.created_to_finished_seconds(o))
        wait_approval.append(timing.waiting_approval_seconds(o, now))
        pending_start.append(timing.pending_start_seconds(o, now))
        f2d = timing.finished_to_delivered_seconds(o)
        if f2d is not None:
            finish_to_deliver.append(f2d)

    avg_eff, n_eff = _avg(eff)
    avg_repair, n_repair = _avg(total_repair)
    avg_wait, n_wait = _avg(wait_approval)
    avg_pending, n_pending = _avg(pending_start)
    avg_f2d, n_f2d = _avg(finish_to_deliver)

    times = {
        "avg_effective": avg_eff, "n_effective": n_eff,
        "avg_repair": avg_repair, "n_repair": n_repair,
        "avg_wait_approval": avg_wait, "n_wait": n_wait,
        "avg_pending_start": avg_pending, "n_pending": n_pending,
        "avg_finish_to_deliver": avg_f2d, "n_f2d": n_f2d,
    }

    # Tiempo efectivo acumulado por empleado en el periodo.
    per_employee = _effective_by_employee(start, end, now)

    # --- Vehículos y servicios (sobre creadas en el periodo) ---
    vehicle_counter = Counter(o.vehicle_type for o in created)
    brand_counter = Counter((o.brand or "Sin marca").strip().title() for o in created)
    model_counter = Counter((o.model or "Sin modelo").strip().title() for o in created)
    worktype_counter = Counter(o.work_type_label for o in created)
    emp_order_counter = Counter(
        (o.assigned_to.full_name if o.assigned_to else "Sin asignar") for o in created)

    total_created = len(created) or 1
    vehicles = {
        "counts": {C.VEHICLE_TYPES.get(k, k): v for k, v in vehicle_counter.items()},
        "moto": vehicle_counter.get(C.VH_MOTO, 0),
        "auto": vehicle_counter.get(C.VH_AUTO, 0),
        "motocarro": vehicle_counter.get(C.VH_MOTOCARRO, 0),
    }
    brands = {
        "counts": dict(brand_counter.most_common()),
        "top": brand_counter.most_common(1)[0] if brand_counter else None,
    }
    worktypes = {
        "counts": dict(worktype_counter.most_common()),
        "top": worktype_counter.most_common(1)[0] if worktype_counter else None,
        "pct": {k: round(100 * v / total_created, 1)
                for k, v in worktype_counter.items()},
    }

    # --- Económicos ---
    approved_vals = [float(o.approved_amount) for o in finished
                     if o.approved_amount is not None]
    final_vals = [float(o.final_amount) for o in delivered
                  if o.final_amount is not None]
    avg_approved, n_approved = _avg(approved_vals)
    avg_final, n_final = _avg(final_vals)
    no_amount = sum(1 for o in finished if o.approved_amount is None)

    economics = {
        "avg_approved": avg_approved, "n_approved": n_approved,
        "avg_final": avg_final, "n_final": n_final,
        "total_approved": sum(approved_vals),
        "total_collected": sum(final_vals),
        "orders_without_amount": no_amount,
        "avg_by_worktype": _avg_amount_by(finished, lambda o: o.work_type_label),
        "avg_by_vehicle": _avg_amount_by(finished, lambda o: o.vehicle_label),
    }

    # Evolución por día (conteo de creadas) para gráfico.
    daily = _daily_series(created)

    return {
        "counts": counts,
        "times": times,
        "per_employee": per_employee,
        "vehicles": vehicles,
        "brands": brands,
        "models": dict(model_counter.most_common(15)),
        "worktypes": worktypes,
        "emp_orders": dict(emp_order_counter.most_common()),
        "economics": economics,
        "daily": daily,
        "created_orders": created,
    }


def _avg_amount_by(orders, keyfn):
    groups = {}
    for o in orders:
        if o.approved_amount is None:
            continue
        key = keyfn(o)
        groups.setdefault(key, []).append(float(o.approved_amount))
    return {k: round(sum(v) / len(v), 2) for k, v in groups.items() if v}


def _effective_by_employee(start, end, now):
    result = {}
    sessions = WorkSession.query.filter(WorkSession.started_at < end).all()
    names = {u.id: u.full_name for u in User.query.all()}
    for s in sessions:
        s_end = s.ended_at or now
        lo = max(s.started_at, start)
        hi = min(s_end, end)
        if hi > lo:
            name = names.get(s.user_id, f"Usuario {s.user_id}")
            result[name] = result.get(name, 0.0) + (hi - lo).total_seconds()
    return result


def _daily_series(created):
    from utils.timezone import to_local
    counter = Counter()
    for o in created:
        local = to_local(o.created_at)
        key = local.strftime("%Y-%m-%d") if local else "?"
        counter[key] += 1
    return dict(sorted(counter.items()))
