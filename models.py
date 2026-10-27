"""Modelo de datos de Vielma - MotoRepuestos.

Todas las marcas de tiempo se guardan en UTC (naive) mediante utils.timezone.utcnow.
"""
from __future__ import annotations

from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db
from utils.timezone import utcnow
import constants as C


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=C.ROLE_EMPLEADO)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_jefe(self) -> bool:
        return self.role == C.ROLE_JEFE

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username} ({self.role})>"


class WorkOrder(db.Model):
    __tablename__ = "work_orders"
    __table_args__ = (
        db.Index("ix_wo_status_created", "status", "created_at"),
        db.Index("ix_wo_assigned_status", "assigned_to_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False, index=True)

    # Identificación / autoría
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    # Vehículo
    vehicle_type = db.Column(db.String(20), nullable=False, default=C.VH_MOTO)
    brand = db.Column(db.String(60))
    model = db.Column(db.String(60))
    year = db.Column(db.Integer)
    plate = db.Column(db.String(20), index=True)          # chapa / matrícula
    mileage = db.Column(db.Integer)

    # Cliente
    client_name = db.Column(db.String(120))
    client_phone = db.Column(db.String(40))

    # Trabajo
    work_type = db.Column(db.String(40), nullable=False, default=C.DEFAULT_WORK_TYPE)
    work_type_other = db.Column(db.String(120))
    problem_description = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    tasks_detail = db.Column(db.Text)
    parts_used = db.Column(db.Text)
    observations = db.Column(db.Text)
    estimated_delivery = db.Column(db.DateTime)

    # Económico
    estimated_budget = db.Column(db.Numeric(12, 2))
    approved_amount = db.Column(db.Numeric(12, 2))
    final_amount = db.Column(db.Numeric(12, 2))
    budget_notes = db.Column(db.Text)

    # Seguimiento
    status = db.Column(db.String(30), nullable=False, default=C.ST_SOLICITADO, index=True)
    status_since = db.Column(db.DateTime, nullable=False, default=utcnow)
    work_started_at = db.Column(db.DateTime)   # primer inicio de trabajo
    finished_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)

    # Relaciones
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])
    status_history = db.relationship(
        "WorkOrderStatusHistory", back_populates="order",
        cascade="all, delete-orphan", order_by="WorkOrderStatusHistory.changed_at")
    sessions = db.relationship(
        "WorkSession", back_populates="order",
        cascade="all, delete-orphan", order_by="WorkSession.started_at")
    approvals = db.relationship(
        "WorkOrderApproval", back_populates="order",
        cascade="all, delete-orphan", order_by="WorkOrderApproval.created_at")
    notes = db.relationship(
        "WorkOrderNote", back_populates="order",
        cascade="all, delete-orphan", order_by="WorkOrderNote.created_at")

    # --- Propiedades de presentación ---
    @property
    def status_label(self) -> str:
        return C.STATUS_LABELS.get(self.status, self.status)

    @property
    def status_css(self) -> str:
        return C.STATUS_CSS.get(self.status, "")

    @property
    def vehicle_label(self) -> str:
        return C.VEHICLE_TYPES.get(self.vehicle_type, self.vehicle_type)

    @property
    def work_type_label(self) -> str:
        if self.work_type == "otro" and self.work_type_other:
            return self.work_type_other
        return C.WORK_TYPE_LABELS.get(self.work_type, self.work_type)

    @property
    def is_closed(self) -> bool:
        return self.status in C.CLOSED_STATES

    @property
    def has_client_approval(self) -> bool:
        """True si existe una aprobación de cliente vigente (la última es aprobada)."""
        last = self._last_client_decision()
        return last is not None and last.decision == "aprobado"

    def _last_client_decision(self):
        decisions = [a for a in self.approvals if a.decision in ("aprobado", "rechazado")]
        if not decisions:
            return None
        return sorted(decisions, key=lambda a: a.created_at)[-1]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WorkOrder #{self.number} {self.status}>"


class WorkOrderStatusHistory(db.Model):
    __tablename__ = "work_order_status_history"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("work_orders.id"), nullable=False, index=True)
    from_status = db.Column(db.String(30))
    to_status = db.Column(db.String(30), nullable=False)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    changed_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    note = db.Column(db.Text)

    order = db.relationship("WorkOrder", back_populates="status_history")
    changed_by = db.relationship("User")


class WorkSession(db.Model):
    """Intervalo de trabajo efectivo de un empleado sobre una orden."""
    __tablename__ = "work_sessions"
    __table_args__ = (
        db.Index("ix_ws_order_user", "order_id", "user_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("work_orders.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    ended_at = db.Column(db.DateTime)           # NULL = sesión activa
    pause_reason = db.Column(db.String(120))    # motivo por el que se cerró (pausa)

    order = db.relationship("WorkOrder", back_populates="sessions")
    user = db.relationship("User")

    @property
    def is_active(self) -> bool:
        return self.ended_at is None

    def duration_seconds(self, now=None) -> float:
        end = self.ended_at or (now or utcnow())
        return max(0.0, (end - self.started_at).total_seconds())


class WorkOrderApproval(db.Model):
    """Historial de presupuestos y decisiones del cliente / confirmaciones internas."""
    __tablename__ = "work_order_approvals"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("work_orders.id"), nullable=False, index=True)
    # kind: 'presupuesto' | 'decision_cliente' | 'confirmacion_jefe'
    kind = db.Column(db.String(30), nullable=False)
    # decision: 'aprobado' | 'rechazado' | None (para presupuesto/confirmación)
    decision = db.Column(db.String(20))
    amount = db.Column(db.Numeric(12, 2))
    note = db.Column(db.Text)
    registered_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    order = db.relationship("WorkOrder", back_populates="approvals")
    registered_by = db.relationship("User")


class WorkOrderNote(db.Model):
    __tablename__ = "work_order_notes"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("work_orders.id"), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    order = db.relationship("WorkOrder", back_populates="notes")
    author = db.relationship("User")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = (
        db.Index("ix_audit_created", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(80), nullable=False)
    entity = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    detail = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    user = db.relationship("User")


class Budget(db.Model):
    """Presupuesto/cotización generado para un cliente (independiente de las órdenes).

    Guarda cada presupuesto para tener numeración correlativa persistente y un
    historial consultable. El PDF se regenera a partir de estos datos.
    """
    __tablename__ = "budgets"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    # Datos del vehículo
    vehicle_type = db.Column(db.String(30))
    brand = db.Column(db.String(60))
    model = db.Column(db.String(60))
    color = db.Column(db.String(40))
    year = db.Column(db.String(10))

    total = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    created_by = db.relationship("User")
    items = db.relationship("BudgetItem", back_populates="budget",
                            cascade="all, delete-orphan", order_by="BudgetItem.id")

    @property
    def code(self) -> str:
        return f"PRES-{self.number:06d}"


class BudgetItem(db.Model):
    """Línea de repuesto/servicio dentro de un presupuesto."""
    __tablename__ = "budget_items"

    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(db.Integer, db.ForeignKey("budgets.id"), nullable=False, index=True)
    description = db.Column(db.String(200), nullable=False)
    unit_value = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    budget = db.relationship("Budget", back_populates="items")

    @property
    def subtotal(self):
        return (self.unit_value or 0) * (self.quantity or 0)
