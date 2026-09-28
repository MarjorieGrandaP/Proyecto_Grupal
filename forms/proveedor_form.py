from .nombre_personal import campo_nombre_personal
from wtforms.validators import Regexp
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length

class ProveedorForm(FlaskForm):
    empresa = StringField('Empresa', validators=[DataRequired(message="La empresa es obligatoria."), Length(min=3, max=100, message="Debe tener entre 3 y 100 caracteres.")])
    contacto = campo_nombre_personal("Contacto")

    telefono = StringField('Teléfono', render_kw={"inputmode": "numeric", "pattern": "[0-9]+"},
        validators=[DataRequired(message="El teléfono es obligatorio."), Regexp(r"\A[0-9]+\Z", message="El teléfono debe contener solo dígitos."), Length(min=9, max=15, message="Debe tener entre 9 y 15 caracteres.")])
    categoria = StringField('Categoría', validators=[DataRequired(message="La categoría es obligatoria."), Length(min=3, max=100, message="Debe tener entre 3 y 100 caracteres.")])
    submit = SubmitField('Guardar')
