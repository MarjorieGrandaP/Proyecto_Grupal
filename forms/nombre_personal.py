"""Regla compartida para nombres de personas en backend y HTML."""
from wtforms import StringField
from wtforms.validators import DataRequired, Length, Regexp

LETRAS = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
# Solo letras y espacios entre palabras; nunca campos vacíos.
PATRON_NOMBRE = rf"[{LETRAS}]+(?: +[{LETRAS}]+)*"
MENSAJE_NOMBRE = "Este campo solo puede contener letras y espacios."



def campo_nombre_personal(etiqueta):
    return StringField(
        etiqueta,
        validators=[
            DataRequired(message="Este campo es obligatorio."),
            Length(min=2, max=100, message="Debe tener entre 2 y 100 caracteres."),
            Regexp(r"\A" + PATRON_NOMBRE + r"\Z", message=MENSAJE_NOMBRE),
        ],
        render_kw={
            "pattern": PATRON_NOMBRE,
            "minlength": 2,
            "maxlength": 100,
            "data-validation": "required,minlength:2,maxlength:100",
            "data-validation-message": MENSAJE_NOMBRE,
        },
    )
