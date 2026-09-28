from .nombre_personal import campo_nombre_personal
from wtforms.validators import Regexp
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

    nombres = campo_nombre_personal("Nombres")

    apellidos = campo_nombre_personal("Apellidos")

    correo = StringField(
        "Correo electrónico",
        validators=[Optional(), Length(max=120), validar_correo],
    )
    telefono = StringField(
        "Teléfono",
        render_kw={"inputmode": "numeric", "pattern": "[0-9]+"},
        validators=[Optional(strip_whitespace=False), Regexp(r"\A[0-9]+\Z", message="El teléfono debe contener solo dígitos."), Length(max=30)],
    )
    imagen = FileField("Imagen de perfil")
    submit = SubmitField("Guardar cambios")
