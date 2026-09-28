from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Optional, Length

ESTADOS_PEDIDO = [
    ("Solicitado", "Solicitado"),
    ("Pendiente de anticipo", "Pendiente de anticipo"),
    ("En revisión", "En revisión"),
    ("En reparación", "En reparación"),
    ("Listo", "Listo"),
    ("Entregado", "Entregado"),
    ("Cancelado", "Cancelado"),
]


class PedidoEstadoForm(FlaskForm):
    """Formulario administrativo para actualizar el estado de un pedido."""

    estado = SelectField(
        "Estado",
        choices=ESTADOS_PEDIDO,
        validators=[DataRequired(message="Selecciona un estado válido.")],
    )
    observacion = TextAreaField("Observaciones", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Actualizar estado")


TRANSICIONES_PEDIDO = {
    "Solicitado": ("Pendiente de anticipo",),
    "Pendiente de anticipo": ("En revisión",),
    "En revisión": ("En reparación", "Listo"),
    "En reparación": ("Listo",),
    "Listo": ("Entregado",),
    "Entregado": (),
    "Cancelado": (),
}

COLORES_PEDIDO = {
    "Solicitado": "bg-primary",
    "Pendiente de anticipo": "bg-warning text-dark",
    "En revisión": "bg-warning text-dark",
    "En reparación": "estado-reparacion",
    "Listo": "bg-success",
    "Entregado": "estado-entregado",
    "Cancelado": "bg-danger",
}


def mensaje_estado_pedido(estado, fisico=True):
    return {
        "Solicitado": "Hemos recibido tu solicitud. Pronto iniciaremos la revisión.",
        "Pendiente de anticipo": "Estamos esperando la confirmación del anticipo para iniciar la revisión.",
        "En revisión": "Estamos evaluando tu solicitud para definir la atención necesaria.",
        "En reparación": "Estamos trabajando en la solución de tu solicitud.",
        "Listo": (
            "Tu equipo está listo para ser retirado." if fisico else
            "El servicio ha sido completado exitosamente."
        ),
        "Entregado": (
            "Tu equipo fue entregado y el servicio ha finalizado." if fisico else
            "El servicio fue completado satisfactoriamente."
        ),
        "Cancelado": "Tu pedido fue cancelado y permanece disponible en el historial.",
    }.get(estado, "Consulta el estado de tu solicitud.")
