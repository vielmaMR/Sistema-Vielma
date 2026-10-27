"""Módulo de presupuestos: formulario, carga de repuestos y generación de PDF.

Independiente de las órdenes. Disponible para todos los roles.
Los repuestos en edición se mantienen en la sesión hasta generar el PDF o limpiar.
"""
from __future__ import annotations

from datetime import datetime

from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, make_response, flash)
from sqlalchemy import func

from extensions import db
from models import Budget, BudgetItem
from auth import login_required, current_user
from services.budget_pdf import generar_pdf, formatear_guaranies
from services.audit import log_action
from utils.timezone import to_local, utcnow
import constants as C

bp = Blueprint("budget", __name__, url_prefix="/presupuestos")

VEHICLE_OPTIONS = ["Moto", "Auto", "Motocarro", "Camioneta", "Otro"]


def _to_int(value, default=0):
    try:
        return int(str(value).replace(".", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return default


def _get_items():
    return session.get("budget_items", [])


def _save_items(items):
    session["budget_items"] = items
    session.modified = True


def _get_vehicle():
    return session.get("budget_vehicle", {})


def _save_vehicle_from_form():
    vehicle = {
        "tipo_vehiculo": request.form.get("tipo_vehiculo", "").strip(),
        "marca": request.form.get("marca", "").strip(),
        "modelo": request.form.get("modelo", "").strip(),
        "color": request.form.get("color", "").strip(),
        "anio": request.form.get("anio", "").strip(),
    }
    session["budget_vehicle"] = vehicle
    session.modified = True
    return vehicle


def _calc_total(items):
    total = 0
    for it in items:
        total += _to_int(it.get("valor_unitario")) * _to_int(it.get("cantidad"), 1)
    return total


@bp.route("/", methods=["GET"])
@login_required
def index():
    items = _get_items()
    vehicle = _get_vehicle()
    # Enriquecer con subtotales formateados para mostrar.
    for it in items:
        valor = _to_int(it.get("valor_unitario"))
        cant = _to_int(it.get("cantidad"), 1)
        it["subtotal"] = valor * cant
        it["subtotal_fmt"] = formatear_guaranies(valor * cant)
        it["valor_fmt"] = formatear_guaranies(valor)
    total = _calc_total(items)
    return render_template("budget/index.html", items=items, vehicle=vehicle,
                           total=total, total_fmt=formatear_guaranies(total),
                           vehicle_options=VEHICLE_OPTIONS)


@bp.route("/agregar", methods=["POST"])
@login_required
def add_item():
    _save_vehicle_from_form()
    items = _collect_hidden_items()

    desc = request.form.get("nuevo_desc", "").strip()
    valor = request.form.get("nuevo_valor", "").strip()
    cant = request.form.get("nuevo_cant", "").strip()

    errores = []
    if not desc:
        errores.append("La descripción del repuesto es obligatoria.")
    if not valor or _to_int(valor) <= 0:
        errores.append("El valor del repuesto debe ser mayor a 0.")
    if not cant:
        cant = "1"
    elif _to_int(cant) <= 0:
        errores.append("La cantidad debe ser mayor a 0.")

    if errores:
        for e in errores:
            flash(e, "danger")
        _save_items(items)
        return redirect(url_for("budget.index"))

    items.append({
        "descripcion": desc,
        "valor_unitario": str(_to_int(valor)),
        "cantidad": str(_to_int(cant, 1)),
    })
    _save_items(items)
    return redirect(url_for("budget.index"))


@bp.route("/eliminar", methods=["POST"])
@login_required
def remove_item():
    _save_vehicle_from_form()
    items = _collect_hidden_items()
    idx = _to_int(request.form.get("eliminar", ""), -1)
    if 0 <= idx < len(items):
        items.pop(idx)
    _save_items(items)
    return redirect(url_for("budget.index"))


@bp.route("/limpiar", methods=["POST"])
@login_required
def clear():
    session.pop("budget_items", None)
    session.pop("budget_vehicle", None)
    flash("Formulario de presupuesto limpiado.", "info")
    return redirect(url_for("budget.index"))


@bp.route("/pdf", methods=["POST"])
@login_required
def generate_pdf():
    vehicle = _save_vehicle_from_form()
    items = _collect_hidden_items()
    _save_items(items)

    # Validación
    errores = []
    if vehicle["tipo_vehiculo"] not in VEHICLE_OPTIONS:
        errores.append("Debe seleccionar el tipo de vehículo.")
    if not vehicle["marca"]:
        errores.append("La marca del vehículo es obligatoria.")
    if not vehicle["modelo"]:
        errores.append("El modelo del vehículo es obligatorio.")
    if not items:
        errores.append("Debe agregar al menos un repuesto.")
    if errores:
        for e in errores:
            flash(e, "danger")
        return redirect(url_for("budget.index"))

    # Calcular subtotales
    for it in items:
        it["subtotal"] = _to_int(it["valor_unitario"]) * _to_int(it["cantidad"], 1)
    total = _calc_total(items)

    # Numeración correlativa persistente + guardar en historial (transacción).
    next_number = (db.session.query(func.max(Budget.number)).scalar() or 0) + 1
    budget = Budget(
        number=next_number,
        created_by_id=current_user().id,
        vehicle_type=vehicle["tipo_vehiculo"], brand=vehicle["marca"],
        model=vehicle["modelo"], color=vehicle["color"], year=vehicle["anio"],
        total=total,
    )
    db.session.add(budget)
    db.session.flush()
    for it in items:
        db.session.add(BudgetItem(
            budget_id=budget.id, description=it["descripcion"],
            unit_value=_to_int(it["valor_unitario"]),
            quantity=_to_int(it["cantidad"], 1)))
    log_action(current_user(), "generar_presupuesto", "budget", budget.id, budget.code)
    db.session.commit()

    fecha = to_local(utcnow()).strftime("%d/%m/%Y")
    datos_pdf = {
        "numero": budget.code,
        "fecha": fecha,
        "tipo_vehiculo": vehicle["tipo_vehiculo"],
        "marca": vehicle["marca"], "modelo": vehicle["modelo"],
        "color": vehicle["color"], "anio": vehicle["anio"],
        "repuestos": items, "total": total,
    }
    pdf_buffer = generar_pdf(datos_pdf)

    # Al generar el PDF se limpia la sesión para empezar un presupuesto nuevo.
    session.pop("budget_items", None)
    session.pop("budget_vehicle", None)

    response = make_response(pdf_buffer.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = \
        f"attachment; filename=presupuesto_{budget.code}.pdf"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


def _collect_hidden_items():
    """Reconstruye la lista de repuestos desde los inputs ocultos del formulario."""
    items = []
    i = 0
    while True:
        desc_key = f"repuesto_desc_{i}"
        if desc_key not in request.form:
            break
        items.append({
            "descripcion": request.form.get(desc_key, "").strip(),
            "valor_unitario": request.form.get(f"repuesto_valor_{i}", "").strip(),
            "cantidad": request.form.get(f"repuesto_cant_{i}", "").strip() or "1",
        })
        i += 1
    return items
