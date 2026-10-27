"""Creación de la base de datos y usuarios semilla idempotente."""
from __future__ import annotations

from extensions import db
from models import User
import constants as C


SEED_USERS = [
    # (username, full_name, role, env_key)
    ("christian", "Christian", C.ROLE_JEFE, "SEED_PASSWORD_CHRISTIAN"),
    ("humberto", "Humberto", C.ROLE_EMPLEADO, "SEED_PASSWORD_HUMBERTO"),
    ("arturo", "Arturo", C.ROLE_EMPLEADO, "SEED_PASSWORD_ARTURO"),
]


def init_db(app):
    """Crea tablas si no existen y siembra los usuarios iniciales sin duplicar.

    Es idempotente y tolerante a arranques concurrentes (varios workers de
    gunicorn): si otro proceso ya creó las tablas o los usuarios, este continúa
    sin fallar.
    """
    from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

    with app.app_context():
        try:
            db.create_all()
        except (OperationalError, ProgrammingError):
            # Otro worker pudo estar creando las tablas al mismo tiempo.
            db.session.rollback()
        try:
            _seed_users(app)
            db.session.commit()
        except IntegrityError:
            # Otro worker ya sembró los usuarios (choque de username único).
            db.session.rollback()


def _seed_users(app):
    for username, full_name, role, env_key in SEED_USERS:
        existing = User.query.filter_by(username=username).first()
        if existing is not None:
            continue
        raw_pw = app.config.get(env_key) or app.config["DEFAULT_TEMP_PASSWORD"]
        used_default = not app.config.get(env_key)
        user = User(username=username, full_name=full_name, role=role,
                    is_active=True, must_change_password=used_default)
        user.set_password(raw_pw)
        db.session.add(user)
        app.logger.info("Usuario semilla creado: %s (%s)%s", username, role,
                        " [contraseña temporal, debe cambiarla]" if used_default else "")
