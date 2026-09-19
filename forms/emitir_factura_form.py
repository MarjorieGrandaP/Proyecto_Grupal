from flask_wtf import FlaskForm
from wtforms import SubmitField


class EmitirFacturaForm(FlaskForm):
    """Protege con CSRF la emisión administrativa de una factura."""

    submit = SubmitField("Emitir factura")
