"""Rutas de autenticación: login, logout, cambio de contraseña."""
from __future__ import annotations

from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, current_app)

from extensions import db
from models import User
from forms import LoginForm, ChangePasswordForm
from auth import login_user, logout_user, current_user, login_required
from services.audit import log_action

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user() is not None:
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(form.password.data):
            flash("Usuario o contraseña incorrectos.", "danger")
            log_action(None, "login_fallido", "user", None, f"usuario={username}", commit=True)
        elif not user.is_active:
            flash("Tu usuario está desactivado. Contacta al jefe del taller.", "danger")
        else:
            login_user(user, remember=form.remember.data)
            log_action(user, "login", "user", user.id, commit=True)
            flash(f"Bienvenido, {user.full_name}.", "success")
            if user.must_change_password:
                return redirect(url_for("auth.change_password"))
            return redirect(url_for("main.index"))
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    user = current_user()
    log_action(user, "logout", "user", user.id, commit=True)
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/cambiar-contrasena", methods=["GET", "POST"])
@login_required
def change_password():
    user = current_user()
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not user.check_password(form.current_password.data):
            flash("La contraseña actual no es correcta.", "danger")
        else:
            user.set_password(form.new_password.data)
            user.must_change_password = False
            log_action(user, "cambio_contrasena", "user", user.id, commit=False)
            db.session.commit()
            flash("Contraseña actualizada correctamente.", "success")
            return redirect(url_for("main.index"))
    return render_template("auth/change_password.html", form=form,
                           forced=user.must_change_password)
