from .equipo_form import campo_equipo, campo_modelo
from .nombre_personal import campo_nombre_personal
from wtforms.validators import Regexp
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Email, Optional


class ClienteForm(FlaskForm):
    nombre = campo_nombre_personal("Nombre del Cliente")

    cedula = StringField(
        "Cédula",
        render_kw={"inputmode": "numeric", "pattern": "[0-9]{10}", "maxlength": 10,
                   "data-validation": "optional,minlength:10,maxlength:10",
                   "data-validation-message": "La cédula debe contener exactamente 10 dígitos."},
        validators=[
            Optional(strip_whitespace=False),
            Regexp(r"\A[0-9]{10}\Z", message="La cédula debe contener exactamente 10 dígitos."),
        ],
    )
    telefono = StringField(
        "Teléfono",
        render_kw={"inputmode": "numeric", "pattern": "[0-9]+"},
        validators=[
            DataRequired(message="El teléfono es obligatorio."),
            Regexp(r"\A[0-9]+\Z", message="El teléfono debe contener solo dígitos."),
            Length(min=9, max=15, message="Debe tener entre 9 y 15 caracteres."),
        ],
    )
    correo = StringField(
        "Correo",
        render_kw={"type": "email", "data-validation": "optional,email,maxlength:100",
                   "data-validation-message": "Introduce un correo válido."},
        validators=[
            Optional(strip_whitespace=False),
            Email(message="Introduce un correo válido."),
            Length(max=100, message="No puede superar 100 caracteres."),
        ],
    )
    equipo = campo_equipo()
    modelo = campo_modelo()

    estado = SelectField(
        "Estado",
        choices=[
            ("En revisión", "En revisión"),
            ("En reparación", "En reparación"),
            ("Entregado", "Entregado"),
            ("Pendiente", "Pendiente"),
        ],
        validators=[DataRequired(message="El estado es obligatorio.")],
    )
    submit = SubmitField("Guardar")
