from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField
from wtforms.validators import DataRequired

ESTADOS_PEDIDO = [
    ("Solicitado", "Solicitado"),
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
    submit = SubmitField("Actualizar estado")
