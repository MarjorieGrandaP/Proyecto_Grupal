from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length

class ProveedorForm(FlaskForm):
    empresa = StringField('Empresa', validators=[DataRequired(message="La empresa es obligatoria."), Length(min=3, max=100, message="Debe tener entre 3 y 100 caracteres.")])
    contacto = StringField('Contacto', validators=[DataRequired(message="El contacto es obligatorio."), Length(min=3, max=100, message="Debe tener entre 3 y 100 caracteres.")])
    telefono = StringField('Teléfono', validators=[DataRequired(message="El teléfono es obligatorio."), Length(min=9, max=15, message="Debe tener entre 9 y 15 caracteres.")])
    categoria = StringField('Categoría', validators=[DataRequired(message="La categoría es obligatoria."), Length(min=3, max=100, message="Debe tener entre 3 y 100 caracteres.")])
    submit = SubmitField('Guardar')
