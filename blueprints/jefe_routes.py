"""Rutas exclusivas del jefe: dashboard, bandeja de órdenes y gestión de empleados."""
from __future__ import annotations

from datetime import date

from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, abort)
from sqlalchemy import or_, func

from extensions import db
from models import User, WorkOrder, WorkSession
from auth import jefe_required, current_user
from forms import EmployeeCreateForm, EmployeeForm, ResetPasswordForm
from services import timing
from services.audit import log_action
from utils.timezone import utcnow, local_day_bounds
import constants as C

bp = Blueprint("jefe", __name__, url_prefix="/jefe")


@bp.route("/")
@jefe_required
def dashboard():
    today = date.today()
    start, end = local_day_bounds(today)
    now = utcnow()

    def count(*statuses):
        return WorkOrder.query.filter(WorkOrder.status.in_(statuses)).count()

    created_today = WorkOrder.query.filter(
        WorkOrder.created_at >= start, WorkOrder.created_at < end).count()
    finished_today = WorkOrder.query.filter(
        WorkOrder.finished_at >= start, WorkOrder.finished_at < end).count()
    delivered_today = WorkOrder.query.filter(
        WorkOrder.delivered_at >= start, WorkOrder.delivered_at < end).count()

    # Monto aprobado hoy (confirmaciones de hoy) y cobrado hoy (entregas de hoy).
    from models import WorkOrderApproval
    approved_today = db.session.query(func.coalesce(func.sum(WorkOrderApproval.amount), 0)) \
        .filter(WorkOrderApproval.kind == "confirmacion_jefe",
                WorkOrderApproval.created_at >= start,
                WorkOrderApproval.created_at < end).scalar()
    collected_today = db.session.query(func.coalesce(func.sum(WorkOrder.final_amount), 0)) \
        .filter(WorkOrder.delivered_at >= start, WorkOrder.delivered_at < end).scalar()

    # Tiempo efectivo total trabajado hoy (todas las sesiones).
    effective_today = _effective_total_today(start, end, now)

    cards = {
        "created_today": created_today,
        "pending_approval": count(C.ST_ESPERA_APROBACION),
        "pending_start": count(C.ST_CONFIRMADO),
        "in_progress": count(C.ST_EN_TRABAJO, C.ST_PAUSADO),
        "finished_today": finished_today,
        "delivered_today": delivered_today,
        "effective_today": effective_today,
        "approved_today": approved_today,
        "collected_today": collected_today,
    }

    # Órdenes que esperan acción del jefe, con antigüedad para destacar.
    attention = (WorkOrder.query
                 .filter(WorkOrder.status.in_([C.ST_ESPERA_APROBACION,
                                               C.ST_APROBADO_CLIENTE,
                                               C.ST_FINALIZADO]))
                 .order_by(WorkOrder.status_since.asc())
                 .limit(20).all())

    # Trabajos que el propio jefe tiene asignados y puede ejecutar como mecánico.
    my_jobs = (WorkOrder.query
               .filter(WorkOrder.assigned_to_id == current_user().id,
                       WorkOrder.status.in_([C.ST_CONFIRMADO, C.ST_EN_TRABAJO,
                                             C.ST_PAUSADO]))
               .order_by(WorkOrder.status_since.asc())
               .all())

    return render_template("jefe/dashboard.html", cards=cards, attention=attention,
                           my_jobs=my_jobs, now=now)


def _effective_total_today(start, end, now):
    total = 0.0
    sessions = WorkSession.query.filter(WorkSession.started_at < end).all()
    for s in sessions:
        s_end = s.ended_at or now
        lo = max(s.started_at, start)
        hi = min(s_end, end)
        if hi > lo:
            total += (hi - lo).total_seconds()
    return total


@bp.route("/ordenes")
@jefe_required
def orders():
    q = WorkOrder.query
    # Filtros
    number = request.args.get("number", type=int)
    plate = request.args.get("plate", "").strip()
    text = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    emp = request.args.get("employee", type=int)
    work_type = request.args.get("work_type", "").strip()
    date_from = request.args.get("from", "").strip()
    date_to = request.args.get("to", "").strip()
    sort = request.args.get("sort", "recent")

    if number:
        q = q.filter(WorkOrder.number == number)
    if plate:
        q = q.filter(WorkOrder.plate.ilike(f"%{plate}%"))
    if text:
        like = f"%{text}%"
        q = q.filter(or_(WorkOrder.brand.ilike(like), WorkOrder.model.ilike(like),
                         WorkOrder.client_name.ilike(like)))
    if status:
        q = q.filter(WorkOrder.status == status)
    if emp:
        q = q.filter(WorkOrder.assigned_to_id == emp)
    if work_type:
        q = q.filter(WorkOrder.work_type == work_type)
    if date_from:
        try:
            d = date.fromisoformat(date_from)
            start, _ = local_day_bounds(d)
            q = q.filter(WorkOrder.created_at >= start)
        except ValueError:
            pass
    if date_to:
        try:
            d = date.fromisoformat(date_to)
            _, end = local_day_bounds(d)
            q = q.filter(WorkOrder.created_at < end)
        except ValueError:
            pass

    if sort == "status":
        q = q.order_by(WorkOrder.status.asc(), WorkOrder.created_at.desc())
    elif sort == "oldest":
        q = q.order_by(WorkOrder.created_at.asc())
    else:
        q = q.order_by(WorkOrder.created_at.desc())

    orders_list = q.limit(300).all()
    employees = User.query.order_by(User.full_name).all()
    return render_template("jefe/orders.html", orders=orders_list,
                           employees=employees, args=request.args)


# --------------- Gestión de empleados ---------------

@bp.route("/empleados")
@jefe_required
def employees():
    users = User.query.order_by(User.role.desc(), User.full_name).all()
    # Estadísticas de productividad por usuario.
    stats = {}
    now = utcnow()
    for u in users:
        orders_count = WorkOrder.query.filter(
            WorkOrder.assigned_to_id == u.id,
            WorkOrder.status.in_(list(C.COMPLETED_STATES))).count()
        sessions = WorkSession.query.filter_by(user_id=u.id).all()
        total = sum(s.duration_seconds(now) for s in sessions)
        stats[u.id] = {"orders": orders_count, "effective": total}
    return render_template("jefe/employees.html", users=users, stats=stats)


@bp.route("/empleados/nuevo", methods=["GET", "POST"])
@jefe_required
def employee_create():
    form = EmployeeCreateForm()
    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        if User.query.filter_by(username=username).first():
            flash("Ese nombre de usuario ya existe.", "danger")
        else:
            user = User(username=username, full_name=form.full_name.data.strip(),
                        phone=form.phone.data, role=form.role.data,
                        is_active=form.is_active.data, must_change_password=True)
            user.set_password(form.password.data)
            db.session.add(user)
            log_action(current_user(), "crear_usuario", "user", None, username)
            db.session.commit()
            flash(f"Empleado {user.full_name} creado.", "success")
            return redirect(url_for("jefe.employees"))
    return render_template("jefe/employee_form.html", form=form, user=None)


@bp.route("/empleados/<int:user_id>/editar", methods=["GET", "POST"])
@jefe_required
def employee_edit(user_id):
    user = User.query.get_or_404(user_id)
    form = EmployeeForm(obj=user)
    if form.validate_on_submit():
        new_username = form.username.data.strip().lower()
        other = User.query.filter(User.username == new_username, User.id != user.id).first()
        if other:
            flash("Ese nombre de usuario ya existe.", "danger")
        else:
            user.full_name = form.full_name.data.strip()
            user.username = new_username
            user.phone = form.phone.data
            user.role = form.role.data
            user.is_active = form.is_active.data
            log_action(current_user(), "editar_usuario", "user", user.id)
            db.session.commit()
            flash("Empleado actualizado.", "success")
            return redirect(url_for("jefe.employees"))
    return render_template("jefe/employee_form.html", form=form, user=user)


@bp.route("/empleados/<int:user_id>/reset", methods=["GET", "POST"])
@jefe_required
def employee_reset_password(user_id):
    user = User.query.get_or_404(user_id)
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        user.must_change_password = True
        log_action(current_user(), "reset_contrasena", "user", user.id)
        db.session.commit()
        flash(f"Contraseña de {user.full_name} restablecida. "
              "Deberá cambiarla al iniciar sesión.", "success")
        return redirect(url_for("jefe.employees"))
    return render_template("jefe/employee_reset.html", form=form, user=user)


@bp.route("/empleados/<int:user_id>/toggle", methods=["POST"])
@jefe_required
def employee_toggle(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user().id:
        flash("No puedes desactivar tu propio usuario.", "warning")
        return redirect(url_for("jefe.employees"))
    user.is_active = not user.is_active
    log_action(current_user(), "toggle_usuario", "user", user.id,
               "activado" if user.is_active else "desactivado")
    db.session.commit()
    flash(f"Usuario {'activado' if user.is_active else 'desactivado'}.", "info")
    return redirect(url_for("jefe.employees"))
