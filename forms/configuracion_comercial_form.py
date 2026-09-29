from flask_wtf import FlaskForm
from wtforms import DecimalField, BooleanField, DateField, StringField, SubmitField
from wtforms.validators import InputRequired, NumberRange, Optional, Length, ValidationError, StopValidation


def porcentaje_finito(form, field):
    if field.data is None or not field.data.is_finite() or field.data.as_tuple().exponent < -2:
        raise StopValidation('Introduce un porcentaje válido con hasta dos decimales.')


class ConfiguracionComercialForm(FlaskForm):
    porcentaje_iva = DecimalField('IVA vigente (%)', places=2,
        validators=[InputRequired(), porcentaje_finito, NumberRange(min=0, max=100)])
    descuento_activo = BooleanField('Activar descuento')
    nombre_promocion = StringField('Nombre de la promoción', validators=[Optional(), Length(max=150)])
    porcentaje_descuento = DecimalField('Descuento (%)', places=2, default=0,
        validators=[InputRequired(), porcentaje_finito, NumberRange(min=0, max=100)])
    fecha_inicio_descuento = DateField('Desde', validators=[Optional()])
    fecha_fin_descuento = DateField('Hasta', validators=[Optional()])
    guardar = SubmitField('Guardar configuración')

    def validate_fecha_fin_descuento(self, field):
        inicio = self.fecha_inicio_descuento.data
        if inicio and field.data and field.data < inicio:
            raise ValidationError('La fecha final no puede ser anterior a la inicial.')
