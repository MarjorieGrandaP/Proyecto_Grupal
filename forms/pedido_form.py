from .equipo_form import campo_equipo, campo_modelo
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
    equipo = campo_equipo()
    modelo = campo_modelo()

    descripcion = TextAreaField(
        "Descripción del problema",
        validators=[
            DataRequired(message="Describe el problema del equipo."),
            Length(
                max=2000, message="La descripción no puede superar 2000 caracteres."
            ),
        ],
    )
    acepta_terminos = BooleanField("Acepto los términos y condiciones y la garantía", validators=[DataRequired(message="Debes aceptar los términos y la garantía.")])
    solicita_factura = BooleanField("Deseo factura")
    submit = SubmitField("Enviar solicitud")


class EditarPedidoForm(PedidoForm):
    """Solo datos del servicio solicitado; no modifica datos administrativos."""
    acepta_terminos = None
    solicita_factura = None
    submit = SubmitField("Guardar cambios")
