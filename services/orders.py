"""Lógica de negocio de las órdenes: numeración, transiciones y sesiones.

Todas las funciones que cambian estado validan la transición en el backend y
registran historial + auditoría. Las transiciones inválidas lanzan OrderError.
"""
from __future__ import annotations

from sqlalchemy import func

from extensions import db
from models import (WorkOrder, WorkOrderStatusHistory, WorkSession,
                    WorkOrderApproval)
from services.audit import log_action
from services import timing
from utils.timezone import utcnow
import constants as C


class OrderError(Exception):
    """Error de regla de negocio (transición inválida, permiso, etc.)."""


def next_order_number() -> int:
    """Número correlativo único. Se calcula dentro de la transacción de creación."""
    current_max = db.session.query(func.max(WorkOrder.number)).scalar()
    return (current_max or 0) + 1


def record_status_change(order, new_status, user, note=None):
    """Registra el cambio en el historial y actualiza el estado de la orden."""
    prev = order.status
    entry = WorkOrderStatusHistory(
        order_id=order.id,
        from_status=prev,
        to_status=new_status,
        changed_by_id=(user.id if user else None),
        note=note,
    )
    db.session.add(entry)
    order.status = new_status
    order.status_since = utcnow()


def transition(order, new_status, user, note=None, *, force=False):
    """Transición genérica validada. Lanza OrderError si no está permitida."""
    if not force and not C.can_transition(order.status, new_status):
        raise OrderError(
            f"Transición no permitida: {C.STATUS_LABELS.get(order.status, order.status)} "
            f"→ {C.STATUS_LABELS.get(new_status, new_status)}."
        )
    record_status_change(order, new_status, user, note)
    log_action(user, "cambio_estado", "work_order", order.id,
               f"{order.status} (desde {order.status})" if False else
               f"-> {new_status}" + (f": {note}" if note else ""))


def create_order(user, data: dict) -> WorkOrder:
    """Crea una orden en estado Solicitado dentro de una transacción."""
    number = next_order_number()
    order = WorkOrder(number=number, created_by_id=user.id, status=C.ST_SOLICITADO,
                      status_since=utcnow())
    # Si el empleado no se asigna explícitamente, se asigna a sí mismo por defecto.
    assigned = data.get("assigned_to_id")
    order.assigned_to_id = assigned if assigned else (user.id if not user.is_jefe else None)
    _apply_order_fields(order, data)
    db.session.add(order)
    db.session.flush()  # obtiene order.id

    db.session.add(WorkOrderStatusHistory(
        order_id=order.id, from_status=None, to_status=C.ST_SOLICITADO,
        changed_by_id=user.id, note="Orden creada"))
    log_action(user, "crear_orden", "work_order", order.id, f"Orden #{number}")
    return order


def _apply_order_fields(order, data):
    """Copia los campos editables de la orden desde un dict de formulario validado."""
    for field in ("vehicle_type", "brand", "model", "plate", "client_name",
                  "client_phone", "work_type", "work_type_other",
                  "problem_description", "diagnosis", "tasks_detail",
                  "parts_used", "observations", "budget_notes"):
        if field in data:
            setattr(order, field, data[field])
    for field in ("year", "mileage"):
        if field in data:
            setattr(order, field, data[field])
    for field in ("estimated_budget", "estimated_delivery"):
        if field in data:
            setattr(order, field, data[field])


def send_for_approval(order, user, estimated_budget=None, note=None):
    if estimated_budget is not None:
        order.estimated_budget = estimated_budget
    db.session.add(WorkOrderApproval(
        order_id=order.id, kind="presupuesto", amount=estimated_budget,
        note=note, registered_by_id=user.id))
    transition(order, C.ST_ESPERA_APROBACION, user, note)


def register_client_decision(order, user, decision, note=None):
    """decision: 'aprobado' | 'rechazado'. Registra la decisión externa del cliente."""
    if decision not in ("aprobado", "rechazado"):
        raise OrderError("Decisión de cliente inválida.")
    db.session.add(WorkOrderApproval(
        order_id=order.id, kind="decision_cliente", decision=decision,
        note=note, registered_by_id=user.id))
    if decision == "aprobado":
        transition(order, C.ST_APROBADO_CLIENTE, user, note)
    else:
        transition(order, C.ST_RECHAZADO_CLIENTE, user, note)
    log_action(user, "decision_cliente", "work_order", order.id, decision)


def confirm_order(order, user, approved_amount, assigned_to_id=None, note=None):
    """El jefe confirma: requiere aprobación de cliente registrada."""
    if not user.is_jefe:
        raise OrderError("Solo el jefe puede confirmar órdenes.")
    if not order.has_client_approval:
        raise OrderError("No se puede confirmar sin la aprobación del cliente registrada.")
    if approved_amount is None:
        raise OrderError("Debe registrar el monto aprobado.")
    order.approved_amount = approved_amount
    if assigned_to_id:
        order.assigned_to_id = assigned_to_id
    db.session.add(WorkOrderApproval(
        order_id=order.id, kind="confirmacion_jefe", amount=approved_amount,
        note=note, registered_by_id=user.id))
    transition(order, C.ST_CONFIRMADO, user, note)
    log_action(user, "confirmar_orden", "work_order", order.id,
               f"monto={approved_amount}")


def start_work(order, user):
    """Inicia (o reanuda) el trabajo del empleado: abre una sesión."""
    if order.status not in (C.ST_CONFIRMADO, C.ST_PAUSADO):
        raise OrderError("La orden no está lista para iniciar trabajo.")
    existing = timing.active_session_for(order, user.id)
    if existing:
        raise OrderError("Ya tienes una sesión de trabajo activa en esta orden.")
    session = WorkSession(user_id=user.id, started_at=utcnow())
    # Asociar vía la relación para que order.sessions (ya cargada) incluya esta
    # sesión de inmediato; así pause/finish la encuentran sin depender del flush.
    order.sessions.append(session)
    db.session.add(session)
    db.session.flush()
    if order.work_started_at is None:
        order.work_started_at = utcnow()
    if order.status != C.ST_EN_TRABAJO:
        transition(order, C.ST_EN_TRABAJO, user, "Inicio/reanudación de trabajo")
    log_action(user, "iniciar_trabajo", "work_order", order.id)


def pause_work(order, user, reason=None):
    """Pausa: cierra la sesión activa del usuario. El estado pasa a Pausado si
    no quedan otras sesiones activas."""
    session = timing.active_session_for(order, user.id)
    if not session:
        raise OrderError("No tienes una sesión activa para pausar.")
    session.ended_at = utcnow()
    session.pause_reason = reason
    # Si no quedan sesiones activas de nadie, la orden queda pausada.
    if timing.any_active_session(order) is None and order.status == C.ST_EN_TRABAJO:
        transition(order, C.ST_PAUSADO, user, f"Pausa: {reason}" if reason else "Pausa")
    log_action(user, "pausar_trabajo", "work_order", order.id, reason)


def finish_work(order, user, data: dict):
    """Finaliza el trabajo: cierra sesiones activas y pasa a Finalizado."""
    if order.status not in (C.ST_EN_TRABAJO, C.ST_PAUSADO):
        raise OrderError("La orden no está en trabajo.")
    now = utcnow()
    for s in order.sessions:
        if s.ended_at is None:
            s.ended_at = now
    # Campos de cierre que el empleado puede completar.
    for field in ("diagnosis", "parts_used", "observations", "tasks_detail"):
        if data.get(field) is not None:
            setattr(order, field, data[field])
    if data.get("summary"):
        existing = order.observations or ""
        order.observations = (existing + "\n" if existing else "") + \
            f"Resumen final: {data['summary']}"
    order.finished_at = now
    transition(order, C.ST_FINALIZADO, user, "Trabajo finalizado")
    log_action(user, "finalizar_trabajo", "work_order", order.id)


def set_final_amount(order, user, final_amount):
    """Solo el jefe puede registrar el monto final cobrado."""
    if not user.is_jefe:
        raise OrderError("Solo el jefe puede registrar el monto cobrado.")
    order.final_amount = final_amount
    log_action(user, "registrar_cobro", "work_order", order.id, f"final={final_amount}")


def deliver_order(order, user, note=None):
    if not user.is_jefe:
        raise OrderError("Solo el jefe puede entregar/cerrar órdenes.")
    if order.status != C.ST_FINALIZADO:
        raise OrderError("Solo se pueden entregar órdenes finalizadas.")
    order.delivered_at = utcnow()
    transition(order, C.ST_ENTREGADO, user, note)
    log_action(user, "entregar_orden", "work_order", order.id)


def cancel_order(order, user, note=None):
    if not user.is_jefe:
        raise OrderError("Solo el jefe puede cancelar órdenes.")
    if order.status in C.CLOSED_STATES:
        raise OrderError("La orden ya está cerrada.")
    # Cierra sesiones activas: no debe seguir acumulando tiempo.
    now = utcnow()
    for s in order.sessions:
        if s.ended_at is None:
            s.ended_at = now
    transition(order, C.ST_CANCELADO, user, note, force=True)
    log_action(user, "cancelar_orden", "work_order", order.id, note)


def reopen_order(order, user, note=None):
    """Reapertura auditada de una orden finalizada/entregada (solo jefe)."""
    if not user.is_jefe:
        raise OrderError("Solo el jefe puede reabrir órdenes.")
    if order.status == C.ST_ENTREGADO:
        order.delivered_at = None
        transition(order, C.ST_FINALIZADO, user, note or "Reapertura: entregada -> finalizada")
    elif order.status == C.ST_FINALIZADO:
        order.finished_at = None
        transition(order, C.ST_EN_TRABAJO, user, note or "Reapertura: finalizada -> en trabajo")
    else:
        raise OrderError("Solo se pueden reabrir órdenes finalizadas o entregadas.")
    log_action(user, "reabrir_orden", "work_order", order.id, note)
