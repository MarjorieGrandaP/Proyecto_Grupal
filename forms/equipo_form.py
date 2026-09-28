"""Campos compartidos para datos de equipos; modelo opcional."""
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, Regexp, ValidationError

LETRAS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
PATRON_EQUIPO = rf"(?=.*[{LETRAS}])[{LETRAS}0-9 \-]+"
MENSAJE_EQUIPO = "El equipo debe contener al menos una letra y solo admite letras, números, espacios y guiones."


def campo_equipo():
    return StringField(
        "Equipo",
        validators=[
            DataRequired(message="El equipo es obligatorio."),
            Length(max=100, message="El equipo no puede superar 100 caracteres."),
            Regexp(r"\A" + PATRON_EQUIPO + r"\Z", message=MENSAJE_EQUIPO),
        ],
        render_kw={
            "pattern": PATRON_EQUIPO, "maxlength": 100,
            "data-validation": "required,maxlength:100",
            "data-validation-message": MENSAJE_EQUIPO,
        },
    )


def campo_modelo():
    return StringField(
        "Modelo (opcional)",
        validators=[Optional(), Length(max=100, message="El modelo no puede superar 100 caracteres.")],
        render_kw={"maxlength": 100, "data-validation": "optional,maxlength:100",
                   "data-validation-message": "El modelo no puede superar 100 caracteres."},
    )


class EquipoPedidoForm(FlaskForm):
    equipo = campo_equipo()
    modelo = campo_modelo()
    descripcion = TextAreaField("Descripción del problema", validators=[Length(max=2000)])

    def validate_descripcion(self, field):
        if field.raw_data and not (field.data or "").strip():
            raise ValidationError("Describe el problema del equipo.")

    submit = SubmitField("Guardar corrección")
