from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length


class PedidoForm(FlaskForm):
    """Formulario para que un cliente solicite un servicio técnico."""

    servicio = SelectField(
        "Servicio",
        coerce=int,
        validators=[DataRequired(message="Selecciona un servicio.")],
    )
    equipo = StringField(
        "Equipo",
        validators=[
            DataRequired(message="Indica el equipo que necesita atención."),
            Length(max=100, message="El equipo no puede superar 100 caracteres."),
        ],
    )
    descripcion = TextAreaField(
        "Descripción del problema",
        validators=[
            DataRequired(message="Describe el problema del equipo."),
            Length(
                max=2000, message="La descripción no puede superar 2000 caracteres."
            ),
        ],
    )
    solicita_factura = BooleanField("Deseo factura")
    submit = SubmitField("Enviar solicitud")
