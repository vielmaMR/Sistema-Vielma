import pytest

from models import User, WorkOrder
from services import orders as svc
from services.orders import OrderError
import constants as C


def _user(username):
    return User.query.filter_by(username=username).first()


def test_create_order_number_correlative(db):
    emp = _user("humberto")
    o1 = svc.create_order(emp, {"vehicle_type": C.VH_MOTO, "work_type": "mantenimiento"})
    db.session.flush()
    o2 = svc.create_order(emp, {"vehicle_type": C.VH_AUTO, "work_type": "mantenimiento"})
    db.session.flush()
    assert o2.number == o1.number + 1
    assert o1.status == C.ST_SOLICITADO


def test_cannot_confirm_without_client_approval(db):
    jefe = _user("christian")
    o = svc.create_order(jefe, {"vehicle_type": C.VH_MOTO, "work_type": "mantenimiento"})
    db.session.flush()
    with pytest.raises(OrderError):
        svc.confirm_order(o, jefe, 100000)


def test_full_flow_to_confirm(db):
    emp = _user("humberto")
    jefe = _user("christian")
    o = svc.create_order(emp, {"vehicle_type": C.VH_MOTO, "work_type": "mantenimiento"})
    db.session.flush()
    svc.send_for_approval(o, emp, 100000, "presupuesto")
    svc.register_client_decision(o, emp, "aprobado", "cliente ok")
    assert o.status == C.ST_APROBADO_CLIENTE
    assert o.has_client_approval
    svc.confirm_order(o, jefe, 120000, assigned_to_id=emp.id)
    assert o.status == C.ST_CONFIRMADO
    assert float(o.approved_amount) == 120000


def test_employee_cannot_set_final_amount(db):
    emp = _user("humberto")
    o = svc.create_order(emp, {"vehicle_type": C.VH_MOTO, "work_type": "mantenimiento"})
    db.session.flush()
    with pytest.raises(OrderError):
        svc.set_final_amount(o, emp, 50000)


def test_work_start_pause_finish(db):
    emp = _user("humberto")
    jefe = _user("christian")
    o = svc.create_order(emp, {"vehicle_type": C.VH_MOTO, "work_type": "mantenimiento"})
    db.session.flush()
    svc.send_for_approval(o, emp, 100000)
    svc.register_client_decision(o, emp, "aprobado")
    svc.confirm_order(o, jefe, 100000, assigned_to_id=emp.id)
    svc.start_work(o, emp)
    assert o.status == C.ST_EN_TRABAJO
    svc.pause_work(o, emp, "Espera de repuesto")
    assert o.status == C.ST_PAUSADO
    svc.start_work(o, emp)
    assert o.status == C.ST_EN_TRABAJO
    svc.finish_work(o, emp, {"summary": "listo"})
    assert o.status == C.ST_FINALIZADO
    assert o.finished_at is not None
    # No quedan sesiones abiertas.
    assert all(s.ended_at is not None for s in o.sessions)


def test_invalid_transition_blocked(db):
    emp = _user("humberto")
    o = svc.create_order(emp, {"vehicle_type": C.VH_MOTO, "work_type": "mantenimiento"})
    db.session.flush()
    with pytest.raises(OrderError):
        svc.transition(o, C.ST_ENTREGADO, emp)  # Solicitado -> Entregado no permitido
