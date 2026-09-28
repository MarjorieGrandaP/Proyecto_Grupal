from decimal import Decimal
from flask_wtf import FlaskForm
from wtforms import DecimalField, DateField, SelectField, SubmitField
from wtforms.validators import DataRequired, InputRequired, NumberRange


class FacturacionForm(FlaskForm):
    id_cliente = SelectField(
        "Cliente",
        choices=[],
        validators=[DataRequired(message="El cliente es obligatorio.")],
    )

    id_servicio = SelectField(
        "Servicio",
        choices=[],
        validators=[DataRequired(message="El servicio es obligatorio.")],
    )

    fecha = DateField(
        "Fecha (AAAA-MM-DD)",
        format="%Y-%m-%d",
        validators=[
            DataRequired(message="La fecha es obligatoria y debe tener formato válido.")
        ],
    )

    total = DecimalField(
        "Total ($)",
        validators=[
            InputRequired(message="El total es obligatorio."),
            NumberRange(min=0, max=Decimal('99999999.99'), message="El total debe estar entre 0 y 99999999.99."),
        ],
    )

    estado = SelectField(
        "Estado",
        choices=[("Pagada", "Pagada"), ("Pendiente", "Pendiente")],
        validators=[DataRequired(message="El estado es obligatorio.")],
    )

    submit = SubmitField("Guardar")
