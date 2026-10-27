"""Autenticación basada en sesiones de Flask y control de acceso por rol."""
from __future__ import annotations

from functools import wraps

from flask import session, g, redirect, url_for, flash, abort

from models import User
import constants as C


def load_current_user():
    """Carga el usuario de la sesión en g.user (o None)."""
    user_id = session.get("user_id")
    g.user = None
    if user_id is not None:
        from extensions import db
        user = db.session.get(User, user_id)
        # Un usuario desactivado no puede seguir usando una sesión activa.
        if user is not None and user.is_active:
            g.user = user
        else:
            session.clear()


def login_user(user, remember=True):
    session.clear()
    session["user_id"] = user.id
    session.permanent = bool(remember)
    g.user = user


def logout_user():
    session.clear()
    g.user = None


def current_user():
    return getattr(g, "user", None)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("Debes iniciar sesión para continuar.", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def jefe_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            flash("Debes iniciar sesión.", "warning")
            return redirect(url_for("auth.login"))
        if not user.is_jefe:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                return redirect(url_for("auth.login"))
            if user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
