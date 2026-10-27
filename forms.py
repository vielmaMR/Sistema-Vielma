"""Formularios con validación de servidor (WTForms) y protección CSRF."""
from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, SelectField, TextAreaField,
                     IntegerField, DecimalField, BooleanField, DateTimeLocalField,
                     SubmitField, HiddenField)
from wtforms.validators import (DataRequired, Length, Optional, NumberRange,
                                 EqualTo, ValidationError)

import constants as C


class MoneyField(DecimalField):
    """Campo de monto en guaraníes.

    Acepta valores con separador de miles ('1.500.000') o sin él ('1500000'),
    quitando los puntos antes de validar. Así es robusto aunque el usuario pegue
    un valor formateado o tenga el JavaScript desactivado. No usa decimales
    (los guaraníes no tienen céntimos de uso corriente).
    """

    def process_formdata(self, valuelist):
        if valuelist:
            raw = (valuelist[0] or "").strip()
            # Quita separadores de miles y espacios; conserva solo dígitos.
            cleaned = raw.replace(".", "").replace(",", "").replace(" ", "")
            valuelist = [cleaned] if cleaned != "" else [""]
        super().process_formdata(valuelist)


class LoginForm(FlaskForm):
    username = StringField("Usuario", validators=[DataRequired(), Length(max=50)])
    password = PasswordField("Contraseña", validators=[DataRequired()])
    remember = BooleanField("Mantener sesión iniciada", default=True)
    submit = SubmitField("Ingresar")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Contraseña actual", validators=[DataRequired()])
    new_password = PasswordField(
        "Nueva contraseña",
        validators=[DataRequired(), Length(min=6, message="Mínimo 6 caracteres.")])
    confirm = PasswordField(
        "Repetir nueva contraseña",
        validators=[DataRequired(), EqualTo("new_password", "Las contraseñas no coinciden.")])
    submit = SubmitField("Cambiar contraseña")


class EmployeeForm(FlaskForm):
    full_name = StringField("Nombre completo", validators=[DataRequired(), Length(max=120)])
    username = StringField("Usuario", validators=[DataRequired(), Length(min=3, max=50)])
    phone = StringField("Teléfono", validators=[Optional(), Length(max=40)])
    role = SelectField("Rol", choices=[(C.ROLE_EMPLEADO, "Empleado mecánico"),
                                       (C.ROLE_JEFE, "Jefe del taller")])
    is_active = BooleanField("Usuario activo", default=True)
    submit = SubmitField("Guardar")


class EmployeeCreateForm(EmployeeForm):
    password = PasswordField(
        "Contraseña inicial",
        validators=[DataRequired(), Length(min=6, message="Mínimo 6 caracteres.")])


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField(
        "Nueva contraseña",
        validators=[DataRequired(), Length(min=6, message="Mínimo 6 caracteres.")])
    submit = SubmitField("Restablecer contraseña")


def _employee_choices():
    """Se completa en la vista con los empleados activos."""
    return []


class OrderForm(FlaskForm):
    """Creación / edición de datos generales de la orden."""
    # Vehículo
    vehicle_type = SelectField(
        "Tipo de vehículo",
        choices=[(k, v) for k, v in C.VEHICLE_TYPES.items()],
        validators=[DataRequired()])
    brand = StringField("Marca", validators=[Optional(), Length(max=60)])
    model = StringField("Modelo", validators=[Optional(), Length(max=60)])
    year = IntegerField("Año", validators=[Optional(), NumberRange(min=1900, max=2100)])
    plate = StringField("Chapa / Matrícula", validators=[Optional(), Length(max=20)])
    mileage = IntegerField("Kilometraje", validators=[Optional(), NumberRange(min=0)])

    # Cliente
    client_name = StringField("Nombre del cliente", validators=[Optional(), Length(max=120)])
    client_phone = StringField("Teléfono del cliente", validators=[Optional(), Length(max=40)])

    # Trabajo
    work_type = SelectField("Tipo de trabajo", choices=C.WORK_TYPES,
                            default=C.DEFAULT_WORK_TYPE, validators=[DataRequired()])
    work_type_other = StringField("Especificar tipo de trabajo",
                                  validators=[Optional(), Length(max=120)])
    problem_description = TextAreaField("Descripción del problema / solicitud",
                                        validators=[Optional()])
    diagnosis = TextAreaField("Diagnóstico", validators=[Optional()])
    tasks_detail = TextAreaField("Detalle de tareas a realizar", validators=[Optional()])
    parts_used = TextAreaField("Repuestos utilizados", validators=[Optional()])
    observations = TextAreaField("Observaciones", validators=[Optional()])
    estimated_delivery = DateTimeLocalField("Entrega estimada", format="%Y-%m-%dT%H:%M",
                                            validators=[Optional()])

    # Económico (presupuesto estimado puede cargarse al crear)
    estimated_budget = MoneyField("Presupuesto estimado", places=0,
                                  validators=[Optional(), NumberRange(min=0)])

    # Asignación (solo jefe la ve/usa)
    assigned_to_id = SelectField("Empleado asignado", coerce=int, validators=[Optional()])
    submit = SubmitField("Guardar orden")

    def validate_work_type_other(self, field):
        if self.work_type.data == "otro" and not (field.data or "").strip():
            raise ValidationError("Debe especificar el tipo de trabajo cuando elige 'Otro'.")


class ApprovalForm(FlaskForm):
    estimated_budget = MoneyField("Presupuesto estimado", places=0,
                                  validators=[Optional(), NumberRange(min=0)])
    note = TextAreaField("Observación", validators=[Optional()])
    submit = SubmitField("Enviar a aprobación")


class ClientDecisionForm(FlaskForm):
    decision = SelectField("Decisión del cliente",
                           choices=[("aprobado", "Aprobó el presupuesto"),
                                    ("rechazado", "Rechazó el presupuesto")],
                           validators=[DataRequired()])
    note = TextAreaField("Observación", validators=[Optional()])
    submit = SubmitField("Registrar decisión")


class ConfirmForm(FlaskForm):
    approved_amount = MoneyField("Monto aprobado a cobrar", places=0,
                                 validators=[DataRequired(), NumberRange(min=0)])
    assigned_to_id = SelectField("Asignar a empleado", coerce=int,
                                 validators=[DataRequired()])
    note = TextAreaField("Observación administrativa", validators=[Optional()])
    submit = SubmitField("Confirmar orden")


class PauseForm(FlaskForm):
    reason = SelectField("Motivo de la pausa",
                         choices=[(r, r) for r in C.PAUSE_REASONS],
                         validators=[DataRequired()])
    reason_other = StringField("Especificar motivo", validators=[Optional(), Length(max=120)])
    submit = SubmitField("Pausar")


class FinishForm(FlaskForm):
    summary = TextAreaField("Resumen del trabajo realizado", validators=[Optional()])
    diagnosis = TextAreaField("Diagnóstico definitivo", validators=[Optional()])
    parts_used = TextAreaField("Repuestos utilizados", validators=[Optional()])
    observations = TextAreaField("Observaciones finales", validators=[Optional()])
    submit = SubmitField("Finalizar trabajo")


class FinalAmountForm(FlaskForm):
    final_amount = MoneyField("Monto final cobrado", places=0,
                              validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Registrar cobro")


class SimpleNoteForm(FlaskForm):
    note = TextAreaField("Observación", validators=[Optional()])
    submit = SubmitField("Confirmar")
