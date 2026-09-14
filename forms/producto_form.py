from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

class ProductoForm(FlaskForm):
    nombre = StringField('Nombre del Servicio/Producto', validators=[
        DataRequired(message="El nombre es obligatorio."),
        Length(min=3, max=100, message="Debe tener entre 3 y 100 caracteres.")
    ])
    descripcion = StringField('Descripción', validators=[
        DataRequired(message="La descripción es obligatoria."),
        Length(min=10, max=255, message="Debe tener entre 10 y 255 caracteres.")
    ])
    precio = FloatField('Precio ($)', validators=[
        DataRequired(message="El precio es obligatorio."),
        NumberRange(min=0.01, message="Debe ser mayor a 0.")
    ])
    duracion = StringField('Duración', validators=[
        DataRequired(message="La duración es obligatoria."),
        Length(min=1, max=50, message="Debe tener entre 1 y 50 caracteres.")
    ])
    imagen = StringField('Nombre de la Imagen (ej. servicio-1.jpg)', validators=[
        DataRequired(message="La imagen es obligatoria.")
    ])
    id_proveedor = SelectField('Proveedor Asociado', coerce=int, validators=[Optional()])
    submit = SubmitField('Guardar')
