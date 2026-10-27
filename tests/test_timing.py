from datetime import timedelta

from models import WorkOrder, WorkSession, WorkOrderStatusHistory, User
from services import timing
from utils.timezone import utcnow
import constants as C


def _make_order(db):
    jefe = User.query.filter_by(username="christian").first()
    o = WorkOrder(number=1, created_by_id=jefe.id, status=C.ST_EN_TRABAJO,
                  status_since=utcnow())
    db.session.add(o)
    db.session.flush()
    return o


def test_effective_excludes_pauses(db):
    o = _make_order(db)
    emp = User.query.filter_by(username="humberto").first()
    base = utcnow() - timedelta(hours=3)
    # Sesión 1: 1 hora
    db.session.add(WorkSession(order_id=o.id, user_id=emp.id,
                               started_at=base, ended_at=base + timedelta(hours=1)))
    # (pausa de 1 hora, no se registra como sesión)
    # Sesión 2: 30 min
    db.session.add(WorkSession(order_id=o.id, user_id=emp.id,
                               started_at=base + timedelta(hours=2),
                               ended_at=base + timedelta(hours=2, minutes=30)))
    db.session.flush()
    secs = timing.effective_work_seconds(o)
    assert abs(secs - (3600 + 1800)) < 2  # 1h30m, sin contar la pausa


def test_status_time_accumulates_multiple_periods(db):
    o = _make_order(db)
    jefe = User.query.filter_by(username="christian").first()
    t0 = utcnow() - timedelta(hours=5)
    # espera -> trabajo -> espera (dos periodos de espera)
    hist = [
        WorkOrderStatusHistory(order_id=o.id, to_status=C.ST_ESPERA_APROBACION,
                               changed_by_id=jefe.id, changed_at=t0),
        WorkOrderStatusHistory(order_id=o.id, from_status=C.ST_ESPERA_APROBACION,
                               to_status=C.ST_EN_TRABAJO, changed_by_id=jefe.id,
                               changed_at=t0 + timedelta(hours=1)),
        WorkOrderStatusHistory(order_id=o.id, from_status=C.ST_EN_TRABAJO,
                               to_status=C.ST_ESPERA_APROBACION, changed_by_id=jefe.id,
                               changed_at=t0 + timedelta(hours=2)),
        WorkOrderStatusHistory(order_id=o.id, from_status=C.ST_ESPERA_APROBACION,
                               to_status=C.ST_EN_TRABAJO, changed_by_id=jefe.id,
                               changed_at=t0 + timedelta(hours=3)),
    ]
    db.session.add_all(hist)
    db.session.flush()
    # Dos periodos de 1 hora en espera = 2 horas.
    secs = timing.waiting_approval_seconds(o)
    assert abs(secs - 7200) < 2
