import re

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, ValidationError


def validar_correo(form, field):
    """Valida el formato de correo sin depender de servicios externos."""
    if field.data and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", field.data.strip()):
        raise ValidationError("Ingresa un correo electrónico válido.")


class PerfilForm(FlaskForm):
    """Formulario para actualizar datos personales sin permitir cambiar el rol."""

    nombres = StringField(
        "Nombres",
        validators=[
            DataRequired(message="Los nombres son obligatorios."),
            Length(max=100),
        ],
    )
    apellidos = StringField(
        "Apellidos",
        validators=[
            DataRequired(message="Los apellidos son obligatorios."),
            Length(max=100),
        ],
    )
    correo = StringField(
        "Correo electrónico",
        validators=[Optional(), Length(max=120), validar_correo],
    )
    telefono = StringField(
        "Teléfono",
        validators=[Optional(), Length(max=30)],
    )
    imagen = FileField("Imagen de perfil")
    submit = SubmitField("Guardar cambios")
