from flask_wtf import FlaskForm
from wtforms import SubmitField


class PedidoAccionForm(FlaskForm):
    """Formulario CSRF para acciones POST sobre un pedido."""

    submit = SubmitField("Confirmar")
