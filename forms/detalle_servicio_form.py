from flask_wtf import FlaskForm
from wtforms import TextAreaField
from wtforms.validators import Optional, Length


class DetalleServicioForm(FlaskForm):
    diagnostico = TextAreaField("Diagnóstico", validators=[Optional(), Length(max=10000)])
    trabajo_realizado = TextAreaField("Trabajo realizado", validators=[Optional(), Length(max=10000)])
    repuestos = TextAreaField("Repuestos o componentes utilizados", validators=[Optional(), Length(max=10000)])
    recomendaciones = TextAreaField("Recomendaciones técnicas", validators=[Optional(), Length(max=10000)])
