from flask_wtf import FlaskForm

from wtforms import (
    StringField,
    FloatField,
    SubmitField,
    SelectField,
)

from wtforms.validators import (
    DataRequired,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
)


class ProductoForm(FlaskForm):

    # ======================================================
    # NOMBRE DEL SERVICIO
    # ======================================================
    # El nombre es obligatorio y debe contener entre
    # 3 y 100 caracteres.
    nombre = StringField(
        "Nombre del Servicio",
        validators=[
            DataRequired(message="El nombre es obligatorio."),
            Length(min=3, max=100, message="Debe tener entre 3 y 100 caracteres."),
        ],
    )

    # ======================================================
    # DESCRIPCIÓN DEL SERVICIO
    # ======================================================
    # La descripción debe contener entre 10 y 255 caracteres.
    descripcion = StringField(
        "Descripción",
        validators=[
            DataRequired(message="La descripción es obligatoria."),
            Length(min=10, max=255, message="Debe tener entre 10 y 255 caracteres."),
        ],
    )

    # ======================================================
    # PRECIO
    # ======================================================
    # InputRequired comprueba que realmente exista un valor.
    #
    # NumberRange evita registrar valores iguales o menores
    # a cero.
    precio = FloatField(
        "Precio ($)",
        validators=[
            InputRequired(message="El precio es obligatorio."),
            NumberRange(min=0.01, message="El precio debe ser mayor a 0."),
        ],
    )

    # ======================================================
    # DURACIÓN
    # ======================================================
    # La duración debe incluir una cantidad y una unidad
    # de tiempo.
    #
    # Ejemplos válidos:
    # 30 minutos
    # 1 hora
    # 1.5 horas
    # Variable
    duracion = StringField(
        "Duración",
        validators=[
            DataRequired(message="La duración es obligatoria."),
            Length(
                max=50,
                message=("La duración no puede superar " "los 50 caracteres."),
            ),
            Regexp(
                (
                    r"(?i)^(Variable|"
                    r"[0-9]+([.,][0-9]+)? "
                    r"(minuto|minutos|hora|horas))$"
                ),
                message=(
                    "Ingrese una duración válida, por ejemplo: "
                    "30 minutos, 1 hora, 1.5 horas o Variable."
                ),
            ),
        ],
    )

    # ======================================================
    # IMAGEN DEL SERVICIO
    # ======================================================
    # Las opciones se cargarán dinámicamente desde app.py
    # leyendo los archivos disponibles en static/img.
    imagen = SelectField(
        "Imagen del servicio",
        choices=[],
        validators=[DataRequired(message="Debe seleccionar una imagen.")],
    )

    # ======================================================
    # PROVEEDOR ASOCIADO
    # ======================================================
    # Este campo es opcional.
    #
    # Las opciones reales se cargan posteriormente desde
    # PostgreSQL en app.py.
    id_proveedor = SelectField(
        "Proveedor Asociado",
        coerce=int,
        validators=[Optional()],
    )

    # ======================================================
    # BOTÓN DEL FORMULARIO
    # ======================================================
    submit = SubmitField("Guardar")
