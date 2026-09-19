from flask_wtf import FlaskForm
from wtforms import PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length

from .password_policy import validar_politica_password, PASSWORD_POLICY_MESSAGE


class CambioPasswordForm(FlaskForm):
    """Formulario para cambiar la contraseña del usuario autenticado."""

    password_actual = PasswordField(
        "Contraseña actual",
        validators=[DataRequired(message="La contraseña actual es obligatoria.")],
    )
    password_nueva = PasswordField(
        "Nueva contraseña",
        validators=[
            DataRequired(message="La nueva contraseña es obligatoria."),
            Length(min=8, max=100, message=PASSWORD_POLICY_MESSAGE),
            validar_politica_password,
        ],
    )
    confirmar_password = PasswordField(
        "Confirmar nueva contraseña",
        validators=[
            DataRequired(message="Debes confirmar la nueva contraseña."),
            EqualTo("password_nueva", message="Las contraseñas no coinciden."),
        ],
    )
    submit = SubmitField("Cambiar contraseña")
