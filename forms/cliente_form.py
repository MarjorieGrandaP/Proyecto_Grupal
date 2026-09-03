from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length

class ClienteForm(FlaskForm):
    nombre = StringField('Nombre del Cliente', validators=[DataRequired(message="El nombre es obligatorio."), Length(min=3, max=100, message="Debe tener entre 3 y 100 caracteres.")])
    telefono = StringField('Teléfono', validators=[DataRequired(message="El teléfono es obligatorio."), Length(min=9, max=15, message="Debe tener entre 9 y 15 caracteres.")])
    equipo = StringField('Equipo', validators=[DataRequired(message="El equipo es obligatorio."), Length(min=3, max=100, message="Debe tener entre 3 y 100 caracteres.")])
    estado = SelectField('Estado', choices=[('En revisión', 'En revisión'), ('En reparación', 'En reparación'), ('Entregado', 'Entregado'), ('Pendiente', 'Pendiente')], validators=[DataRequired(message="El estado es obligatorio.")])
    submit = SubmitField('Guardar')
