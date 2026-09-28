from flask_wtf import FlaskForm
from wtforms import SelectField, TextAreaField, BooleanField
from wtforms.validators import DataRequired, Length, Optional

MOTIVOS_CLIENTE = (
    "Ya no necesito el servicio", "Ingresé información incorrecta",
    "Elegí el servicio equivocado", "Deseo realizar otra solicitud", "Otro",
)
MOTIVOS_ADMIN = (
    "Cliente solicitó cancelación", "Cliente no respondió", "Solicitud duplicada", "Servicio no procedente",
    "Falta de anticipo", "Otro",
)


class CancelacionForm(FlaskForm):
    motivo = SelectField("Motivo de cancelación", validators=[DataRequired(message="Selecciona un motivo.")])
    observacion = TextAreaField(
        "Observaciones / detalle de Otro",
        validators=[Optional(), Length(max=2000)],
    )

    def validate(self, extra_validators=None):
        valido = super().validate(extra_validators)
        if self.motivo.data == "Otro" and not (self.observacion.data or "").strip():
            self.observacion.errors = list(self.observacion.errors) + ["Describe el motivo de cancelación."]
            valido = False
        return valido


class AnticipoForm(FlaskForm):
    solicitado = BooleanField("Anticipo solicitado", validators=[DataRequired(message="Confirma que se solicitó el anticipo.")])


class ObservacionPedidoForm(FlaskForm):
    visible_cliente = BooleanField("Visible para el cliente", default=False)
    texto = TextAreaField("Añadir observación", validators=[
        DataRequired(message="Escribe una observación."), Length(max=2000)
    ])
