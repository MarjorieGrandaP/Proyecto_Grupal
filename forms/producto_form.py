import re
from decimal import Decimal
from flask_wtf import FlaskForm

from wtforms import (
    StringField,
    DecimalField,
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
    precio = DecimalField(
        "Precio ($)",
        validators=[
            InputRequired(message="El precio es obligatorio."),
            NumberRange(
                min=Decimal("0.01"),
                max=Decimal("99999999.99"),
                message="El precio debe estar entre 0.01 y 99999999.99.",
            ),
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
                    r"(minuto|minutos|hora|horas|día|días|semana|semanas))$"
                ),
                message=(
                    "Ingrese una duración válida, por ejemplo: "
                    "30 minutos, 1 hora, 1.5 horas o Variable."
                ),
            ),
        ],
    )

    duracion_cantidad = DecimalField(
        "Tiempo",
        places=2,
        validators=[
            Optional(),
            NumberRange(min=Decimal("0.01"), max=Decimal("999999.99")),
        ],
    )
    duracion_unidad = SelectField(
        "Unidad",
        choices=[
            ("", "Selecciona"),
            ("Minutos", "Minutos"),
            ("Horas", "Horas"),
            ("Días", "Días"),
            ("Semanas", "Semanas"),
            ("Variable", "Variable"),
        ],
        validators=[Optional()],
    )

    def validate(self, extra_validators=None):
        estructurada = bool(self.duracion_unidad.raw_data)
        if estructurada:
            if self.duracion_unidad.data == "Variable":
                self.duracion_cantidad.data = None
                self.duracion_cantidad.raw_data = []
                self.duracion_cantidad.process_errors = []
                self.duracion.data = "Variable"
            elif (
                self.duracion_cantidad.data is not None
                and self.duracion_cantidad.data.is_finite()
            ):
                self.duracion.data = f"{self.duracion_cantidad.data.normalize():f} {self.duracion_unidad.data.lower()}"
        else:
            # Compatibilidad de clientes antiguos; la interfaz ya usa cantidad/unidad.
            cantidad, unidad = separar_duracion(self.duracion.data)
            self.duracion_cantidad.data, self.duracion_unidad.data = cantidad, unidad
        valido = super().validate(extra_validators)
        if self.duracion_unidad.data != "Variable" and (
            self.duracion_cantidad.data is None
            or not self.duracion_cantidad.data.is_finite()
            or self.duracion_cantidad.data <= 0
        ):
            self.duracion_cantidad.errors = list(self.duracion_cantidad.errors) + [
                "Indica una cantidad mayor que cero."
            ]
            valido = False
        return valido

    # ======================================================
    # IMAGEN DEL SERVICIO
    # ======================================================
    # Las opciones se cargarán dinámicamente desde app.py
    # combinando static/img y la biblioteca PostgreSQL.
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
    requiere_entrega_equipo = SelectField(
        "¿Requiere que el cliente deje o retire físicamente el equipo?",
        choices=[("si", "Sí"), ("no", "No")],
        default="si",
        validators=[DataRequired(message="Selecciona la modalidad del servicio.")],
    )
    submit = SubmitField("Guardar")


def separar_duracion(texto):
    if (texto or "").lower() == "variable":
        return None, "Variable"
    match = re.fullmatch(
        r"([0-9]+(?:[.,][0-9]+)?) (minutos?|horas?|días?|semanas?)", texto or "", re.I
    )
    if not match:
        return None, ""
    unidad = match[2].lower()
    normal = (
        "Minutos"
        if unidad.startswith("minuto")
        else (
            "Horas"
            if unidad.startswith("hora")
            else "Días" if unidad.startswith("día") else "Semanas"
        )
    )
    return Decimal(match[1].replace(",", ".")), normal
