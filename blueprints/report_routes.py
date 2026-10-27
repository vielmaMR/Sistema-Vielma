"""Rutas de reportes diarios y mensuales (solo jefe) + exportación CSV."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime

from flask import Blueprint, render_template, request, Response

from auth import jefe_required
from services import reports
from utils.timezone import local_day_bounds, local_month_bounds, format_duration

bp = Blueprint("reports", __name__, url_prefix="/reportes")


@bp.route("/")
@jefe_required
def index():
    mode = request.args.get("mode", "daily")
    today = date.today()

    if mode == "monthly":
        year = request.args.get("year", type=int) or today.year
        month = request.args.get("month", type=int) or today.month
        start, end = local_month_bounds(year, month)
        title = f"Reporte mensual — {month:02d}/{year}"
        period = {"mode": "monthly", "year": year, "month": month}
    else:
        day_str = request.args.get("date", "")
        try:
            day = date.fromisoformat(day_str) if day_str else today
        except ValueError:
            day = today
        start, end = local_day_bounds(day)
        title = f"Reporte diario — {day.strftime('%d/%m/%Y')}"
        period = {"mode": "daily", "date": day.isoformat()}

    data = reports.build_report(start, end)
    return render_template("reports/index.html", data=data, title=title,
                           period=period, fmt_dur=format_duration)


@bp.route("/csv")
@jefe_required
def export_csv():
    mode = request.args.get("mode", "daily")
    today = date.today()
    if mode == "monthly":
        year = request.args.get("year", type=int) or today.year
        month = request.args.get("month", type=int) or today.month
        start, end = local_month_bounds(year, month)
        label = f"{year}-{month:02d}"
    else:
        day_str = request.args.get("date", "")
        try:
            day = date.fromisoformat(day_str) if day_str else today
        except ValueError:
            day = today
        start, end = local_day_bounds(day)
        label = day.isoformat()

    data = reports.build_report(start, end)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Vielma - MotoRepuestos", f"Reporte {label}"])
    writer.writerow([])
    writer.writerow(["Indicador", "Valor"])
    c = data["counts"]
    writer.writerow(["Órdenes creadas", c["created"]])
    writer.writerow(["Aprobadas por cliente", c["approved_client"]])
    writer.writerow(["Confirmadas", c["confirmed"]])
    writer.writerow(["Iniciadas", c["started"]])
    writer.writerow(["Finalizadas", c["finished"]])
    writer.writerow(["Entregadas", c["delivered"]])
    writer.writerow(["Rechazadas/Canceladas", c["rejected_cancelled"]])
    writer.writerow([])

    t = data["times"]
    writer.writerow(["Tiempo", "Promedio", "N"])
    writer.writerow(["Efectivo de trabajo", format_duration(t["avg_effective"]), t["n_effective"]])
    writer.writerow(["Total de reparación", format_duration(t["avg_repair"]), t["n_repair"]])
    writer.writerow(["Espera de aprobación", format_duration(t["avg_wait_approval"]), t["n_wait"]])
    writer.writerow(["Pendiente de inicio", format_duration(t["avg_pending_start"]), t["n_pending"]])
    writer.writerow(["Finalización → entrega", format_duration(t["avg_finish_to_deliver"]), t["n_f2d"]])
    writer.writerow([])

    e = data["economics"]
    writer.writerow(["Económico", "Valor", "N"])
    writer.writerow(["Promedio aprobado", e["avg_approved"], e["n_approved"]])
    writer.writerow(["Promedio cobrado", e["avg_final"], e["n_final"]])
    writer.writerow(["Total aprobado", e["total_approved"], ""])
    writer.writerow(["Total cobrado", e["total_collected"], ""])
    writer.writerow(["Órdenes sin monto", e["orders_without_amount"], ""])
    writer.writerow([])

    writer.writerow(["Tipo de trabajo", "Cantidad", "%"])
    for k, v in data["worktypes"]["counts"].items():
        writer.writerow([k, v, data["worktypes"]["pct"].get(k, "")])
    writer.writerow([])
    writer.writerow(["Marca", "Cantidad"])
    for k, v in data["brands"]["counts"].items():
        writer.writerow([k, v])
    writer.writerow([])
    writer.writerow(["Vehículo", "Cantidad"])
    for k, v in data["vehicles"]["counts"].items():
        writer.writerow([k, v])

    csv_bytes = output.getvalue()
    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=reporte_{label}.csv"},
    )
