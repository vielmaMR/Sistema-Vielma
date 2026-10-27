"""Punto de entrada de la aplicación Vielma - MotoRepuestos (app factory)."""
from __future__ import annotations

import os

from flask import Flask, render_template, g, request, redirect, url_for, flash

from config import get_config, INSTANCE_DIR
from extensions import db, csrf
from auth import load_current_user, current_user
from seed import init_db
from utils.timezone import format_local, format_duration, to_local
import constants as C


def create_app(config_object=None):
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    app = Flask(__name__, instance_path=INSTANCE_DIR)
    app.config.from_object(config_object or get_config())

    # Si la base SQLite apunta a una ruta externa (ej. disco persistente en
    # Render), asegurar que su carpeta exista antes de crear las tablas.
    _db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if _db_uri.startswith("sqlite:///") and ":memory:" not in _db_uri:
        _db_file = _db_uri.replace("sqlite:///", "", 1)
        _db_dir = os.path.dirname(_db_file)
        if _db_dir:
            os.makedirs(_db_dir, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)

    _register_hooks(app)
    _register_blueprints(app)
    _register_template_helpers(app)
    _register_error_handlers(app)

    # Crea la base de datos y los usuarios semilla la primera vez.
    if not app.config.get("TESTING"):
        init_db(app)

    return app


def _register_hooks(app):
    @app.before_request
    def _load_user():
        load_current_user()
        _enforce_password_change()

    def _enforce_password_change():
        user = current_user()
        if user is None or not user.must_change_password:
            return
        # Permite acceder a la propia pantalla de cambio, logout y estáticos.
        allowed = {"auth.change_password", "auth.logout", "static"}
        if request.endpoint not in allowed:
            flash("Debes cambiar tu contraseña temporal antes de continuar.", "warning")
            return redirect(url_for("auth.change_password"))


def _register_blueprints(app):
    from blueprints.auth_routes import bp as auth_bp
    from blueprints.main_routes import bp as main_bp
    from blueprints.order_routes import bp as order_bp
    from blueprints.jefe_routes import bp as jefe_bp
    from blueprints.report_routes import bp as report_bp
    from blueprints.budget_routes import bp as budget_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(order_bp)
    app.register_blueprint(jefe_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(budget_bp)


def _register_template_helpers(app):
    tz = app.config["TIMEZONE"]

    @app.context_processor
    def inject_globals():
        return {
            "current_user": current_user(),
            "C": C,
            "STATUS_LABELS": C.STATUS_LABELS,
            "STATUS_CSS": C.STATUS_CSS,
            "shop_name": "Vielma - MotoRepuestos",
        }

    @app.template_filter("localdt")
    def _localdt(value, fmt="%d/%m/%Y %H:%M"):
        return format_local(value, tz, fmt)

    @app.template_filter("localdate")
    def _localdate(value):
        return format_local(value, tz, "%d/%m/%Y")

    @app.template_filter("dur")
    def _dur(seconds):
        return format_duration(seconds)

    @app.template_filter("money")
    def _money(value):
        if value is None:
            return "—"
        try:
            return "Gs {:,.0f}".format(float(value)).replace(",", ".")
        except (ValueError, TypeError):
            return str(value)


def _register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500


# Instancia a nivel de módulo para `flask run` y gunicorn.
app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config.get("DEBUG", False))
