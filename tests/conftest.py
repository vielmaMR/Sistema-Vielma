import os
import sys

# Asegura que el paquete raíz esté en el path al correr pytest.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app import create_app
from config import TestingConfig
from extensions import db as _db
from models import User
import constants as C


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        _db.create_all()
        _seed_test_users()
        _db.session.commit()
    yield app
    with app.app_context():
        _db.session.remove()
        _db.drop_all()


def _seed_test_users():
    jefe = User(username="christian", full_name="Christian", role=C.ROLE_JEFE,
                is_active=True)
    jefe.set_password("secret123")
    h = User(username="humberto", full_name="Humberto", role=C.ROLE_EMPLEADO,
             is_active=True)
    h.set_password("secret123")
    a = User(username="arturo", full_name="Arturo", role=C.ROLE_EMPLEADO,
             is_active=True)
    a.set_password("secret123")
    _db.session.add_all([jefe, h, a])


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    with app.app_context():
        yield _db


def login(client, username, password="secret123"):
    return client.post("/login", data={"username": username, "password": password,
                                        "remember": "y"}, follow_redirects=True)
