from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class ComprobanteForm(FlaskForm):
    tipo_pago = SelectField(
        "Tipo de pago",
        choices=[
            ("anticipo", "Anticipo 50 %"),
            ("total", "Total 100 %"),
            ("saldo", "Saldo"),
        ],
        validators=[DataRequired()],
    )
    archivo = FileField(
        "Comprobante",
        validators=[
            FileRequired(),
            FileAllowed(["jpg", "jpeg", "png", "pdf"], "Solo JPG, PNG o PDF."),
        ],
    )


class DecisionPagoForm(FlaskForm):
    decision = SelectField(
        "Decisión",
        choices=[("Confirmado", "Confirmar"), ("Rechazado", "Rechazar")],
        validators=[DataRequired()],
    )
    motivo = TextAreaField(
        "Motivo del rechazo", validators=[Optional(), Length(max=2000)]
    )

    def validate(self, extra_validators=None):
        valido = super().validate(extra_validators)
        if self.decision.data == "Rechazado" and not (self.motivo.data or "").strip():
            self.motivo.errors = list(self.motivo.errors) + [
                "Indica el motivo del rechazo."
            ]
            return False
        return valido
