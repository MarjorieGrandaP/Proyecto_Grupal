from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, DateField, SelectField, SubmitField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange


class FacturacionForm(FlaskForm):
    numero = StringField(
        "Número de Factura",
        validators=[
            DataRequired(message="El número es obligatorio."),
            Length(min=3, max=20, message="Debe tener entre 3 y 20 caracteres."),
        ],
    )

    cliente = StringField(
        "Cliente",
        validators=[
            DataRequired(message="El cliente es obligatorio."),
            Length(min=3, max=100, message="Debe tener entre 3 y 100 caracteres."),
        ],
    )

    servicio = StringField(
        "Servicio",
        validators=[
            DataRequired(message="El servicio es obligatorio."),
            Length(min=3, max=100, message="Debe tener entre 3 y 100 caracteres."),
        ],
    )

    fecha = DateField(
        "Fecha (AAAA-MM-DD)",
        format="%Y-%m-%d",
        validators=[
            DataRequired(message="La fecha es obligatoria y debe tener formato válido.")
        ],
    )

    total = FloatField(
        "Total ($)",
        validators=[
            InputRequired(message="El total es obligatorio."),
            NumberRange(min=0, message="El total debe ser mayor o igual a 0."),
        ],
    )

    estado = SelectField(
        "Estado",
        choices=[("Pagada", "Pagada"), ("Pendiente", "Pendiente")],
        validators=[DataRequired(message="El estado es obligatorio.")],
    )

    submit = SubmitField("Guardar")
