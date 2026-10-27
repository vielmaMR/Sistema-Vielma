"""Rutas de órdenes de trabajo: creación, detalle, edición y transiciones.

Todos los permisos se validan en el servidor (no basta con ocultar botones).
"""
from __future__ import annotations

from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, abort)

from extensions import db
from models import WorkOrder, User, WorkOrderNote
from auth import login_required, current_user
from forms import (OrderForm, ApprovalForm, ClientDecisionForm, ConfirmForm,
                   PauseForm, FinishForm, FinalAmountForm, SimpleNoteForm)
from services import orders as svc
from services import timing
from services.orders import OrderError
from services.audit import log_action
import constants as C

bp = Blueprint("orders", __name__, url_prefix="/ordenes")


def _get_order_or_404(order_id):
    order = db.session.get(WorkOrder, order_id)
    if order is None:
        abort(404)
    return order


def _can_view(order, user):
    """El jefe ve todo. El empleado ve las creadas por él o asignadas a él."""
    if user.is_jefe:
        return True
    return order.created_by_id == user.id or order.assigned_to_id == user.id


def _can_edit_fields(order, user):
    """Quién puede editar datos generales/diagnóstico de la orden."""
    if order.status in C.CLOSED_STATES:
        return user.is_jefe  # solo jefe, y con reapertura auditada para cambios de fondo
    if user.is_jefe:
        return True
    # Empleado: puede editar mientras participe y no esté cerrada.
    return order.created_by_id == user.id or order.assigned_to_id == user.id


def _employee_choices(include_empty=True):
    employees = User.query.filter_by(is_active=True).order_by(User.full_name).all()
    choices = [(u.id, f"{u.full_name} ({u.username})") for u in employees]
    if include_empty:
        choices = [(0, "— Sin asignar —")] + choices
    return choices


@bp.route("/nueva", methods=["GET", "POST"])
@login_required
def create():
    user = current_user()
    form = OrderForm()
    form.assigned_to_id.choices = _employee_choices()
    if not user.is_jefe:
        # El empleado no asigna; se asigna a sí mismo por defecto.
        del form.assigned_to_id

    if form.validate_on_submit():
        data = _collect_order_data(form, user)
        try:
            order = svc.create_order(user, data)
            db.session.commit()
            flash(f"Orden #{order.number} creada.", "success")
            return redirect(url_for("orders.detail", order_id=order.id))
        except OrderError as e:
            db.session.rollback()
            flash(str(e), "danger")
    return render_template("orders/form.html", form=form, order=None,
                           is_jefe=user.is_jefe)


@bp.route("/<int:order_id>/editar", methods=["GET", "POST"])
@login_required
def edit(order_id):
    user = current_user()
    order = _get_order_or_404(order_id)
    if not _can_view(order, user):
        abort(403)
    if not _can_edit_fields(order, user):
        flash("No puedes editar esta orden en su estado actual.", "warning")
        return redirect(url_for("orders.detail", order_id=order.id))

    form = OrderForm(obj=order)
    if user.is_jefe:
        form.assigned_to_id.choices = _employee_choices()
        if request.method == "GET":
            form.assigned_to_id.data = order.assigned_to_id or 0
    else:
        del form.assigned_to_id

    if form.validate_on_submit():
        data = _collect_order_data(form, user, for_edit=True)
        svc._apply_order_fields(order, data)
        if user.is_jefe and "assigned_to_id" in data:
            order.assigned_to_id = data["assigned_to_id"]
        log_action(user, "editar_orden", "work_order", order.id)
        db.session.commit()
        flash("Orden actualizada.", "success")
        return redirect(url_for("orders.detail", order_id=order.id))
    return render_template("orders/form.html", form=form, order=order,
                           is_jefe=user.is_jefe)


def _collect_order_data(form, user, for_edit=False):
    data = {
        "vehicle_type": form.vehicle_type.data,
        "brand": form.brand.data,
        "model": form.model.data,
        "year": form.year.data,
        "plate": form.plate.data,
        "mileage": form.mileage.data,
        "client_name": form.client_name.data,
        "client_phone": form.client_phone.data,
        "work_type": form.work_type.data,
        "work_type_other": form.work_type_other.data if form.work_type.data == "otro" else None,
        "problem_description": form.problem_description.data,
        "diagnosis": form.diagnosis.data,
        "tasks_detail": form.tasks_detail.data,
        "parts_used": form.parts_used.data,
        "observations": form.observations.data,
        "estimated_delivery": form.estimated_delivery.data,
        "estimated_budget": form.estimated_budget.data,
    }
    if user.is_jefe and hasattr(form, "assigned_to_id"):
        val = form.assigned_to_id.data
        data["assigned_to_id"] = val if val else None
    return data


@bp.route("/<int:order_id>")
@login_required
def detail(order_id):
    user = current_user()
    order = _get_order_or_404(order_id)
    if not _can_view(order, user):
        abort(403)

    timing_summary = timing.order_timing_summary(order)
    by_user = timing.effective_work_seconds_by_user(order)
    user_map = {u.id: u for u in User.query.all()}
    active_session = timing.active_session_for(order, user.id)

    return render_template(
        "orders/detail.html",
        order=order,
        timing=timing_summary,
        by_user=by_user,
        user_map=user_map,
        active_session=active_session,
        approval_form=ApprovalForm(),
        client_form=ClientDecisionForm(),
        confirm_form=_prepared_confirm_form(order),
        pause_form=PauseForm(),
        finish_form=FinishForm(obj=order),
        final_form=FinalAmountForm(obj=order),
        note_form=SimpleNoteForm(),
        can_edit=_can_edit_fields(order, user),
    )


def _prepared_confirm_form(order):
    form = ConfirmForm()
    form.assigned_to_id.choices = _employee_choices(include_empty=False)
    if order.assigned_to_id:
        form.assigned_to_id.data = order.assigned_to_id
    if order.approved_amount is not None:
        form.approved_amount.data = order.approved_amount
    return form


# ----------------- Transiciones de estado -----------------

@bp.route("/<int:order_id>/enviar-aprobacion", methods=["POST"])
@login_required
def send_for_approval(order_id):
    user = current_user()
    order = _get_order_or_404(order_id)
    if not _can_view(order, user):
        abort(403)
    form = ApprovalForm()
    if not form.validate_on_submit():
        flash("Datos inválidos.", "danger")
        return redirect(url_for("orders.detail", order_id=order.id))
    try:
        svc.send_for_approval(order, user, form.estimated_budget.data, form.note.data)
        db.session.commit()
        flash("Orden enviada a espera de aprobación.", "success")
    except OrderError as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("orders.detail", order_id=order.id))


@bp.route("/<int:order_id>/decision-cliente", methods=["POST"])
@login_required
def client_decision(order_id):
    user = current_user()
    order = _get_order_or_404(order_id)
    if not _can_view(order, user):
        abort(403)
    form = ClientDecisionForm()
    if not form.validate_on_submit():
        flash("Datos inválidos.", "danger")
        return redirect(url_for("orders.detail", order_id=order.id))
    try:
        svc.register_client_decision(order, user, form.decision.data, form.note.data)
        db.session.commit()
        flash("Decisión del cliente registrada.", "success")
    except OrderError as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("orders.detail", order_id=order.id))


@bp.route("/<int:order_id>/confirmar", methods=["POST"])
@login_required
def confirm(order_id):
    user = current_user()
    if not user.is_jefe:
        abort(403)
    order = _get_order_or_404(order_id)
    form = ConfirmForm()
    form.assigned_to_id.choices = _employee_choices(include_empty=False)
    if not form.validate_on_submit():
        flash("Datos inválidos para confirmar.", "danger")
        return redirect(url_for("orders.detail", order_id=order.id))
    try:
        svc.confirm_order(order, user, form.approved_amount.data,
                          form.assigned_to_id.data, form.note.data)
        db.session.commit()
        flash("Orden confirmada y asignada.", "success")
    except OrderError as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("orders.detail", order_id=order.id))


@bp.route("/<int:order_id>/iniciar", methods=["POST"])
@login_required
def start(order_id):
    user = current_user()
    order = _get_order_or_404(order_id)
    # Solo el empleado asignado (o el jefe) puede iniciar.
    if not user.is_jefe and order.assigned_to_id != user.id:
        abort(403)
    try:
        svc.start_work(order, user)
        db.session.commit()
        flash("Trabajo iniciado. El cronómetro está corriendo.", "success")
    except OrderError as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("orders.detail", order_id=order.id))


@bp.route("/<int:order_id>/pausar", methods=["POST"])
@login_required
def pause(order_id):
    user = current_user()
    order = _get_order_or_404(order_id)
    if not user.is_jefe and order.assigned_to_id != user.id:
        abort(403)
    form = PauseForm()
    if not form.validate_on_submit():
        flash("Debes indicar el motivo de la pausa.", "danger")
        return redirect(url_for("orders.detail", order_id=order.id))
    reason = form.reason.data
    if reason == "Otro" and form.reason_other.data:
        reason = form.reason_other.data
    try:
        svc.pause_work(order, user, reason)
        db.session.commit()
        flash("Trabajo pausado.", "info")
    except OrderError as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("orders.detail", order_id=order.id))


@bp.route("/<int:order_id>/finalizar", methods=["POST"])
@login_required
def finish(order_id):
    user = current_user()
    order = _get_order_or_404(order_id)
    if not user.is_jefe and order.assigned_to_id != user.id:
        abort(403)
    form = FinishForm()
    if not form.validate_on_submit():
        flash("Datos inválidos.", "danger")
        return redirect(url_for("orders.detail", order_id=order.id))
    data = {
        "summary": form.summary.data,
        "diagnosis": form.diagnosis.data,
        "parts_used": form.parts_used.data,
        "observations": form.observations.data,
    }
    try:
        svc.finish_work(order, user, data)
        db.session.commit()
        flash("Trabajo finalizado.", "success")
    except OrderError as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("orders.detail", order_id=order.id))


@bp.route("/<int:order_id>/cobro", methods=["POST"])
@login_required
def set_final_amount(order_id):
    user = current_user()
    if not user.is_jefe:
        abort(403)
    order = _get_order_or_404(order_id)
    form = FinalAmountForm()
    if not form.validate_on_submit():
        flash("Monto inválido.", "danger")
        return redirect(url_for("orders.detail", order_id=order.id))
    try:
        svc.set_final_amount(order, user, form.final_amount.data)
        db.session.commit()
        flash("Monto cobrado registrado.", "success")
    except OrderError as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("orders.detail", order_id=order.id))


@bp.route("/<int:order_id>/entregar", methods=["POST"])
@login_required
def deliver(order_id):
    user = current_user()
    if not user.is_jefe:
        abort(403)
    order = _get_order_or_404(order_id)
    form = SimpleNoteForm()
    note = form.note.data if form.validate_on_submit() else None
    try:
        svc.deliver_order(order, user, note)
        db.session.commit()
        flash("Orden entregada y cerrada.", "success")
    except OrderError as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("orders.detail", order_id=order.id))


@bp.route("/<int:order_id>/cancelar", methods=["POST"])
@login_required
def cancel(order_id):
    user = current_user()
    if not user.is_jefe:
        abort(403)
    order = _get_order_or_404(order_id)
    form = SimpleNoteForm()
    note = form.note.data if form.validate_on_submit() else None
    try:
        svc.cancel_order(order, user, note)
        db.session.commit()
        flash("Orden cancelada.", "info")
    except OrderError as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("orders.detail", order_id=order.id))


@bp.route("/<int:order_id>/reabrir", methods=["POST"])
@login_required
def reopen(order_id):
    user = current_user()
    if not user.is_jefe:
        abort(403)
    order = _get_order_or_404(order_id)
    form = SimpleNoteForm()
    note = form.note.data if form.validate_on_submit() else None
    try:
        svc.reopen_order(order, user, note)
        db.session.commit()
        flash("Orden reabierta (acción auditada).", "warning")
    except OrderError as e:
        db.session.rollback()
        flash(str(e), "danger")
    return redirect(url_for("orders.detail", order_id=order.id))


@bp.route("/<int:order_id>/nota", methods=["POST"])
@login_required
def add_note(order_id):
    user = current_user()
    order = _get_order_or_404(order_id)
    if not _can_view(order, user):
        abort(403)
    form = SimpleNoteForm()
    if form.validate_on_submit() and (form.note.data or "").strip():
        db.session.add(WorkOrderNote(order_id=order.id, author_id=user.id,
                                     body=form.note.data.strip()))
        log_action(user, "nota_orden", "work_order", order.id)
        db.session.commit()
        flash("Observación agregada.", "success")
    return redirect(url_for("orders.detail", order_id=order.id))
