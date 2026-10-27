"""Configuración de la aplicación Vielma - MotoRepuestos.

Lee los valores sensibles desde variables de entorno (archivo .env).
"""
import os
from datetime import timedelta

from dotenv import load_dotenv

# Carga variables desde .env si existe.
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


class Config:
    """Configuración base compartida por todos los entornos."""

    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-insegura-cambiar-en-produccion"

    # Base de datos.
    # - DATABASE_URL: si se define (ej. PostgreSQL en Render), se usa tal cual.
    # - DATABASE_PATH: ruta al archivo SQLite (ej. un disco persistente de Render
    #   montado en /var/data). Si no, se usa instance/vielma.db local.
    _db_url = os.environ.get("DATABASE_URL")
    if _db_url:
        # SQLAlchemy requiere el prefijo postgresql:// (Render a veces da postgres://).
        if _db_url.startswith("postgres://"):
            _db_url = _db_url.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = _db_url
    else:
        _db_path = os.environ.get("DATABASE_PATH") or os.path.join(INSTANCE_DIR, "vielma.db")
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + _db_path
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        # Permite que SQLite escriba esperando bloqueos en lugar de fallar al instante.
        "connect_args": {"timeout": 15},
    }

    # Zona horaria del taller.
    TIMEZONE = os.environ.get("TIMEZONE", "America/Asuncion")

    # --- Sesión / cookies ---
    SESSION_LIFETIME_DAYS = int(os.environ.get("SESSION_LIFETIME_DAYS", "30"))
    PERMANENT_SESSION_LIFETIME = timedelta(days=SESSION_LIFETIME_DAYS)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _as_bool(os.environ.get("SESSION_COOKIE_SECURE"), False)
    REMEMBER_COOKIE_HTTPONLY = True

    # --- CSRF (Flask-WTF) ---
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # el token vive mientras viva la sesión

    # --- Semillas iniciales ---
    SEED_PASSWORD_CHRISTIAN = os.environ.get("SEED_PASSWORD_CHRISTIAN", "")
    SEED_PASSWORD_HUMBERTO = os.environ.get("SEED_PASSWORD_HUMBERTO", "")
    SEED_PASSWORD_ARTURO = os.environ.get("SEED_PASSWORD_ARTURO", "")

    # Contraseña temporal por defecto si no se define por entorno.
    DEFAULT_TEMP_PASSWORD = "cambiar123"


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = _as_bool(os.environ.get("SESSION_COOKIE_SECURE"), True)


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


def get_config():
    env = os.environ.get("FLASK_ENV", "development").lower()
    if env == "production":
        return ProductionConfig
    if env == "testing":
        return TestingConfig
    return DevelopmentConfig
